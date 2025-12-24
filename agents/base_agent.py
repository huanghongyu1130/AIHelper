"""
BaseAgent - Agent 基類
提供所有 Agent 的共同介面和基礎功能
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseAgent(ABC):
    """Agent 基類"""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
    
    @abstractmethod
    async def process(self, input_data: Any) -> Dict[str, Any]:
        """
        處理輸入並返回結果
        
        Args:
            input_data: 輸入數據
            
        Returns:
            處理結果字典
        """
        pass
    
    @abstractmethod
    async def get_status(self) -> Dict[str, Any]:
        """
        獲取 Agent 當前狀態
        
        Returns:
            狀態字典
        """
        pass
    
    def __repr__(self):
        return f"<{self.__class__.__name__}(name='{self.name}')>"
