import asyncio
import datetime
import json
import os
import random
import time
import base64
import io
import pyautogui
from contextlib import AsyncExitStack
from typing import Optional, Any, Dict

import pandas as pd
import requests
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.run_config import RunConfig
from google.adk.agents.run_config import StreamingMode
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService  # Optional
from google.adk.models import LlmRequest, LlmResponse
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import ToolContext, BaseTool
from google.adk.tools.mcp_tool.mcp_toolset import (
    McpToolset,
    StreamableHTTPConnectionParams,
)
from google.genai import types
from mcp import StdioServerParameters
from openpyxl.reader.excel import load_workbook
from sympy.strategies.core import switch

from activate_mcp_server import servers

# Load environment variables from .env file in the parent directory
# Place this near the top, before using env vars like API keys

log_records = []
# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s.%(msecs)03d %(levelname)-8s [%(name)s] %(message)s",
#     datefmt="%Y-%m-%d %H:%M:%S",
# )
# import litellm
# litellm.set_verbose = True

os.environ['OPENAI_API_BASE'] = "http://127.0.0.1:9000/v1"
os.environ['OPENAI_API_KEY'] = "123456"  
# ---------- env ----------
# 如果要新增不同廠家模型請參照litellm官網
# https://docs.litellm.ai/docs/providers
# 進去後點選指定
# 
MODEL = LiteLlm(model="openai/gemini-3-flash")


# ---------------------------紀錄callback---------------------------
# ---------- 1. before_agent_callback：只接收 CallbackContext，回傳 Optional[LlmResponse] ----------
def cb_before_agent(callback_context: CallbackContext) -> Optional[types.Content]:
    """
    在 Agent 核心邏輯開始前觸發，用來記錄時間。
    callback_context 內可取得 invocation_id, agent_name, state 等。
    回傳 None 表示不攔截 Agent 執行流程。
    函式簽名: (CallbackContext) -> Optional[LlmResponse]
    """
    ts = datetime.datetime.now()
    log_records.append({
        "Stage": "before_agent[START]",
        "Timestamp": ts,
        "Cost_Time": "<------開始時間",
        "Prompt": "",
        "Model_Response": "",
        "Tool": "",
    })
    return None  # 不攔截 Agent，繼續執行模型呼叫


# :contentReference[oaicite:11]{index=11}

# ---------- 2. after_agent_callback：接收 (CallbackContext, LlmResponse)，回傳 Optional[LlmResponse] ----------


def cb_after_agent(callback_context: CallbackContext) -> Optional[types.Content]:
    """
    在 Agent 執行完畢並產生 final_response 前觸發。
    可用於記錄時間、清理資源或直接覆蓋最終回應。
    函式簽名: (CallbackContext, types.LlmResponse) -> Optional[types.LlmResponse]
    """
    ts = datetime.datetime.now()
    old_ts = log_records[-1]["Timestamp"]
    log_records.append({
        "Stage": "after_agent[END]",
        "Timestamp": ts,
        "Cost_Time": f"{(ts - old_ts).total_seconds():.6f} 秒",
        "Prompt": "",
        "Model_Response": "",
        "Tool": "",
    })
    return None  # 不修改最終回應，保留 final_response


# :contentReference[oaicite:12]{index=12}

# ---------- 3. before_model_callback：接收 (CallbackContext, LlmRequest)，回傳 Optional[LlmResponse] ----------


