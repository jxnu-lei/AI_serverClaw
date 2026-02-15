"""
对话历史记录 API
"""
import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, delete
from pydantic import BaseModel

from app.database import get_db
from app.models.chat_session import ChatSession, ChatMessage
from app.routes.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/chat-history", tags=["Chat History"])


# ==================== Schemas ====================

class ChatMessageOut(BaseModel):
    id: str
    sequence: int
    role: str
    content: str
    command: Optional[str] = None
    command_output: Optional[str] = None
    command_status: Optional[str] = None
    ai_explanation: Optional[str] = None
    ai_suggested_command: Optional[str] = None
    message_type: str
    extra_data: Optional[dict] = None
    timestamp: datetime

    class Config:
        from_attributes = True


class ChatSessionOut(BaseModel):
    id: str
    title: str
    host: str
    username: str
    message_count: int
    command_count: int
    status: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatSessionDetail(ChatSessionOut):
    messages: List[ChatMessageOut] = []


class ChatSessionListResponse(BaseModel):
    total: int
    items: List[ChatSessionOut]


class CreateSessionRequest(BaseModel):
    connection_id: Optional[str] = None
    host: str = ""
    username: str = ""
    title: str = ""


class AddMessageRequest(BaseModel):
    role: str
    content: str = ""
    command: Optional[str] = None
    command_output: Optional[str] = None
    command_status: Optional[str] = None
    ai_explanation: Optional[str] = None
    ai_suggested_command: Optional[str] = None
    message_type: str = "text"
    extra_data: Optional[dict] = None


class UpdateSessionRequest(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None


# ==================== 会话管理 ====================

@router.post("/sessions", response_model=ChatSessionOut)
async def create_session(
    req: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建新的对话会话"""
    session = ChatSession(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        connection_id=req.connection_id,
        host=req.host,
        username=req.username,
        title=req.title or f"{req.username}@{req.host}" if req.host else "新会话",
        status="active",
        start_time=datetime.now(),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/sessions", response_model=ChatSessionListResponse)
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取对话会话列表"""
    query = select(ChatSession).where(ChatSession.user_id == current_user.id)
    count_query = select(func.count(ChatSession.id)).where(ChatSession.user_id == current_user.id)
    
    if status:
        query = query.where(ChatSession.status == status)
        count_query = count_query.where(ChatSession.status == status)
    
    if search:
        search_filter = ChatSession.title.ilike(f"%{search}%")
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)
    
    # 总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # 分页
    query = query.order_by(desc(ChatSession.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    sessions = result.scalars().all()
    
    return ChatSessionListResponse(total=total, items=sessions)


@router.get("/sessions/{session_id}", response_model=ChatSessionDetail)
async def get_session_detail(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取会话详情（含所有消息）"""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id)
        .where(ChatSession.user_id == current_user.id)
    )
    session = result.scalars().one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # 获取消息
    msg_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.sequence)
    )
    messages = msg_result.scalars().all()
    
    return ChatSessionDetail(
        id=session.id,
        title=session.title,
        host=session.host,
        username=session.username,
        message_count=session.message_count,
        command_count=session.command_count,
        status=session.status,
        start_time=session.start_time,
        end_time=session.end_time,
        duration=session.duration,
        created_at=session.created_at,
        messages=messages
    )


@router.put("/sessions/{session_id}", response_model=ChatSessionOut)
async def update_session(
    session_id: str,
    req: UpdateSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新会话信息"""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id)
        .where(ChatSession.user_id == current_user.id)
    )
    session = result.scalars().one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if req.title is not None:
        session.title = req.title
    if req.status is not None:
        session.status = req.status
        if req.status == "completed":
            session.end_time = datetime.now()
            if session.start_time:
                session.duration = int((session.end_time - session.start_time).total_seconds())
    
    session.updated_at = datetime.now()
    await db.commit()
    await db.refresh(session)
    return session


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除会话及其所有消息"""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id)
        .where(ChatSession.user_id == current_user.id)
    )
    session = result.scalars().one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # 删除消息
    await db.execute(
        delete(ChatMessage).where(ChatMessage.session_id == session_id)
    )
    # 删除会话
    await db.delete(session)
    await db.commit()
    
    return {"message": "Session deleted"}


# ==================== 消息管理 ====================

@router.post("/sessions/{session_id}/messages", response_model=ChatMessageOut)
async def add_message(
    session_id: str,
    req: AddMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """向会话添加消息"""
    # 验证会话归属
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id)
        .where(ChatSession.user_id == current_user.id)
    )
    session = result.scalars().one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # 获取下一个序号
    seq_result = await db.execute(
        select(func.coalesce(func.max(ChatMessage.sequence), 0))
        .where(ChatMessage.session_id == session_id)
    )
    next_seq = (seq_result.scalar() or 0) + 1
    
    message = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=session_id,
        sequence=next_seq,
        role=req.role,
        content=req.content,
        command=req.command,
        command_output=req.command_output,
        command_status=req.command_status,
        ai_explanation=req.ai_explanation,
        ai_suggested_command=req.ai_suggested_command,
        message_type=req.message_type,
        extra_data=req.extra_data,
        timestamp=datetime.now(),
    )
    db.add(message)
    
    # 更新会话统计
    session.message_count = next_seq
    if req.command_status == "executed":
        session.command_count = (session.command_count or 0) + 1
    session.updated_at = datetime.now()
    
    # 自动生成标题（取第一条用户消息）
    if next_seq == 1 and req.role == "user" and not session.title:
        session.title = req.content[:100]
    
    await db.commit()
    await db.refresh(message)
    return message


@router.post("/sessions/{session_id}/messages/batch")
async def add_messages_batch(
    session_id: str,
    messages: List[AddMessageRequest],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量添加消息（用于前端定期同步）"""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id)
        .where(ChatSession.user_id == current_user.id)
    )
    session = result.scalars().one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    seq_result = await db.execute(
        select(func.coalesce(func.max(ChatMessage.sequence), 0))
        .where(ChatMessage.session_id == session_id)
    )
    next_seq = (seq_result.scalar() or 0) + 1
    
    command_count = 0
    for i, msg_req in enumerate(messages):
        msg = ChatMessage(
            id=str(uuid.uuid4()),
            session_id=session_id,
            sequence=next_seq + i,
            role=msg_req.role,
            content=msg_req.content,
            command=msg_req.command,
            command_output=msg_req.command_output,
            command_status=msg_req.command_status,
            ai_explanation=msg_req.ai_explanation,
            ai_suggested_command=msg_req.ai_suggested_command,
            message_type=msg_req.message_type,
            extra_data=msg_req.extra_data,
            timestamp=datetime.now(),
        )
        db.add(msg)
        if msg_req.command_status == "executed":
            command_count += 1
    
    session.message_count = next_seq + len(messages) - 1
    session.command_count = (session.command_count or 0) + command_count
    session.updated_at = datetime.now()
    
    await db.commit()
    return {"message": f"Added {len(messages)} messages", "count": len(messages)}
