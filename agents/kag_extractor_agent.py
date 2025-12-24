"""
KAG (Knowledge Agentic Graph) Extractor Agent
負責從文本中提取實體和關係，構建知識圖譜

使用方式:
    from agents import get_kag_agent_async
    
    agent = await get_kag_agent_async()
"""

import os
from google.adk.agents.llm_agent import LlmAgent
from google.adk.models.lite_llm import LiteLlm

# 使用與主 Agent 相同的模型配置
os.environ.setdefault('OPENAI_API_BASE', "http://127.0.0.1:9000/v1")
os.environ.setdefault('OPENAI_API_KEY', "123456")

# KAG Agent 使用的模型
KAG_MODEL = LiteLlm(model="openai/gemini-3-flash")


async def get_kag_agent_async():
    """
    獲取 KAG (知識圖譜提取) Agent
    
    Returns:
        LlmAgent: 配置好的知識圖譜提取 Agent
    """
    
    kag_agent = LlmAgent(
        model=KAG_MODEL,
        name="知識圖譜提取助手",
        instruction="""你是一位專業的知識圖譜提取助手。

你的任務是從文本中提取結構化的知識圖譜數據，包括：

1. **實體 (Entities)**：識別文本中的重要概念、人物、組織、地點、技術等
2. **關係 (Relations)**：識別實體之間的關係

## 輸出格式要求

請以純 JSON 格式返回，不要包含 markdown 代碼塊，不要有額外說明文字。

格式範例：
{"entities": [{"name": "實體名稱", "type": "concept/entity/tech/model/person/org", "description": "簡短描述"}], "relations": [{"from": "起始實體名", "to": "目標實體名", "relation": "關係描述"}]}

## 注意事項
- 只提取最重要的 3-5 個實體
- 確保實體名稱簡短明確
- 關係描述要簡潔
- 只返回 JSON，不要有其他內容
""",
        tools=[],  # KAG Agent 不需要額外工具
    )
    
    return kag_agent


# 便利函數：同步獲取 Agent
def get_kag_agent_sync():
    """
    同步獲取 KAG Agent（注意：這會阻塞）
    """
    import asyncio
    return asyncio.get_event_loop().run_until_complete(get_kag_agent_async())
