"""
向量存儲模組
支援 Gemini 和 Voyage AI 兩種 Embedding 服務
"""

from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct, Filter, FieldCondition, MatchValue
from typing import List, Dict, Optional
import uuid

from config import (
    EMBEDDING_PROVIDER,
    GEMINI_API_KEY, GEMINI_EMBEDDING_MODEL,
    VOYAGE_API_KEY, VOYAGE_MODEL,
    QDRANT_HOST, QDRANT_PORT, QDRANT_COLLECTION,
    VECTOR_DIMENSION, SEARCH_TOP_K
)


class VectorStorage:
    """向量存儲類 - 管理 embedding 產生和 Qdrant 操作"""
    
    def __init__(self):
        """初始化 Embedding 客戶端和 Qdrant"""
        self.provider = EMBEDDING_PROVIDER
        
        if self.provider == "gemini":
            # 嘗試使用新的 google.genai，否則回退到舊的 google.generativeai
            try:
                from google import genai
                self.genai_client = genai.Client(api_key=GEMINI_API_KEY)
                self.use_new_genai = True
                print(f"[VectorStorage] 使用 google.genai (新版)")
            except ImportError:
                import google.generativeai as genai
                genai.configure(api_key=GEMINI_API_KEY)
                self.genai_module = genai
                self.use_new_genai = False
                print(f"[VectorStorage] 使用 google.generativeai (舊版)")
            self.embed_model = GEMINI_EMBEDDING_MODEL
            print(f"[VectorStorage] Gemini Embedding 模型: {self.embed_model}")
        else:
            import voyageai
            self.voyage_client = voyageai.Client(api_key=VOYAGE_API_KEY)
            self.embed_model = VOYAGE_MODEL
            print(f"[VectorStorage] 使用 Voyage AI: {self.embed_model}")
        
        self.qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        self._ensure_collection()
        print(f"[VectorStorage] 已連接 Qdrant: {QDRANT_HOST}:{QDRANT_PORT}")
    
    def _ensure_collection(self):
        """確保 collection 存在"""
        collections = [c.name for c in self.qdrant_client.get_collections().collections]
        
        if QDRANT_COLLECTION not in collections:
            self.qdrant_client.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=VectorParams(
                    size=VECTOR_DIMENSION,
                    distance=Distance.COSINE
                )
            )
            print(f"[VectorStorage] 已創建 collection: {QDRANT_COLLECTION}")
    
    def embed_texts(self, texts: List[str], input_type: str = "document") -> List[List[float]]:
        """
        對文本列表產生 embedding
        
        Args:
            texts: 文本列表
            input_type: "document" 用於存儲, "query" 用於搜尋
            
        Returns:
            embedding 向量列表
        """
        if not texts:
            return []
        
        if self.provider == "gemini":
            task_type = "RETRIEVAL_DOCUMENT" if input_type == "document" else "RETRIEVAL_QUERY"
            embeddings = []
            
            for text in texts:
                if self.use_new_genai:
                    # 新版 google.genai API
                    result = self.genai_client.models.embed_content(
                        model=self.embed_model,
                        contents=text,
                        config={"task_type": task_type}
                    )
                    embeddings.append(result.embeddings[0].values)
                else:
                    # 舊版 google.generativeai API
                    result = self.genai_module.embed_content(
                        model=f"models/{self.embed_model}",
                        content=text,
                        task_type=task_type
                    )
                    embeddings.append(result['embedding'])
            
            return embeddings
        else:
            # 使用 Voyage AI
            result = self.voyage_client.embed(
                texts,
                model=self.embed_model,
                input_type=input_type
            )
            return result.embeddings
    
    def embed_entity(self, entity: Dict) -> Dict:
        """對實體產生 embedding"""
        text = f"{entity['name']} ({entity.get('type', 'entity')}): {entity.get('description', '')}"
        embeddings = self.embed_texts([text], input_type="document")
        
        return {
            "id": str(uuid.uuid4()),
            "vector": embeddings[0],
            "payload": {
                "type": "entity",
                "document_id": entity.get("document_id", ""),
                "entity_name": entity["name"],
                "entity_type": entity.get("type", "entity"),
                "description": entity.get("description", ""),
                "text": text
            }
        }
    
    def embed_relation(self, relation: Dict) -> Dict:
        """對關係產生 embedding"""
        text = f"{relation['from']} {relation['relation']} {relation['to']}"
        embeddings = self.embed_texts([text], input_type="document")
        
        return {
            "id": str(uuid.uuid4()),
            "vector": embeddings[0],
            "payload": {
                "type": "relation",
                "document_id": relation.get("document_id", ""),
                "from_entity": relation["from"],
                "to_entity": relation["to"],
                "relation_type": relation["relation"],
                "text": text
            }
        }

    def embed_document_chunk(self, chunk_text: str, doc_id: str, chunk_index: int) -> Dict:
        """對文檔塊產生 embedding"""
        embeddings = self.embed_texts([chunk_text], input_type="document")
        
        return {
            "id": str(uuid.uuid4()),
            "vector": embeddings[0],
            "payload": {
                "type": "document_chunk",
                "document_id": doc_id,
                "chunk_index": chunk_index,
                "text": chunk_text
            }
        }
    
    def upsert_vectors(self, vectors: List[Dict]) -> bool:
        """批量存入向量"""
        if not vectors:
            return True
        
        try:
            points = [
                PointStruct(
                    id=v["id"],
                    vector=v["vector"],
                    payload=v["payload"]
                )
                for v in vectors
            ]
            
            self.qdrant_client.upsert(
                collection_name=QDRANT_COLLECTION,
                points=points
            )
            
            print(f"[VectorStorage] 已存入 {len(points)} 個向量")
            return True
            
        except Exception as e:
            print(f"[VectorStorage] 存入向量失敗: {e}")
            return False
    
    def search(self, query: str, limit: int = SEARCH_TOP_K, 
               filter_type: Optional[str] = None) -> List[Dict]:
        """語義搜尋"""
        try:
            query_vector = self.embed_texts([query], input_type="query")[0]
            
            search_filter = None
            if filter_type:
                search_filter = Filter(
                    must=[
                        FieldCondition(
                            key="type",
                            match=MatchValue(value=filter_type)
                        )
                    ]
                )
            
            # 使用 query_points（新版 API）或 search（舊版 API）
            try:
                # 新版 qdrant-client
                from qdrant_client.models import QueryRequest
                results = self.qdrant_client.query_points(
                    collection_name=QDRANT_COLLECTION,
                    query=query_vector,
                    limit=limit,
                    query_filter=search_filter
                )
                hits = results.points
            except (ImportError, AttributeError):
                # 舊版 qdrant-client
                hits = self.qdrant_client.search(
                    collection_name=QDRANT_COLLECTION,
                    query_vector=query_vector,
                    limit=limit,
                    query_filter=search_filter
                )
            
            formatted_results = []
            for hit in hits:
                result = {
                    "score": hit.score,
                    "type": hit.payload.get("type"),
                    "text": hit.payload.get("text"),
                    "document_id": hit.payload.get("document_id")
                }
                
                if hit.payload.get("type") == "entity":
                    result["entity_name"] = hit.payload.get("entity_name")
                    result["entity_type"] = hit.payload.get("entity_type")
                    result["description"] = hit.payload.get("description")
                else:
                    result["from"] = hit.payload.get("from_entity")
                    result["to"] = hit.payload.get("to_entity")
                    result["relation"] = hit.payload.get("relation_type")
                
                formatted_results.append(result)
            
            return formatted_results
            
        except Exception as e:
            print(f"[VectorStorage] 搜尋失敗: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def delete_by_document(self, document_id: str) -> bool:
        """刪除指定文檔的所有向量"""
        try:
            self.qdrant_client.delete(
                collection_name=QDRANT_COLLECTION,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id)
                        )
                    ]
                )
            )
            print(f"[VectorStorage] 已刪除文檔 {document_id} 的向量")
            return True
        except Exception as e:
            print(f"[VectorStorage] 刪除向量失敗: {e}")
            return False
    
    def get_stats(self) -> Dict:
        """獲取 collection 統計信息"""
        try:
            info = self.qdrant_client.get_collection(QDRANT_COLLECTION)
            return {
                "points_count": info.points_count,
                "status": str(info.status)
            }
        except Exception as e:
            return {"error": str(e)}


# 全局單例
_vector_storage_instance = None


def get_vector_storage() -> VectorStorage:
    """獲取向量存儲單例"""
    global _vector_storage_instance
    if _vector_storage_instance is None:
        _vector_storage_instance = VectorStorage()
    return _vector_storage_instance
