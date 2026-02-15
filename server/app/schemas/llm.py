from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class ChatMessage(BaseModel):
    """聊天消息模型"""
    role: str
    content: str


class LLMRequest(BaseModel):
    """LLM请求模型"""
    prompt: str
    temperature: Optional[float] = 0.7
    system_prompt: Optional[str] = None
    conversation_history: Optional[List[ChatMessage]] = []
    terminal_context: Optional[str] = ""


class LLMResponse(BaseModel):
    """LLM响应模型"""
    content: str
    error: Optional[str] = None


class LLMConfigUpdate(BaseModel):
    """LLM配置更新模型"""
    provider: str
    model: str
    api_key: str
    base_url: Optional[str] = None
    temperature: Optional[float] = 0.7
    name: Optional[str] = None
    is_active: Optional[bool] = False
