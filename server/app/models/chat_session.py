"""
AI对话会话模型
一个 chat_session 对应一次完整的AI交互会话（从开启到结束/断开）
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database import Base


class ChatSession(Base):
    """AI对话会话"""
    __tablename__ = "chat_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    connection_id = Column(String(36), ForeignKey("connections.id"), nullable=True)
    
    # 会话基本信息
    title = Column(String(255), default="")          # 会话标题（可由AI自动生成或取第一条消息）
    host = Column(String(255), default="")            # 连接的服务器
    username = Column(String(100), default="")        # SSH用户名
    
    # 统计信息
    message_count = Column(Integer, default=0)        # 消息总数
    command_count = Column(Integer, default=0)         # 执行的命令数
    status = Column(String(20), default="active")     # active / completed / error
    
    # 时间
    start_time = Column(DateTime, default=datetime.now)
    end_time = Column(DateTime, nullable=True)
    duration = Column(Integer, nullable=True)          # 秒
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关系
    messages = relationship("ChatMessage", back_populates="session", 
                          order_by="ChatMessage.sequence", cascade="all, delete-orphan")


class ChatMessage(Base):
    """对话消息记录"""
    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("chat_sessions.id"), nullable=False, index=True)
    
    # 消息内容
    sequence = Column(Integer, nullable=False)         # 消息序号（保证顺序）
    role = Column(String(20), nullable=False)          # user / assistant / system / command / output
    content = Column(Text, default="")                 # 消息内容
    
    # 命令相关（role=command 或 role=output 时使用）
    command = Column(Text, nullable=True)              # 执行的命令
    command_output = Column(Text, nullable=True)       # 命令输出
    command_status = Column(String(20), nullable=True) # executed / rejected / modified / error
    exit_code = Column(Integer, nullable=True)         # 命令退出码（如果能获取）
    
    # AI相关（role=assistant 时使用）
    ai_explanation = Column(Text, nullable=True)       # AI的解释文本
    ai_suggested_command = Column(Text, nullable=True) # AI建议的命令
    
    # 元数据
    message_type = Column(String(30), default="text")  # text / command_suggest / command_execute / 
                                                        # command_reject / command_modify / output / error
    extra_data = Column(JSON, nullable=True)             # 额外元数据
    
    timestamp = Column(DateTime, default=datetime.now)
    
    # 关系
    session = relationship("ChatSession", back_populates="messages")
