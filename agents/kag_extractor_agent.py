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

你的任務是從文本中**全面、詳盡地**提取結構化的知識圖譜數據，包括：

1. **實體 (Entities)**：識別文本中的所有重要概念、人物、組織、地點、技術、方法、系統、產品等
   - concept: 抽象概念、理論、方法論
   - tech: 技術、工具、框架、算法
   - model: 模型、架構、設計模式
   - person: 人物、作者、研究者
   - org: 組織、公司、機構、團隊
   - entity: 其他具體事物

2. **關係 (Relations)**：識別實體之間的所有有意義的關係
   - 包含/組成、使用/應用、屬於/類型、相關/關聯、創建/發明、改進/優化等

## 輸出格式要求

請以純 JSON 格式返回，不要包含 markdown 代碼塊，不要有額外說明文字。

格式範例：
{"entities": [{"name": "實體名稱", "type": "concept/entity/tech/model/person/org", "description": "簡短描述"}], "relations": [{"from": "起始實體名", "to": "目標實體名", "relation": "關係描述"}]}

## 重要提取原則
- **全面提取**：不要人為限制數量，提取所有有價值的實體和關係
- **保持專業**：使用文檔中的原始術語和名稱
- **詳細描述**：每個實體都要有有意義的描述
- **完整關係**：盡可能建立實體之間的關係連接
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
