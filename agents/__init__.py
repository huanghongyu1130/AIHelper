"""
Agents 模組
提供統一的 Agent 管理介面

使用方式:
    from agents import get_pdf_agent_async, get_kag_agent_async
    
    agent = await get_pdf_agent_async()
"""

from .pdf_analyzer_agent import get_pdf_agent_async
from .kag_extractor_agent import get_kag_agent_async

# 所有可用的 Agent 工廠函數
__all__ = [
    'get_pdf_agent_async',
    'get_kag_agent_async',
]

# Agent 註冊表，方便動態獲取
AGENT_REGISTRY = {
    'pdf': get_pdf_agent_async,
    'kag': get_kag_agent_async,
}


async def get_agent_by_name(name: str):
    """
    根據名稱動態獲取 Agent
    
    Args:
        name: Agent 名稱 ('pdf', 'kag')
        
    Returns:
        對應的 Agent 實例
    """
    if name not in AGENT_REGISTRY:
        raise ValueError(f"未知的 Agent: {name}。可用的 Agent: {list(AGENT_REGISTRY.keys())}")
    
    return await AGENT_REGISTRY[name]()
