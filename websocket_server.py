"""
WebSocket 聊天伺服器
整合 agent.py 的 AI 功能，提供 WebSocket 即時通訊
支援模擬模式用於 UI 測試
"""

import asyncio
import datetime
import json
import os
from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# 嘗試導入 agent.py，如果失敗則使用模擬模式
MOCK_MODE = False
KAG_AGENT_AVAILABLE = False

try:
    from agent import (
        get_agent_async,
        Runner,
        InMemorySessionService,
        InMemoryArtifactService,
        RunConfig,
        StreamingMode,
        types
    )
    print("[Agent] 成功載入 AI Agent 模組")
except ImportError as e:
    print(f"⚠️ 無法載入 AI Agent 模組: {e}")
    print("🔄 啟用模擬模式 (Demo Mode)")
    MOCK_MODE = True

# 嘗試導入 KAG Agent
try:
    from agents import get_kag_agent_async
    KAG_AGENT_AVAILABLE = True
    print("[Agent] 成功載入 KAG Agent 模組")
except ImportError as e:
    print(f"⚠️ 無法載入 KAG Agent: {e}")
    KAG_AGENT_AVAILABLE = False

app = FastAPI(title="AI Chat WebSocket Server")

# 靜態文件目錄
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)

# 掛載靜態文件
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class ConnectionManager:
    """管理 WebSocket 連接"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.agents: Dict[str, any] = {}
        # 持久化 Session 相關物件以保持對話連續性
        self.session_services: Dict[str, any] = {}  # client_id -> SessionService
        self.sessions: Dict[str, any] = {}  # client_id -> Session
        self.runners: Dict[str, any] = {}  # client_id -> Runner
    
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        print(f"[連接] 客戶端 {client_id} 已連接")
    
    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        # 注意：斷開連接時不刪除 session，以便重新連接時恢復對話
        print(f"[斷開] 客戶端 {client_id} 已斷開")
    
    async def send_message(self, client_id: str, message: dict):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(message)
    
    async def get_or_create_agent(self, client_id: str):
        if not MOCK_MODE:
            if client_id not in self.agents:
                self.agents[client_id] = await get_agent_async(client_id)
            return self.agents[client_id]
        return None
    
    async def get_or_create_session(self, client_id: str):
        """獲取或創建持久化的 Session"""
        if not MOCK_MODE:
            # 如果 SessionService 不存在，創建一個
            if client_id not in self.session_services:
                self.session_services[client_id] = InMemorySessionService()
                print(f"[Session] 為 {client_id} 創建新的 SessionService")
            
            session_service = self.session_services[client_id]
            
            # 如果 Session 不存在，創建一個
            if client_id not in self.sessions:
                session = await session_service.create_session(
                    state={},
                    app_name='websocket_chat',
                    user_id=client_id
                )
                self.sessions[client_id] = session
                print(f"[Session] 為 {client_id} 創建新的對話 Session (ID: {session.id})")
            
            return session_service, self.sessions[client_id]
        return None, None
    
    async def get_or_create_runner(self, client_id: str, agent, session_service):
        """獲取或創建持久化的 Runner"""
        if not MOCK_MODE:
            if client_id not in self.runners:
                artifacts_service = InMemoryArtifactService()
                self.runners[client_id] = Runner(
                    app_name='websocket_chat',
                    agent=agent,
                    artifact_service=artifacts_service,
                    session_service=session_service,
                )
                print(f"[Runner] 為 {client_id} 創建新的 Runner")
            return self.runners[client_id]
        return None
    
    def clear_session(self, client_id: str):
        """清除特定客戶端的對話（開始新對話時使用）"""
        if client_id in self.sessions:
            del self.sessions[client_id]
        if client_id in self.runners:
            del self.runners[client_id]
        if client_id in self.session_services:
            del self.session_services[client_id]
        if client_id in self.agents:
            del self.agents[client_id]
        print(f"[Session] 已清除 {client_id} 的對話記錄")


manager = ConnectionManager()


async def mock_ai_response(user_message: str, send_func):
    """
    模擬 AI 回應，用於測試 UI
    """
    mock_responses = {
        "你好": "你好！我是 AI 智能助手。我可以幫助您回答問題、提供資訊、協助完成各種任務。有什麼我可以幫您的嗎？",
        "你能做什麼？": """我可以幫您完成很多事情，包括：

