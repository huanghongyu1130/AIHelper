"""
Knowledge Query MCP Tool
讓 AI Agent 可以查詢已導入的知識庫

使用方式：
1. 啟動此 MCP 服務: python Tool/knowledge_mcp.py --port 8022
2. 在 agent.py 中註冊此工具
3. AI 可使用 knowledge_search 和 get_all_knowledge 工具
"""

import asyncio
import sys
from pathlib import Path
from typing import Literal

from fastmcp import FastMCP
from pydantic import BaseModel, Field

# 添加父目錄到路徑以導入 knowledge_storage
sys.path.insert(0, str(Path(__file__).parent.parent))

from knowledge_storage import get_knowledge_storage
# 添加父目錄到路徑以導入 vector_storage
sys.path.insert(0, str(Path(__file__).parent.parent))
from vector_storage import get_vector_storage

mcp = FastMCP(name="KnowledgeTool")
SERVER_PORT = 8022


class SearchResult(BaseModel):
    """搜尋結果"""
    type: Literal["text", "error"]
    keyword: str = ""
    entities: list = []
    relations: list = []
    chunks: list = []
    total: int = 0


class KnowledgeSummary(BaseModel):
    """知識摘要"""
    type: Literal["text", "error"]
    summary: str = ""
    document_count: int = 0
    entity_count: int = 0


@mcp.tool(name="knowledge_search")
async def knowledge_search(
    keyword: str = Field(..., description="要搜尋的關鍵字，用於在知識庫中查找相關實體和關係")
) -> dict:
    """
    【混合搜尋】結合關鍵字搜尋與向量語義搜尋。
    
    搜尋流程：
    1. 在知識庫中搜尋精確關鍵字 (SQLite)
    2. 在向量資料庫中搜尋語義相關內容 (Qdrant)
    3. 合併結果返回
    
    這樣既能找到明確的實體關係，也能找到語義相關的文本片段。
    """
    try:
        results = {}
        
        # 1. 關鍵字搜尋 (Graph)
        try:
            storage = get_knowledge_storage()
            graph_results = storage.search_knowledge(keyword)
            results["entities"] = graph_results.get("entities", [])
            results["relations"] = graph_results.get("relations", [])
        except Exception as e:
            print(f"[Knowledge] Graph search failed: {e}")
            results["entities"] = []
            results["relations"] = []
            
        # 2. 向量搜尋 (Vector)
        vector_results = []
        try:
            vector_storage = get_vector_storage()
            # 搜尋相關文檔塊
            vector_results = vector_storage.search(keyword, limit=5)
        except Exception as e:
            print(f"[Knowledge] Vector search failed: {e}")
            
        return SearchResult(
            type="text",
            keyword=keyword,
            entities=results.get("entities", []),
            relations=results.get("relations", []),
            chunks=vector_results,
            total=len(results.get("entities", [])) + len(results.get("relations", [])) + len(vector_results)
        ).model_dump()
        
    except Exception as e:
        return {"type": "error", "error": f"知識搜尋時發生錯誤: {e}"}


@mcp.tool(name="get_all_knowledge")
async def get_all_knowledge() -> dict:
    """
    獲取知識庫中的所有知識摘要。
    返回所有已導入的文檔、實體和關係的概覽。
    
    適合在需要了解知識庫整體內容時使用。
    """
    try:
        storage = get_knowledge_storage()
        all_knowledge = storage.get_all_knowledge()
        
        return {
            "type": "text",
            "documents": all_knowledge.get("documents", []),
            "entities": all_knowledge.get("entities", []),
            "relations": all_knowledge.get("relations", []),
            "stats": {
                "document_count": len(all_knowledge.get("documents", [])),
                "entity_count": len(all_knowledge.get("entities", [])),
                "relation_count": len(all_knowledge.get("relations", []))
            }
        }
        
    except Exception as e:
        return {"type": "error", "error": f"獲取知識時發生錯誤: {e}"}


@mcp.tool(name="get_knowledge_summary")
async def get_knowledge_summary() -> dict:
    """
    獲取知識庫的文字摘要，可直接融入對話上下文。
    返回格式化的知識描述，方便理解和引用。
    
    適合在回答用戶問題前了解有哪些相關知識。
    """
    try:
        storage = get_knowledge_storage()
        summary = storage.get_knowledge_for_ai()
        all_knowledge = storage.get_all_knowledge()
        
        return KnowledgeSummary(
            type="text",
            summary=summary,
            document_count=len(all_knowledge.get("documents", [])),
            entity_count=len(all_knowledge.get("entities", []))
        ).model_dump()
        
    except Exception as e:
        return {"type": "error", "error": f"獲取知識摘要時發生錯誤: {e}"}


@mcp.tool(name="check_knowledge_exists")
async def check_knowledge_exists(
    topic: str = Field(..., description="要檢查的主題或實體名稱")
) -> dict:
    """
    檢查知識庫中是否存在關於特定主題的知識。
    返回 True/False 以及找到的相關實體數量。
    
    適合在決定是否需要使用知識庫時進行快速檢查。
    """
    try:
        storage = get_knowledge_storage()
        results = storage.search_knowledge(topic)
        
        exists = results.get("total", 0) > 0
        
        return {
            "type": "text",
            "topic": topic,
            "exists": exists,
            "count": results.get("total", 0),
            "entities_found": [e["name"] for e in results.get("entities", [])[:5]]
        }
        
    except Exception as e:
        return {"type": "error", "error": f"檢查知識時發生錯誤: {e}"}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", "-p", type=int, required=False, default=SERVER_PORT)
    args = parser.parse_args()
    
    print(f"[Knowledge] Starting Knowledge MCP Server on port {args.port}...")
    print(f"[Knowledge] Available tools: knowledge_search, get_all_knowledge, get_knowledge_summary, check_knowledge_exists")
    asyncio.run(mcp.run_http_async(host="0.0.0.0", port=args.port))
