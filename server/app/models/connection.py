from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
import uuid
from app.database import Base


class Connection(Base):
    __tablename__ = "connections"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    group_name = Column(String(64), default="default")
    host = Column(String(256), nullable=False)
    port = Column(Integer, default=22)
    protocol = Column(String(16), default="ssh")  # ssh / sftp
    auth_method = Column(String(16), default="password")  # password / privatekey
    username = Column(String(64), nullable=False)
    password = Column(Text, nullable=True)  # 加密存储
    private_key = Column(Text, nullable=True)  # 加密存储
    passphrase = Column(Text, nullable=True)  # 加密存储
    description = Column(Text, nullable=True)
    tags = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