1. **回答問題** - 從歷史、科學到生活常識
2. **提供建議** - 旅遊、購物、學習等方面
3. **協助寫作** - 文章、郵件、報告等
4. **程式碼協助** - 解釋程式碼、除錯、建議優化方案
5. **創意發想** - 腦力激盪、故事創作等

有什麼想問我的嗎？""",
        "today天氣如何？": "<think>用戶詢問天氣...這需要連接天氣 API 才能取得即時資料。在模擬模式下，我無法取得實際天氣資訊。</think>\n\n抱歉，目前處於模擬模式，無法取得即時天氣資訊。當連接到實際 AI 後，我可以為您查詢天氣！",
        "給我一些靈感": """這裡有一些靈感給您：

✨ **創意專案點子**
- 製作一個個人作品集網站
- 開發一個習慣追蹤 App
- 設計一個智能家居控制面板

🎨 **藝術創作靈感**
- 嘗試抽象表現主義風格
- 用文字拼貼創作詩歌
- 記錄每日一景攝影計畫

📚 **學習新技能**
- 學習一種新的程式語言
- 嘗試手作皮革工藝
- 開始學習樂器或音樂製作

希望這些靈感對您有幫助！需要更多具體的建議嗎？"""
    }
    
    # 預設回應
    response = mock_responses.get(user_message)
    if not response:
        response = f"""<think>收到訊息：「{user_message}」

正在分析用戶需求...
這是一個模擬回應，實際 AI 會提供更豐富的答案。</think>

我收到了您的訊息：**「{user_message}」**

目前處於 **模擬模式**，這是一個預設回應。當您安裝好 `google-adk` 套件並配置好 AI Agent 後，我就能提供真正的智能回答！

🔧 **如何啟用完整 AI 功能：**
1. 確保安裝必要的依賴套件
2. 設定 AI API 金鑰
3. 重新啟動伺服器

如果需要協助，請參考專案文檔。"""

    # 模擬串流效果
    await send_func({"type": "stream_start"})
    
    # 將回應分成小塊發送，模擬串流
    chunk_size = 3
    for i in range(0, len(response), chunk_size):
        chunk = response[i:i+chunk_size]
        await send_func({"type": "stream", "content": chunk})
        await asyncio.sleep(0.02)  # 模擬延遲
    
    await send_func({"type": "stream_end", "full_content": response})


@app.get("/")
async def root():
    """返回聊天頁面"""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health():
    """健康檢查"""
    return {"status": "ok", "mock_mode": MOCK_MODE, "message": "服務運行中"}


# ========== PDF 處理相關 ==========

from fastapi import UploadFile, File, Form
import tempfile
import io

# 嘗試導入 PDF 處理庫
try:
    import fitz  # PyMuPDF
    PDF_SUPPORT = True
    print("[PDF] PDF 處理模組 (PyMuPDF) 已載入")
except ImportError:
    try:
        import PyPDF2
        PDF_SUPPORT = True
        print("[PDF] PDF 處理模組 (PyPDF2) 已載入")
    except ImportError:
        PDF_SUPPORT = False
        print("⚠️ 未安裝 PDF 處理庫 (PyMuPDF 或 PyPDF2)")


# 存儲已上傳的文件和提取的知識
uploaded_documents: Dict[str, dict] = {}
knowledge_graph_data = {
    "nodes": [],
    "edges": []
}

# 從 SQLite 載入已存儲的知識
def load_knowledge_from_storage():
    """啟動時從 SQLite 載入已有知識"""
    global uploaded_documents
    try:
        from knowledge_storage import get_knowledge_storage
        storage = get_knowledge_storage()
        all_knowledge = storage.get_all_knowledge()
        
        # 按文檔分組重建 uploaded_documents
        for doc in all_knowledge.get("documents", []):
            doc_id = doc["id"]
            doc_entities = [
                e for e in all_knowledge.get("entities", [])
                if e.get("document_id") == doc_id
            ]
            doc_relations = [
                r for r in all_knowledge.get("relations", [])
                if r.get("document_id") == doc_id
            ]
            
            uploaded_documents[doc_id] = {
                "filename": doc["filename"],
                "text_length": doc.get("text_length", 0),
                "entities": [
                    {"name": e["name"], "type": e["type"], "description": e.get("description", "")}
                    for e in doc_entities
                ],
                "relations": [
                    {"from": r["from"], "to": r["to"], "relation": r.get("relation", "")}
                    for r in doc_relations
                ],
                "processed_at": doc.get("created_at", "")
            }
        
        if uploaded_documents:
            print(f"[Knowledge] 已從資料庫載入 {len(uploaded_documents)} 份文檔的知識")
    except Exception as e:
        print(f"[Knowledge] 載入知識時發生錯誤: {e}")

# 啟動時載入知識
load_knowledge_from_storage()


def extract_text_from_pdf(pdf_content: bytes) -> str:
    """從 PDF 提取文字"""
    try:
        import fitz
        doc = fitz.open(stream=pdf_content, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    except ImportError:
        pass
    
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_content))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text
    except ImportError:
        pass
    
    return ""


async def extract_knowledge_with_llm(text: str, document_name: str) -> dict:
    """使用 LLM 從文本中提取知識 (實體和關係)"""
    
    # 如果文本太長，只取前 4000 字符
    text_chunk = text[:4000] if len(text) > 4000 else text
    
    if MOCK_MODE or not text_chunk.strip():
        # 模擬模式：根據文檔名稱生成模擬知識
        mock_entities = [
            {"name": f"{document_name[:10]}概念1", "type": "concept", "description": "從文檔提取的概念"},
            {"name": f"{document_name[:10]}概念2", "type": "concept", "description": "從文檔提取的概念"},
            {"name": f"實體A", "type": "entity", "description": "識別的實體"},
        ]
        mock_relations = [
            {"from": f"{document_name[:10]}概念1", "to": f"{document_name[:10]}概念2", "relation": "相關"},
        ]
        return {
            "entities": mock_entities,
            "relations": mock_relations
        }
    
    # 真實模式：使用 AI Agent 提取知識
    try:
        prompt = f"""請從以下文檔內容中提取知識圖譜信息，只提取最重要的 3-5 個實體。

