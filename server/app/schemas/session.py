from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class SessionLog(BaseModel):
    """会话日志模型"""
    id: str
    connection_id: str
    host: str
    username: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[int] = None  # 持续时间（秒）
    commands_executed: Optional[List[str]] = []
    error_message: Optional[str] = None


class SessionCreate(BaseModel):
    """创建会话模型"""
    connection_id: str


class SessionStats(BaseModel):
    """会话统计模型"""
    total_sessions: int
    total_duration: int
    average_duration: float
    successful_sessions: int
    failed_sessions: int
    success_rate: float
    host_stats: dict
