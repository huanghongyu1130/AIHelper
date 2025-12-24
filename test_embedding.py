"""
測試 Voyage AI Embedding + Qdrant 向量資料庫
執行: python test_embedding.py
"""

import voyageai
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

# ===== 配置 =====
VOYAGE_API_KEY = "pa-QAbRHGsYoqhGlJJ2L6x3yXEk9Gro44BSIS2u75pLS44"
VOYAGE_MODEL = "voyage-large-2"  # 支援的模型列表中的通用模型
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTION_NAME = "test_knowledge"


def test_voyage_embedding():
    """測試 Voyage AI Embedding"""
    print("=" * 50)
    print("[1] 測試 Voyage AI Embedding")
    print("=" * 50)
    
    try:
        vo = voyageai.Client(api_key=VOYAGE_API_KEY)
        
        # 測試文本
        texts = [
            "機器學習是人工智慧的一個分支",
            "深度學習使用神經網路進行學習",
            "Python 是最流行的程式語言之一"
        ]
        
        print(f"輸入文本: {texts}")
        
        # 產生 embedding
        result = vo.embed(
            texts,
            model=VOYAGE_MODEL,
            input_type="document"
        )
        
        embeddings = result.embeddings
        print(f"✓ 成功產生 {len(embeddings)} 個 embedding")
        print(f"✓ 向量維度: {len(embeddings[0])}")
        print(f"✓ 範例向量 (前5個值): {embeddings[0][:5]}")
        
        return embeddings, texts
        
    except Exception as e:
        print(f"✗ Voyage AI 錯誤: {e}")
        return None, None


def test_qdrant_connection():
    """測試 Qdrant 連接"""
    print("\n" + "=" * 50)
    print("[2] 測試 Qdrant 連接")
    print("=" * 50)
    
    try:
        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        
        # 獲取集合列表
        collections = client.get_collections()
        print(f"✓ 成功連接 Qdrant")
        print(f"✓ 現有集合: {[c.name for c in collections.collections]}")
        
        return client
        
    except Exception as e:
        print(f"✗ Qdrant 連接錯誤: {e}")
        print("  請確認 Qdrant 是否正在運行: docker run -p 6333:6333 qdrant/qdrant")
        return None


def test_create_collection(client, vector_size):
    """測試創建集合"""
    print("\n" + "=" * 50)
    print("[3] 測試創建集合")
    print("=" * 50)
    
    try:
        # 檢查集合是否存在
        collections = [c.name for c in client.get_collections().collections]
        
        if COLLECTION_NAME in collections:
            print(f"✓ 集合 '{COLLECTION_NAME}' 已存在，刪除重建...")
            client.delete_collection(COLLECTION_NAME)
        
        # 創建新集合
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE
            )
        )
        
        print(f"✓ 成功創建集合 '{COLLECTION_NAME}'")
        print(f"  向量維度: {vector_size}")
        print(f"  距離度量: Cosine")
        
        return True
        
    except Exception as e:
        print(f"✗ 創建集合錯誤: {e}")
        return False


def test_insert_vectors(client, embeddings, texts):
    """測試插入向量"""
    print("\n" + "=" * 50)
    print("[4] 測試插入向量")
    print("=" * 50)
    
    try:
        points = [
            PointStruct(
                id=i,
                vector=embedding,
                payload={"text": text, "source": "test"}
            )
            for i, (embedding, text) in enumerate(zip(embeddings, texts))
        ]
        
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        )
        
        print(f"✓ 成功插入 {len(points)} 個向量")
        
        # 確認插入
        info = client.get_collection(COLLECTION_NAME)
        print(f"✓ 集合現有 {info.points_count} 個點")
        
        return True
        
    except Exception as e:
        print(f"✗ 插入向量錯誤: {e}")
        return False


def test_search(client, vo):
    """測試向量搜尋"""
    print("\n" + "=" * 50)
    print("[5] 測試向量搜尋")
    print("=" * 50)
    
    try:
        query = "什麼是 AI 和機器學習?"
        print(f"查詢: {query}")
        
        # 產生查詢向量
        result = vo.embed(
            [query],
            model=VOYAGE_MODEL,
            input_type="query"  # 查詢時用 query
        )
        query_vector = result.embeddings[0]
        
        # 搜尋
        search_result = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            limit=3
        )
        
        print(f"\n搜尋結果 (Top 3):")
        for i, hit in enumerate(search_result):
            print(f"  {i+1}. [相似度: {hit.score:.4f}] {hit.payload['text']}")
        
        return True
        
    except Exception as e:
        print(f"✗ 搜尋錯誤: {e}")
        return False


def main():
    print("\n" + "=" * 50)
    print("   Voyage AI + Qdrant 整合測試")
    print("=" * 50)
    
    # 1. 測試 Voyage AI
    embeddings, texts = test_voyage_embedding()
    if not embeddings:
        return
    
    # 2. 測試 Qdrant 連接
    client = test_qdrant_connection()
    if not client:
        return
    
    # 3. 創建集合
    vector_size = len(embeddings[0])
    if not test_create_collection(client, vector_size):
        return
    
    # 4. 插入向量
    if not test_insert_vectors(client, embeddings, texts):
        return
    
    # 5. 測試搜尋
    vo = voyageai.Client(api_key=VOYAGE_API_KEY)
    test_search(client, vo)
    
    print("\n" + "=" * 50)
    print("✓ 所有測試完成！")
    print("=" * 50)


if __name__ == "__main__":
    main()