文檔名稱: {document_name}

文檔內容(節錄):
{text_chunk[:2000]}

請以 JSON 格式返回，包含兩個數組:
1. entities: 實體列表(最多5個)，每個實體包含 name(名稱), type(類型: concept/entity/tech), description(簡短描述)
2. relations: 關係列表，每個關係包含 from(起始實體名), to(目標實體名), relation(關係類型)

只返回純 JSON，不要 markdown 代碼塊，不要其他說明文字。
格式示例: {{"entities": [{{"name": "概念A", "type": "concept", "description": "描述"}}], "relations": []}}
"""
        
        # 使用 KAG Agent (來自 agents 模組)
        if KAG_AGENT_AVAILABLE:
            agent = await get_kag_agent_async()
            print("📊 使用 KAG Agent 提取知識")
        else:
            # 回退到主 Agent
            agent = await get_agent_async("kag_processor")
            print("📊 使用主 Agent 提取知識")
        
        session_service = InMemorySessionService()
        session = await session_service.create_session(
            state={},
            app_name='kag_extractor',
            user_id='system'
        )
        
        runner = Runner(
            app_name='kag_extractor',
            agent=agent,
            artifact_service=InMemoryArtifactService(),
            session_service=session_service,
        )
        
        content = types.Content(
            role='user',
            parts=[types.Part(text=prompt)]
        )
        
        response_text = ""
        async for event in runner.run_async(
            session_id=session.id,
            user_id=session.user_id,
            new_message=content,
            run_config=RunConfig(streaming_mode=StreamingMode.NONE, max_llm_calls=5)
        ):
            if event.content and event.content.parts[0].text:
                response_text += event.content.parts[0].text
        
        # 嘗試解析 JSON - 更穩健的方式
        import re
        
        # 先嘗試找到包含 entities 和 relations 的 JSON
        try:
            # 找到第一個 { 和最後一個 } 之間的內容
            start_idx = response_text.find('{')
            if start_idx != -1:
                # 計算括號平衡來找到正確的結束位置
                depth = 0
                end_idx = start_idx
                for i, char in enumerate(response_text[start_idx:], start_idx):
                    if char == '{':
                        depth += 1
                    elif char == '}':
                        depth -= 1
                        if depth == 0:
                            end_idx = i + 1
                            break
                
                json_str = response_text[start_idx:end_idx]
                result = json.loads(json_str)
                
                # 確保有必要的鍵
                if 'entities' in result or 'relations' in result:
                    return {
                        "entities": result.get("entities", []),
                        "relations": result.get("relations", [])
                    }
        except json.JSONDecodeError as je:
            print(f"JSON 解析錯誤: {je}")
        
    except Exception as e:
        print(f"LLM 提取知識失敗: {e}")
    
    # 回退到基於文檔名的模擬數據
    safe_name = document_name[:15].replace('.pdf', '')
    return {
        "entities": [
            {"name": f"{safe_name}_主題", "type": "concept", "description": f"從 {document_name} 提取"},
            {"name": f"{safe_name}_內容", "type": "entity", "description": "文檔主要內容"}
        ],
        "relations": [
            {"from": f"{safe_name}_主題", "to": f"{safe_name}_內容", "relation": "包含"}
        ]
    }


@app.post("/api/upload-pdf")
async def upload_pdf(file: UploadFile = File(...), document_id: str = Form(...)):
    """上傳並處理 PDF 文件"""
    
    if not file.filename.lower().endswith('.pdf'):
        return {"success": False, "error": "僅支援 PDF 文件"}
    
    try:
        # 讀取文件內容
        pdf_content = await file.read()
        
        # === 新增：儲存 PDF 到 uploads/ 資料夾 ===
        import os
        from pathlib import Path
        uploads_dir = Path(__file__).parent / "uploads"
        uploads_dir.mkdir(exist_ok=True)
        
        pdf_path = uploads_dir / f"{document_id}_{file.filename}"
        with open(pdf_path, "wb") as f:
            f.write(pdf_content)
        print(f"[PDF] 已儲存到: {pdf_path}")
        
        # 提取文字
        if PDF_SUPPORT:
            text = extract_text_from_pdf(pdf_content)
        else:
            text = f"[PDF 處理庫未安裝，無法提取文字。文件名: {file.filename}]"
        
        # 使用 LLM 提取知識
        knowledge = await extract_knowledge_with_llm(text, file.filename)
        
        entities = knowledge.get("entities", [])
        relations = knowledge.get("relations", [])
        
        # 存儲到內存
        uploaded_documents[document_id] = {
            "filename": file.filename,
            "text_length": len(text),
            "entities": entities,
            "relations": relations,
            "processed_at": datetime.datetime.now().isoformat()
        }
        
        # 存儲到 SQLite 知識庫
        try:
            from knowledge_storage import get_knowledge_storage
            storage = get_knowledge_storage()
            storage.save_knowledge(
                doc_id=document_id,
                filename=file.filename,
                text=text[:5000],  # 只存儲前 5000 字符
                entities=entities,
                relations=relations
            )
        except Exception as storage_error:
            print(f"知識存儲警告: {storage_error}")
        
        # === 新增：存入向量資料庫 ===
        try:
            from vector_storage import get_vector_storage
            vector_storage = get_vector_storage()
            
            vectors = []
            
            # 對每個實體做 embedding
            for entity in entities:
                entity["document_id"] = document_id
                vectors.append(vector_storage.embed_entity(entity))
            
            # 對每個關係做 embedding
            for relation in relations:
                relation["document_id"] = document_id
                vectors.append(vector_storage.embed_relation(relation))
            
            # 批量存入向量
            if vectors:
                vector_storage.upsert_vectors(vectors)
                print(f"[Vector] 已存入 {len(vectors)} 個向量到 Qdrant")
                
        except Exception as vector_error:
            print(f"向量存儲警告: {vector_error}")
        
        return {
            "success": True,
            "document_id": document_id,
            "filename": file.filename,
            "text_length": len(text),
            "entities": entities,
            "relations": relations,
            "vectors_count": len(vectors) if 'vectors' in dir() else 0,
            "message": f"成功處理文件，提取了 {len(entities)} 個實體，已存入向量資料庫"
        }
        
    except Exception as e:
        import traceback
        print(f"PDF 處理錯誤: {e}")
        traceback.print_exc()
        return {"success": False, "error": str(e)}


@app.get("/api/documents")
async def get_documents():
    """獲取已上傳的文檔列表"""
    return {
        "documents": [
            {
                "id": doc_id,
                "filename": doc["filename"],
                "entities_count": len(doc.get("entities", [])),
                "processed_at": doc.get("processed_at")
            }
            for doc_id, doc in uploaded_documents.items()
        ]
    }


@app.delete("/api/documents/{doc_id}")
async def delete_document(doc_id: str):
    """刪除文檔（從內存、SQLite、Qdrant 和 uploads 資料夾）"""
    try:
        # 從內存刪除
        if doc_id in uploaded_documents:
            del uploaded_documents[doc_id]
        
        # 從 SQLite 刪除
        try:
            from knowledge_storage import get_knowledge_storage
            storage = get_knowledge_storage()
            storage.delete_document(doc_id)
            print(f"[Knowledge] 已從 SQLite 刪除文檔: {doc_id}")
        except Exception as e:
            print(f"[Knowledge] SQLite 刪除失敗: {e}")
        
        # 從 Qdrant 刪除向量
        try:
            from vector_storage import get_vector_storage
            vector_storage = get_vector_storage()
            vector_storage.delete_by_document(doc_id)
            print(f"[Vector] 已從 Qdrant 刪除文檔向量: {doc_id}")
        except Exception as e:
            print(f"[Vector] Qdrant 刪除失敗: {e}")
        
        # 從 uploads 資料夾刪除 PDF 文件
        try:
            from pathlib import Path
            uploads_dir = Path(__file__).parent / "uploads"
            if uploads_dir.exists():
                # 搜尋符合 doc_id 開頭的文件
                for pdf_file in uploads_dir.glob(f"{doc_id}_*"):
                    pdf_file.unlink()
                    print(f"[Uploads] 已刪除 PDF 文件: {pdf_file.name}")
        except Exception as e:
            print(f"[Uploads] PDF 文件刪除失敗: {e}")
        
        return {"success": True, "message": f"已刪除文檔 {doc_id}（含知識圖譜、向量和 PDF 文件）"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/knowledge-graph")
async def get_knowledge_graph():
    """獲取知識圖譜數據（含 Qdrant 向量統計）"""
    all_nodes = []
    all_edges = []
    
    node_id = 1000
    for doc_id, doc in uploaded_documents.items():
        # 添加文檔節點
        doc_node_id = node_id
        all_nodes.append({
            "id": doc_node_id,
            "label": doc["filename"][:20],
            "group": "document"
        })
        node_id += 1
        
        # 添加實體節點
        entity_map = {}
        for entity in doc.get("entities", []):
            entity_map[entity["name"]] = node_id
            all_nodes.append({
                "id": node_id,
                "label": entity["name"],
                "group": entity.get("type", "entity")
            })
            all_edges.append({
                "from": doc_node_id,
                "to": node_id
            })
            node_id += 1
        
        # 添加關係邊
        for rel in doc.get("relations", []):
            from_id = entity_map.get(rel["from"])
            to_id = entity_map.get(rel["to"])
            if from_id and to_id:
                all_edges.append({
                    "from": from_id,
                    "to": to_id,
                    "label": rel.get("relation", "")
                })
    
    # 獲取 Qdrant 向量統計
    vector_stats = {"points_count": 0, "status": "unknown"}
    try:
        from vector_storage import get_vector_storage
        vector_storage = get_vector_storage()
        vector_stats = vector_storage.get_stats()
    except Exception as e:
        vector_stats["error"] = str(e)
    
    # 如果內存中沒有數據，嘗試從 SQLite 獲取統計
    sqlite_stats = {"documents": 0, "entities": 0, "relations": 0}
    try:
        from knowledge_storage import get_knowledge_storage
        storage = get_knowledge_storage()
        all_knowledge = storage.get_all_knowledge()
        sqlite_stats = {
            "documents": len(all_knowledge.get("documents", [])),
            "entities": len(all_knowledge.get("entities", [])),
            "relations": len(all_knowledge.get("relations", []))
        }
    except Exception as e:
        print(f"[Knowledge] 獲取 SQLite 統計失敗: {e}")
    
    # 使用內存或 SQLite 中較大的數值
    docs_count = max(len(uploaded_documents), sqlite_stats["documents"])
    nodes_count = len(all_nodes) if all_nodes else sqlite_stats["entities"]
    edges_count = len(all_edges) if all_edges else sqlite_stats["relations"]
    
    return {
        "nodes": all_nodes, 
        "edges": all_edges,
        "stats": {
            "documents_count": docs_count,
            "nodes_count": nodes_count,
            "edges_count": edges_count,
            "vectors_count": vector_stats.get("points_count", 0),
            "qdrant_status": vector_stats.get("status", "unknown")
        }
    }


@app.get("/api/knowledge/search")
async def search_knowledge(keyword: str = ""):
    """搜尋知識庫"""
    try:
        from knowledge_storage import get_knowledge_storage
        storage = get_knowledge_storage()
        
        if keyword:
            results = storage.search_knowledge(keyword)
        else:
            results = storage.get_all_knowledge()
        
        return {"success": True, **results}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/knowledge/for-ai")
async def get_knowledge_for_ai():
    """獲取 AI 可使用的知識摘要"""
    try:
        from knowledge_storage import get_knowledge_storage
        storage = get_knowledge_storage()
        
        knowledge_text = storage.get_knowledge_for_ai()
        
        return {
            "success": True,
            "knowledge": knowledge_text,
            "usage": "將此內容注入到 AI 的 system prompt 中"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """主要的 WebSocket 端點"""
    await manager.connect(websocket, client_id)
    
    async def send_func(msg):
        await manager.send_message(client_id, msg)
    
    try:
        while True:
            # 接收客戶端訊息
            data = await websocket.receive_json()
            message_type = data.get("type", "message")
            
            if message_type == "message":
                user_message = data.get("content", "")
                user_images = data.get("images", [])  # Base64 格式的圖片列表
                
                if not user_message.strip() and not user_images:
                    continue
                
                # 通知開始處理
                await send_func({
                    "type": "status",
                    "status": "processing",
                    "message": "正在處理您的請求..."
                })
                
                # 如果是模擬模式，使用模擬回應
                if MOCK_MODE:
                    await mock_ai_response(user_message, send_func)
                    continue
                
                # 以下是真實 AI 處理邏輯
                try:
                    # 獲取或創建持久化的 Agent
                    agent = await manager.get_or_create_agent(client_id)
                    
                    # 獲取或創建持久化的 Session（保持對話連續性）
                    session_service, session = await manager.get_or_create_session(client_id)
                    
                    # 獲取或創建持久化的 Runner
                    runner = await manager.get_or_create_runner(client_id, agent, session_service)
                    
                    # 構建 Content parts
                    parts = []
                    
                    # 添加圖片 parts
                    if user_images:
                        import base64
                        for img_obj in user_images:
                            try:
                                # 前端發送格式: {data: "data:image/png;base64,...", type: "image/png", name: "..."}
                                if isinstance(img_obj, dict):
                                    img_data = img_obj.get('data', '')
                                    img_type = img_obj.get('type', 'image/png')
                                else:
                                    img_data = img_obj  # 相容舊格式
                                    img_type = 'image/png'
                                
                                if not img_data:
                                    continue
                                
                                # 處理 data URL 格式 (data:image/png;base64,...)
                                if ',' in img_data:
                                    header, encoded = img_data.split(',', 1)
                                    # 從 header 提取 mime_type
                                    if 'image/png' in header:
                                        mime_type = 'image/png'
                                    elif 'image/jpeg' in header or 'image/jpg' in header:
                                        mime_type = 'image/jpeg'
                                    elif 'image/gif' in header:
                                        mime_type = 'image/gif'
                                    elif 'image/webp' in header:
                                        mime_type = 'image/webp'
                                    else:
                                        mime_type = img_type or 'image/png'
                                else:
                                    encoded = img_data
                                    mime_type = img_type or 'image/png'
                                
                                # 直接使用 base64 字串（與 agent.py 的 get_screenshot_part 一致）
                                # 創建圖片 Part
                                parts.append(types.Part(
                                    inline_data=types.Blob(
                                        mime_type=mime_type,
                                        data=encoded  # 使用 base64 字串而非 bytes
                                    )
                                ))
                                print(f"[Image] 已添加圖片到請求 ({mime_type}, {len(encoded)} chars)")
                            except Exception as img_error:
                                print(f"[Image] 處理圖片失敗: {img_error}")
                    
                    # 添加文字 part（附加時間戳）
                    query = user_message + f" now_time : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    parts.append(types.Part(text=query))
                    
                    content = types.Content(
                        role='user',
                        parts=parts
                    )
                    
                    # ===== 調試輸出 =====
                    print("=" * 60)
                    print("[DEBUG] 使用者輸入:", user_message)
                    print("[DEBUG] 圖片數量:", len(user_images) if user_images else 0)
                    print("[DEBUG] Parts 內容:")
                    for i, part in enumerate(parts):
                        if hasattr(part, 'text') and part.text:
                            print(f"  Part[{i}] TEXT: {part.text[:200]}{'...' if len(part.text) > 200 else ''}")
                        elif hasattr(part, 'inline_data') and part.inline_data:
                            print(f"  Part[{i}] IMAGE: mime={part.inline_data.mime_type}, size={len(str(part.inline_data.data))} chars")
                        else:
                            print(f"  Part[{i}] OTHER: {type(part)}")
                    print("=" * 60)
                    
                    # 開始串流回應
                    full_response = ""
                    is_first_chunk = True
                    
                    async for event in runner.run_async(
                        session_id=session.id,
                        user_id=session.user_id,
                        new_message=content,
                        run_config=RunConfig(
                            streaming_mode=StreamingMode.SSE,
                            max_llm_calls=100
                        )
                    ):
                        if event.content:
                            # 處理函數調用（工具使用）
                            if event.content.parts[0].function_call is not None:
                                fn_call = event.content.parts[0].function_call
                                print(f"呼叫工具={fn_call.name}||傳入參數:{fn_call.args}\n=====================================================")
                                await send_func({
                                    "type": "tool_call",
                                    "name": fn_call.name,
                                    "args": str(fn_call.args)[:200]
                                })
                            
                            # 處理函數回應
                            elif event.content.parts[0].function_response is not None:
                                fn_resp = event.content.parts[0].function_response
                                response_payload = fn_resp.response
                                result_payload = (
                                    response_payload.get("result", response_payload)
                                    if isinstance(response_payload, dict)
                                    else response_payload
                                )

                                tmp = None
                                if isinstance(result_payload, dict):
                                    content = result_payload.get("content")
                                    if isinstance(content, list) and content:
                                        first = content[0]
                                        if isinstance(first, dict) and "text" in first:
                                            tmp = first["text"]
                                elif getattr(result_payload, "content", None):
                                    first = result_payload.content[0]
                                    tmp = getattr(first, "text", None) or str(first)

                                if tmp is None:
                                    try:
                                        tmp = json.dumps(result_payload, ensure_ascii=False, default=str)
                                    except Exception:
                                        tmp = str(result_payload)

                                if len(tmp) > 2000:
                                    tmp = tmp[:2000] + "...(truncated)"
                                print(f"工具回應={fn_resp.name}||回傳結果:{tmp}\n=====================================================")
                                
                                await send_func({
                                    "type": "tool_response",
                                    "name": fn_resp.name
                                })
                            
                            # 處理串流文字
                            elif event.partial and event.content.parts[0].text:
                                text_chunk = event.content.parts[0].text
                                if text_chunk.strip():
                                    full_response += text_chunk
                                    
                                    if is_first_chunk:
                                        await send_func({"type": "stream_start"})
                                        is_first_chunk = False
                                    
                                    await send_func({
                                        "type": "stream",
                                        "content": text_chunk
                                    })
                    
                    # 串流結束
                    if not full_response.strip():
                        # 如果沒有收到任何文字回應
                        full_response = "[AI 未產生文字回應，請重試或檢查 API 連線]"
                        print("[Warning] AI 未產生文字回應")
                    
                    # ===== 模型輸出調試 =====
                    print("=" * 60)
                    print("[DEBUG] 模型輸出:")
                    print(full_response[:500] if len(full_response) > 500 else full_response)
                    if len(full_response) > 500:
                        print(f"... (共 {len(full_response)} 字)")
                    print("=" * 60)
                    
                    await send_func({
                        "type": "stream_end",
                        "full_content": full_response
                    })
                    
                except Exception as e:
                    import traceback
                    error_detail = traceback.format_exc()
                    print(f"[錯誤] 處理訊息時發生錯誤: {e}")
                    print(f"[錯誤詳情] {error_detail}")
                    await send_func({
                        "type": "error",
                        "message": f"處理請求時發生錯誤: {str(e)}"
                    })
            
            elif message_type == "ping":
                await send_func({"type": "pong"})
    
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        print(f"[錯誤] WebSocket 錯誤: {e}")
        manager.disconnect(client_id)


if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("🚀 啟動 WebSocket 聊天伺服器...")
    print("=" * 50)
    if MOCK_MODE:
        print("⚠️  模擬模式啟用中 - AI 回應為模擬內容")
    else:
        print("[Agent] AI Agent 模組已載入")
    print(f"📡 伺服器地址: http://localhost:8765")
    print("🌐 開啟瀏覽器訪問上述地址開始聊天")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8765)
