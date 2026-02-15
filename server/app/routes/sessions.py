from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import datetime

from app.database import get_db
from app.models.user import User
from app.models.session_log import SessionLog
from app.schemas.session import SessionLog as SessionLogSchema
from app.routes.auth import get_current_active_user

router = APIRouter()


@router.get("", response_model=List[SessionLogSchema])
async def get_sessions(
    skip: int = 0,
    limit: int = 100,
    start_date: str = None,
    end_date: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取用户的会话日志列表"""
    query = select(SessionLog).where(SessionLog.user_id == current_user.id)
    
    # 日期过滤
    if start_date:
        query = query.where(SessionLog.start_time >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.where(SessionLog.end_time <= datetime.fromisoformat(end_date))
    
    # 排序和分页
    query = query.order_by(SessionLog.start_time.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    sessions = result.scalars().all()
    
    return [
        SessionLogSchema(
            id=str(session.id),
            connection_id=str(session.connection_id),
            host=session.host,
            username=session.username,
            start_time=session.start_time,
            end_time=session.end_time,
            duration=session.duration,
            commands_executed=session.commands_executed,
            error_message=session.error_message
        )
        for session in sessions
    ]


@router.get("/{session_id}", response_model=SessionLogSchema)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取会话详情"""
    result = await db.execute(
        select(SessionLog)
        .where(SessionLog.id == session_id)
        .where(SessionLog.user_id == current_user.id)
    )
    session = result.scalars().one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    return SessionLogSchema(
        id=str(session.id),
        connection_id=str(session.connection_id),
        host=session.host,
        username=session.username,
        start_time=session.start_time,
        end_time=session.end_time,
        duration=session.duration,
        commands_executed=session.commands_executed,
        error_message=session.error_message
    )


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """删除会话日志"""
    result = await db.execute(
        select(SessionLog)
        .where(SessionLog.id == session_id)
        .where(SessionLog.user_id == current_user.id)
    )
    session = result.scalars().one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    await db.delete(session)
    await db.commit()
    
    return {"message": "Session deleted successfully"}


@router.delete("/bulk/delete")
async def delete_sessions(
    session_ids: List[str],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """批量删除会话日志"""
    # 验证所有会话ID都属于当前用户
    result = await db.execute(
        select(SessionLog)
        .where(SessionLog.id.in_(session_ids))
        .where(SessionLog.user_id == current_user.id)
    )
    sessions = result.scalars().all()
    
    if len(sessions) != len(session_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Some session IDs are invalid or do not belong to you"
        )
    
    # 批量删除
    for session in sessions:
        await db.delete(session)
    
    await db.commit()
    
    return {"message": f"Deleted {len(sessions)} sessions successfully"}


@router.get("/stats/summary")
async def get_session_stats(
    start_date: str = None,
    end_date: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取会话统计摘要"""
    query = select(SessionLog).where(SessionLog.user_id == current_user.id)
    
    # 日期过滤
    if start_date:
        query = query.where(SessionLog.start_time >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.where(SessionLog.end_time <= datetime.fromisoformat(end_date))
    
    result = await db.execute(query)
    sessions = result.scalars().all()
    
    # 计算统计数据
    total_sessions = len(sessions)
    total_duration = sum(session.duration or 0 for session in sessions)
    successful_sessions = sum(1 for session in sessions if not session.error_message)
    failed_sessions = total_sessions - successful_sessions
    
    # 按主机分组
    host_stats = {}
    for session in sessions:
        if session.host not in host_stats:
            host_stats[session.host] = {
                "count": 0,
                "duration": 0,
                "successful": 0,
                "failed": 0
            }
        host_stats[session.host]["count"] += 1
        host_stats[session.host]["duration"] += session.duration or 0
        if session.error_message:
            host_stats[session.host]["failed"] += 1
        else:
            host_stats[session.host]["successful"] += 1
    
    return {
        "total_sessions": total_sessions,
        "total_duration": total_duration,
        "average_duration": total_duration / total_sessions if total_sessions > 0 else 0,
        "successful_sessions": successful_sessions,
        "failed_sessions": failed_sessions,
        "success_rate": successful_sessions / total_sessions * 100 if total_sessions > 0 else 0,
        "host_stats": host_stats
    }
