from typing import Literal
import asyncio
from fastmcp import FastMCP
from pydantic import BaseModel, Field
from ddgs import DDGS
import pprint as pp


mcp = FastMCP(name="WebSearchTool")
DOMAINS = []
# DOMAINS = ['https://moeaca.nat.gov.tw/',"https://moeacaweb.nat.gov.tw/"]
SERVER_PORT = 8018

class WebSearchInput(BaseModel):
    query: str = Field(..., description="要搜尋的查詢字串。")


class WebSearchOutput(BaseModel):
    type: Literal["text", "error"]
    result: list[dict]


@mcp.tool(name="web_search")
async def web_search(query: str = Field(..., description="放入需要查詢的問題")) -> dict:
    """
    FAQ問答工具
    """
    try:
        with DDGS() as s:
            all_hits = []
            if DOMAINS:
                for d in DOMAINS:
                    all_hits += s.text(f'{query}', max_results=5,
                                    region="tw-tzh", backend="yahoo")
            else:
                all_hits += s.text(f'{query}', max_results=5,
                                    region="tw-tzh", backend="yahoo")
            # 使用安全的方式輸出結果數量（避免 Unicode 編碼問題）
            print(f"[WebSearch] Found {len(all_hits)} results")

        return WebSearchOutput(type="text", result=all_hits)

    except Exception as e:
        error_msg = str(e).encode('ascii', 'replace').decode('ascii')
        return {"error": f"網頁搜尋時發生錯誤: {error_msg}"}


def test_web_search(query: str):
    """

    """
    print("test")
    try:
        print("test")
        with DDGS() as s:
            print("test")
            all_hits = []
            if DOMAINS:
                for d in DOMAINS:
                    print("test")
                    all_hits += s.text(f'site:{d} {query}', max_results=5,
                                       region="tw-tzh", backend="yahoo")
            else:
                all_hits += s.text(f'{query}', max_results=5,
                                   region="tw-tzh", backend="yahoo")
            pp.pp(all_hits)
            print(f"{all_hits=}")
            return WebSearchOutput(type="text", result=all_hits)

    except Exception as e:
        return {"error": f"網頁搜尋時發生錯誤: {e}"}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", "-p", type=int, required=False, default=8021)
    args = parser.parse_args()
    
    print(f"Starting MCP Web Extract Server on port {args.port}...")
    asyncio.run(mcp.run_http_async(host="0.0.0.0", port=args.port))
    # print("test")
    # result = test_web_search("絕區零 最新角色")
    # print(result)
