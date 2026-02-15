from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer
from sqlalchemy.sql import func
import uuid
from app.database import Base


class SessionLog(Base):
    __tablename__ = "session_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    connection_id = Column(String(36), ForeignKey("connections.id", ondelete="CASCADE"), nullable=False, index=True)
    # session type: e.g. 'terminal', 'ai_chat'
    type = Column(String(16), nullable=False, default='terminal')
    # content for AI chat sessions (optional for terminal sessions)
    content = Column(Text, nullable=True)
    # role for AI chat: 'user', 'assistant', 'system'
    role = Column(String(16), nullable=True)
    # session fields for SSH terminal sessions
    host = Column(String(256), nullable=True)
    username = Column(String(128), nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    duration = Column(Integer, nullable=True)
    commands_executed = Column(Text, nullable=True)  # JSON/text list of commands
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
