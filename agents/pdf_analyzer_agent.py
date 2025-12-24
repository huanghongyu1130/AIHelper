"""
PDF Analyzer Agent
負責解析 PDF 文件並提取內容

使用方式:
    from agents import get_pdf_agent_async
    
    agent = await get_pdf_agent_async()
"""

import os
from google.adk.agents.llm_agent import LlmAgent
from google.adk.models.lite_llm import LiteLlm

# 使用與主 Agent 相同的模型配置
os.environ.setdefault('OPENAI_API_BASE', "http://127.0.0.1:9000/v1")
os.environ.setdefault('OPENAI_API_KEY', "123456")

# PDF Agent 使用的模型
PDF_MODEL = LiteLlm(model="openai/gemini-3-flash")


async def get_pdf_agent_async():
    """
    獲取 PDF 分析 Agent
    
    Returns:
        LlmAgent: 配置好的 PDF 分析 Agent
    """
    
    pdf_agent = LlmAgent(
        model=PDF_MODEL,
        name="PDF分析助手",
        instruction="""你是一位專業的 PDF 文件分析助手。

你的任務是：
1. 分析 PDF 文件的內容和結構
2. 提取關鍵信息
3. 總結文件的主要內容
4. 識別文件中的重要實體（人名、地名、組織、概念等）

請用繁體中文回答，並確保分析結果清晰且有條理。
""",
        tools=[],  # PDF Agent 不需要額外工具
    )
    
    return pdf_agent


# 便利函數：同步獲取 Agent（用於簡單場景）
def get_pdf_agent_sync():
    """
    同步獲取 PDF Agent（注意：這會阻塞）
    """
    import asyncio
    return asyncio.get_event_loop().run_until_complete(get_pdf_agent_async())
