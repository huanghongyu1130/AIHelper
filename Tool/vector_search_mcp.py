"""
向量搜尋 MCP 工具
讓 AI Agent 可以使用語義搜尋查詢知識庫

使用方式：
1. 啟動此 MCP 服務: python Tool/vector_search_mcp.py --port 8023
2. 在 agent.py 中註冊此工具
3. AI 可使用 vector_search 工具進行語義搜尋
"""

import asyncio
import sys
from pathlib import Path
from typing import Literal, Optional

from fastmcp import FastMCP
from pydantic import BaseModel, Field

# 添加父目錄到路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from vector_storage import get_vector_storage

mcp = FastMCP(name="VectorSearchTool")
SERVER_PORT = 8023


class SearchResult(BaseModel):
    """搜尋結果"""
    type: Literal["text", "error"]
    query: str = ""
    results: list = []
    total: int = 0


@mcp.tool(name="vector_search")
async def vector_search(
    query: str = Field(..., description="要搜尋的查詢文本，用於在知識庫中進行語義搜尋"),
    filter_type: Optional[str] = Field(None, description="可選的過濾類型：'entity' 只搜尋實體，'relation' 只搜尋關係，None 搜尋全部")
) -> dict:
    """
    【語義搜尋】在知識庫中進行向量相似度搜尋，返回語義相關的 Top 5 結果。
    
    適用場景：
    - 用戶問題比較模糊，沒有指定具體關鍵字
    - 需要找「相關」或「類似」的知識
    - 想了解某個概念的相關知識
    
    例如：
    - 「深度學習和機器學習有什麼關係?」→ 可以找到「機器學習 包含 深度學習」
    - 「AI 技術有哪些?」→ 可以找到「人工智慧」、「機器學習」等相關實體
    
    注意：這是語義搜尋，即使用詞不完全匹配也能找到相關結果。
    如需精確匹配關鍵字，請使用 knowledge_search。
    """
    try:
        storage = get_vector_storage()
        results = storage.search(query, limit=5, filter_type=filter_type)
        
        # 格式化結果
        formatted_results = []
        for r in results:
            if r["type"] == "entity":
                formatted_results.append({
                    "score": round(r["score"], 4),
                    "type": "entity",
                    "name": r.get("entity_name", ""),
                    "entity_type": r.get("entity_type", ""),
                    "description": r.get("description", "")
                })
            else:
                formatted_results.append({
                    "score": round(r["score"], 4),
                    "type": "relation",
                    "text": f"{r.get('from', '')} -> {r.get('relation', '')} -> {r.get('to', '')}"
                })
        
        return SearchResult(
            type="text",
            query=query,
            results=formatted_results,
            total=len(formatted_results)
        ).model_dump()
        
    except Exception as e:
        error_msg = str(e).encode('ascii', 'replace').decode('ascii')
        return {"type": "error", "error": f"向量搜尋時發生錯誤: {error_msg}"}


@mcp.tool(name="get_vector_stats")
async def get_vector_stats() -> dict:
    """
    獲取向量資料庫的統計信息。
    
    返回目前存儲的向量數量等信息。
    """
    try:
        storage = get_vector_storage()
        stats = storage.get_stats()
        
        return {
            "type": "text",
            "points_count": stats.get("points_count", 0),
            "vectors_count": stats.get("vectors_count", 0)
        }
        
    except Exception as e:
        error_msg = str(e).encode('ascii', 'replace').decode('ascii')
        return {"type": "error", "error": f"獲取統計時發生錯誤: {error_msg}"}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", "-p", type=int, required=False, default=SERVER_PORT)
    args = parser.parse_args()
    
    print(f"[VectorSearch] Starting Vector Search MCP Server on port {args.port}...")
    print(f"[VectorSearch] Available tools: vector_search, get_vector_stats")
    asyncio.run(mcp.run_http_async(host="0.0.0.0", port=args.port))
