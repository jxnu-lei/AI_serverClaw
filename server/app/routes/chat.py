"""
聊天相关 API
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional

from app.database import get_db
from app.models.user import User
from app.models.chat_session import ChatSession, ChatMessage
from app.routes.auth import get_current_active_user
from app.routes.llm import generate_llm_response
from app.schemas.llm import LLMRequest

router = APIRouter(prefix="/api/chat", tags=["Chat"])


# ==================== 会话管理 ====================

@router.post("/sessions")
async def create_chat_session(
    connection_id: Optional[str] = None,
    title: Optional[str] = None,
    host: str = "",            # 新增：接收服务器IP
    username: str = "",        # 新增：接收用户名
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """创建新的聊天会话"""
    session = ChatSession(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        connection_id=connection_id,
        title=title or "新会话",
        host=host,              # 修改：保存服务器IP
        username=username,      # 修改：保存用户名
        status="active",
        start_time=datetime.now(),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {
        "id": session.id,
        "title": session.title,
        "status": session.status,
        "created_at": session.created_at
    }


@router.get("/sessions")
async def list_chat_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取用户的聊天会话列表"""
    result = await db.execute(
        select(ChatSession).where(ChatSession.user_id == current_user.id)
    )
    sessions = result.scalars().all()
    return [
        {
            "id": session.id,
            "title": session.title,
            "status": session.status,
            "created_at": session.created_at
        }
        for session in sessions
    ]


@router.post("/sessions/{session_id}/messages")
async def add_chat_message(
    session_id: str,
    message_data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """向会话添加消息"""
    # 验证会话归属
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id
        )
    )
    session = result.scalars().one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )
    
    # 从请求体中提取参数
    role = message_data.get("role")
    content = message_data.get("content")
    message_type = message_data.get("message_type", "text")
    
    # 验证必要参数
    if not role or not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="role 和 content 是必需的"
        )
    
    # 创建消息
    message = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=session_id,
        sequence=session.message_count + 1,
        role=role,
        content=content,
        message_type=message_type,
        timestamp=datetime.now(),
    )
    db.add(message)
    
    # 更新会话
    session.message_count += 1
    session.updated_at = datetime.now()
    
    await db.commit()
    await db.refresh(message)
    
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "timestamp": message.timestamp
    }


# ==================== LLM 调用 ====================

@router.post("/completions")
async def chat_completions(
    request_data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """调用真实 LLM API"""
    import httpx
    import logging
    logger = logging.getLogger(__name__)
    
    messages = request_data.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="messages 不能为空")

    # 获取 LLM 配置
    from app.routes.llm import _get_active_config
    from app.config import settings
    
    config = await _get_active_config(db, current_user.id)
    
    api_key = None
    if config and config.api_key:
        api_key = config.api_key
    elif hasattr(settings, 'DEFAULT_LLM_API_KEY') and settings.DEFAULT_LLM_API_KEY:
        api_key = settings.DEFAULT_LLM_API_KEY
    
    if not api_key:
        raise HTTPException(status_code=400, detail="LLM API key 未配置")
    
    model = config.model if config else getattr(settings, 'DEFAULT_LLM_MODEL', 'gpt-3.5-turbo')
    base_url = (getattr(config, "api_url", "") if config else "") or getattr(settings, 'DEFAULT_LLM_API_URL', '')
    temperature = (config.temperature if config else None) or 0.7
    
    # 构建 API URL
    if base_url:
        base_url = base_url.rstrip("/")
        api_url = f"{base_url}/chat/completions" if not base_url.endswith("/chat/completions") else base_url
    else:
        provider = (config.provider if config else getattr(settings, 'DEFAULT_LLM_PROVIDER', 'openai')).lower()
        if provider == "deepseek":
            api_url = "https://api.deepseek.com/v1/chat/completions"
        else:
            api_url = "https://api.openai.com/v1/chat/completions"
    
    # 调用真实 LLM API
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                api_url,
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                },
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                }
            )
        
        if response.status_code != 200:
            logger.error(f"LLM API error {response.status_code}: {response.text[:500]}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"LLM API 错误: {response.text[:500]}"
            )
        
        return response.json()
        
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="LLM API 请求超时")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"LLM API 请求失败: {str(e)}")


# 导入必要的模块
import uuid
from datetime import datetime
