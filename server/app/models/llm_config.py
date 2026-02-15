from sqlalchemy import Column, String, Float, Integer, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
import uuid
from app.database import Base


class LLMProvider(Base):
    """AI服务提供商表"""
    __tablename__ = "llm_providers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(64), nullable=False)  # 显示名称，如 "DeepSeek"
    code = Column(String(32), nullable=False)  # 代码，如 "deepseek"
    default_model = Column(String(64), nullable=True)  # 默认模型
    default_url = Column(String(256), nullable=True)  # 默认API URL
    is_default = Column(Boolean, default=False)  # 是否为系统默认
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class LLMConfig(Base):
    __tablename__ = "llm_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(64), nullable=False)
    provider = Column(String(32), default="deepseek")  # deepseek / openai / ollama
    api_url = Column(String(256), nullable=False)
    api_key = Column(Text, nullable=True)  # 加密存储
    model = Column(String(64), nullable=False)
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=2048)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