def cb_before_model(
        callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    """
    在真正將 prompt 發送給模型前觸發，簽名: (CallbackContext, types.LlmRequest) -> Optional[types.LlmResponse]
    可檢查或修改 llm_request，例如插入動態系統提示、或依據關鍵字跳過模型呼叫。
    """
    ts = datetime.datetime.now()
    prompt_text = ""
    old_ts = log_records[-1]["Timestamp"]
    # 假設取 LlmRequest.contents 最後一條 user 訊息做示範
    if llm_request.contents and llm_request.contents[-1].role == "user":
        parts = llm_request.contents[-1].parts or []
        if parts:
            prompt_text = parts[0].text or ""
    log_records.append({
        "Stage": "before_model",
        "Timestamp": ts,
        "Cost_Time": f"{(ts - old_ts).total_seconds():.6f} 秒",
        "Prompt": prompt_text,
        "Model_Response": "",
        "Tool": "",
    })
    return None  # 不攔截，讓模型照常生成回應


# :contentReference[oaicite:13]{index=13}

# ---------- 4. after_model_callback：接收 (CallbackContext, LlmResponse)，回傳 Optional[LlmResponse] ----------


def cb_after_model(
        callback_context: CallbackContext, llm_response: LlmResponse
) -> Optional[LlmResponse]:
    """
    在模型生成完成、且回應尚未進一步傳回 Agent 前觸發。
    函式簽名: (CallbackContext, types.LlmResponse) -> Optional[types.LlmResponse]
    可檢查 llm_response.content.parts[0].text，做過濾或修改。
    """
    # resp = str(llm_response.content)
    # if resp.type = "func":
    #     switch(resp.fn)
    #
    #     result = requests.Request("http:localhost:XXXX/sse ",json=json.loads(resp.arg))
    #     return  result

    model_text = ""
    if llm_response.content and llm_response.content.parts:
        if not llm_response.partial:
            ts = datetime.datetime.now()
            old_ts = log_records[-1]["Timestamp"]
            if llm_response.content.parts[0].function_call:
                function = llm_response.content.parts[0].function_call
                log_records.append({
                    "Stage": "after_model",
                    "Timestamp": ts,
                    "Cost_Time": f"{(ts - old_ts).total_seconds():.6f} 秒",
                    "Prompt": "",
                    "Model_Response": f"思考後，模型決定呼叫 : {function.name}，參數 : {function.args}",
                    "Tool": "",
                })
                return None
            model_text = llm_response.content.parts[0].text or ""
            log_records.append({
                "Stage": "after_model",
                "Timestamp": ts,
                "Cost_Time": f"{(ts - old_ts).total_seconds():.6f} 秒",
                "Prompt": "",
                "Model_Response": model_text,
                "Tool": "",
            })
    return None  # 不修改模型回應，讓 Agent 繼續執行 Tool 或產生最終回應


# :contentReference[oaicite:14]{index=14}

# ---------- 5. before_tool_callback：接收 (BaseTool, dict, ToolContext)，回傳 Optional[dict] ----------


def cb_before_tool(
        tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext
) -> Optional[Dict]:
    """
    在 Agent 決定要呼叫某個 Tool.run_async(inputs) 前觸發。
    簽名: (BaseTool, dict[str,Any], ToolContext) -> Optional[dict[str,Any]]
    回傳 dict 可直接跳過 tool 執行，改用該 dict 作為 tool 返回值；回傳 None 則執行 tool.run(inputs)。
    """
    ts = datetime.datetime.now()
    tool_name = getattr(tool, "name", "unknown_tool")
    old_ts = log_records[-1]["Timestamp"]
    log_records.append({
        "Stage": "before_tool",
        "Timestamp": ts,
        "Cost_Time": f"{(ts - old_ts).total_seconds():.6f} 秒",
        "Prompt": "",
        "Model_Response": "",
        "Tool": f"開始呼叫 {tool_name}，傳入參數 : {args}",
    })

    return None  # 不攔截 Tool 執行，繼續執行 tool.run(inputs)


# :contentReference[oaicite:15]{index=15}

# ---------- 6. after_tool_callback：接收 (BaseTool, dict, ToolContext)，回傳 Optional[dict] ----------


def cb_after_tool(
        tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext, tool_response: Dict
) -> Optional[Dict]:
    """
    在 Tool.run_async 完成並取得 tool_output 後觸發。
    簽名: (BaseTool, dict[str,Any], ToolContext) -> Optional[dict[str,Any]]
    回傳 None 表示保留原本 tool_output；回傳 dict 可修改最終返回給 LLM 的 tool_output。
    
    特殊處理：如果工具回傳包含 screenshot (Base64)，會轉換成 types.Part 讓 LLM 能「看到」圖片。
    """
    ts = datetime.datetime.now()
    tool_name = getattr(tool, "name", "unknown_tool")
    old_ts = log_records[-1]["Timestamp"] if log_records else ts
    
    # 處理截圖：將 Base64 轉換成 types.Part
    modified_response = None
    if isinstance(tool_response, dict):
        # 檢查回應中是否有 screenshot 欄位 (可能在 result 內或直接在 tool_response)
        screenshot_b64 = None
        result_data = tool_response.get("result", tool_response)
        
        if isinstance(result_data, dict):
            screenshot_b64 = result_data.get("screenshot")
        
        if screenshot_b64 and isinstance(screenshot_b64, str):
            try:
                # 將 Base64 解碼成 bytes
                screenshot_bytes = base64.b64decode(screenshot_b64)
                
                # 建立 types.Part 物件
                screenshot_part = types.Part(
                    inline_data=types.Blob(
                        data=screenshot_bytes,
                        mime_type="image/png"
                    )
                )
                
                # 修改回應，加入 screenshot_part 並移除原始 Base64 (避免重複大量資料)
                modified_response = tool_response.copy()
                if "result" in modified_response and isinstance(modified_response["result"], dict):
                    modified_response["result"] = modified_response["result"].copy()
                    modified_response["result"]["screenshot_part"] = screenshot_part
                    # 截短 Base64 避免 log 過大
                    modified_response["result"]["screenshot"] = f"[圖片已轉換為 Part，大小: {len(screenshot_bytes)} bytes]"
                else:
                    modified_response["screenshot_part"] = screenshot_part
                    modified_response["screenshot"] = f"[圖片已轉換為 Part，大小: {len(screenshot_bytes)} bytes]"
                
                print(f"[Callback] 已將 {tool_name} 的截圖轉換為 types.Part (大小: {len(screenshot_bytes)} bytes)")
                
            except Exception as e:
                print(f"[Callback] 截圖轉換失敗: {e}")
    
    # 記錄 log (使用修改後或原始的回應)
    log_response = modified_response if modified_response else tool_response
    log_records.append({
        "Stage": "after_tool",
        "Timestamp": ts,
        "Cost_Time": f"{(ts - old_ts).total_seconds():.6f} 秒",
        "Prompt": "",
        "Model_Response": "",
        "Tool": f"接收到工具回應 {tool_name}，接收回應 : {str(log_response)[:500]}...",  # 截短避免 log 過大
    })
    
    return modified_response  # 回傳修改後的結果，或 None 保持原樣


# --- Step 1: Agent Definition ---


# def simple_before_tool_modifier(
#     tool: BaseTool, args: dict, tool_context: ToolContext
# ) -> None:
#     """Inspects/modifies tool args or skips the tool call."""
#     agent_name = tool_context.agent_name
#     tool_name = tool.name
#     print(f"[Callback] 使用工具前的呼叫內容 工具名稱:'{tool_name}' 工具參數:'{args}'")
#     # print(f"[Callback] Original args: {args}")


async def get_agent_async(conversation_id: str):
    """
    這邊後續可能要拆分成(session_service,artifacts_service) 跟 agent避免agent 重複建立
    Creates an ADK Agent equipped with tools from the MCP Server."""

    common_exit_stack = AsyncExitStack()

    # MCP使用規則
    # 依照下面的方式去新增MCP工具
    # StdioServerParameters可以仿照config.json的方式
    # SseServerParams用於URL呼叫的方式

    # 這邊把mcp的port加入 註冊工具
    mcp_server_port = servers

    all_tools_set = []
    # 默認本地網址 後面可以再改成其他網址 如果今天要掛在151應該也可以 但不確定會不會有CROS的問題(LM Studio有出現過)
    tool_name = ""

    tool_set = []

    root_agent = LlmAgent(
        model=MODEL,
        name="黃泓瑜",
        instruction="""
你是一位擅長使用工具的助手。請注意每個訊息的新鮮度與現在時間，回答時不用再提及現在時間。
使用工具時必須謹慎 且你可以多次使用工具
例如:
用WebSearch工具後
會取得大量的網址，你可以查看複數個你覺得有相關的網址

## 知識搜尋工具使用指南

你有兩個知識搜尋工具可用：

### 1. vector_search (語義搜尋)
- **用途**: 當你需要找「相關」或「類似」的知識時使用
- **例子**: 「深度學習和機器學習有什麼關係?」、「AI 技術有哪些?」
- **特點**: 即使用詞不完全匹配也能找到語義相關的結果

### 2. knowledge_search (精確搜尋)
- **用途**: 當你需要找「特定」實體或「精確」關鍵字時使用
- **例子**: 「Python 這個實體的描述是什麼?」、「查詢包含'機器學習'的所有關係」
- **特點**: 只返回完全匹配關鍵字的結果

### 選擇建議
- 用戶問題比較模糊時 → 優先使用 vector_search
- 用戶指定具體名詞時 → 優先使用 knowledge_search
- 需要獲取知識庫概覽時 → 使用 get_all_knowledge 或 get_knowledge_summary

## 其他工具
- web_search: 網頁搜尋，用於獲取最新資訊
- web_extract: 網頁內容提取，自行判斷是否需要取得更詳細資料
""",
        tools=[
            McpToolset(
                connection_params=StreamableHTTPConnectionParams(
                    url=f"http://127.0.0.1:{current_port}/mcp",
                ),
            ) for tool_name, _, tool_py_loc, current_port in mcp_server_port
        ],

        before_agent_callback=cb_before_agent,
        after_agent_callback=cb_after_agent,
        before_model_callback=cb_before_model,
        after_model_callback=cb_after_model,
        before_tool_callback=cb_before_tool,
        after_tool_callback=cb_after_tool  # 啟用：處理截圖轉換
    )

    return root_agent


# --- Step 2: Main Execution Logic ---


def get_screenshot_part():
    """擷取螢幕並轉換為 types.Part"""
    try:
        screenshot = pyautogui.screenshot()
        # 縮小圖片以節省 token 並符合 API 限制 (可選)
        screenshot.thumbnail((1280, 1280))
        
        buffered = io.BytesIO()
        screenshot.save(buffered, format="JPEG", quality=70)
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        return types.Part(
            inline_data=types.Blob(
                mime_type="image/jpeg",
                data=img_str
            )
        )
    except Exception as e:
        print(f"截圖失敗: {e}")
        return None

async def invoke(querys: list, index):
    global start_stream_time, end_stream_time, log_records
    end_stream_time =""
    root_agent = await get_agent_async("123")
    print(root_agent.model)

    for query in querys:
        session_service = InMemorySessionService()
        artifacts_service = InMemoryArtifactService()

        session = await session_service.create_session(
            state={}, app_name='mcp_filesystem_app', user_id=f"Q{index}"
        )

        runner = Runner(
            app_name='mcp_filesystem_app',
            agent=root_agent,
            artifact_service=artifacts_service,  # Optional
            session_service=session_service,
        )

        index += 1
        query = query + f" now_time : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        parts = [types.Part(text=query)]
        
        # 取得螢幕截圖並加入 parts
        screenshot_part = get_screenshot_part()
        if screenshot_part:
            parts.append(screenshot_part)
            print("已加入螢幕截圖")

        content = types.Content(role='user', parts=parts)
        print(f"User Query: '{query}'")

        print("Running agent...")

        start_stream_flag = True
        print("Agent:")
        token_count = 0
        call_count = 0

        async for event in runner.run_async(
                session_id=session.id, user_id=session.user_id, new_message=content,
                run_config=RunConfig(streaming_mode=StreamingMode.SSE,
                                        # 串流 這邊設定串流選項 ctrl點進去可以看有哪些 LM Studio目前應該是用SSE跑，None就沒串流 還有一個B開頭的不知道啥甚麼交互式的
                                        max_llm_calls=1000)  # 最多呼叫次數 應該有包含tool call
        ):
            if event.content:
                # 這邊是把串流內容全部輸出出來 後續改工具近來可能會導致工具使用狀況也被輸出 好處是比較有交互感
                if event.content.parts[0].function_call is not None:
                    call_count += 1
                    print(
                        f"呼叫工具={event.content.parts[0].function_call.name}||傳入參數:{event.content.parts[0].function_call.args}\n=====================================================")
                elif event.content.parts[0].function_response is not None:
                    # 取出回來的東西 目前都是文字 後續應該可以改用part去改成FunctionResponse的格式
                    function_response = event.content.parts[0].function_response
                    response_payload = function_response.response
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
                    print(
                        f"工具回應={event.content.parts[0].function_response.name}||回傳結果:{tmp}\n=====================================================")
                elif event.partial and event.content.parts[0].text not in ["", " ", "\\n"]:
                    if start_stream_flag:
                        start_stream_time = time.time()
                        start_stream_flag = False

                    token_count += 1
                    print(event.content.parts[0].text, end="")
                    # for c in event.content.parts[0].text:
                    #     print(c, end="", flush=True)
                    #     await asyncio.sleep(0.01)

                elif not event.partial:
                    # print(f"{event=}")
                    end_stream_time = time.time()
        print(f"\n\n總共花費時間:{end_stream_time - start_stream_time}")
        print(f"總共花費token:{token_count}")
        print(f"總共花費次數:{call_count}")



if __name__ == '__main__':

    asyncio.get_event_loop().run_until_complete(
        invoke(querys=["台灣的張文 最近是有甚麼事情嗎?，越詳細越好"], index=0))
    #     asyncio.get_event_loop().run_until_complete(invoke(querys=question_set, index=0))

    # except Exception as e:
    #     print("Unhandled error: %s", e)
