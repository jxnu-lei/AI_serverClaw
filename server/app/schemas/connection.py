from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional


class ConnectionCreate(BaseModel):
    name: str = Field(..., max_length=128)
    group_name: str = Field(default="default", max_length=64)
    host: str = Field(..., max_length=256)
    port: int = Field(default=22, ge=1, le=65535)
    protocol: str = Field(default="ssh", pattern="^(ssh|sftp)$")
    auth_method: str = Field(default="password", pattern="^(password|privatekey)$")
    username: str = Field(..., max_length=64)
    password: Optional[str] = None
    private_key: Optional[str] = None
    passphrase: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None


class ConnectionOut(BaseModel):
    id: UUID
    name: str
    group_name: str
    host: str
    port: int
    protocol: str
    auth_method: str
    username: str
    description: Optional[str] = None
    tags: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConnectionUpdate(BaseModel):
    name: Optional[str] = None
    group_name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = Field(None, ge=1, le=65535)
    protocol: Optional[str] = None
    auth_method: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    private_key: Optional[str] = None
    passphrase: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None


class ConnectionTest(BaseModel):
    """连接测试请求模型"""
    host: str
    port: int = Field(default=22, ge=1, le=65535)
    username: str
    password: Optional[str] = None
    private_key: Optional[str] = None
    auth_method: str = Field(default="password", pattern="^(password|privatekey)$")


class ConnectionTestResponse(BaseModel):
    """连接测试响应模型"""
    status: str
    message: str
    host: Optional[str] = None


# 别名，保持向后兼容
Connection = ConnectionOut
ConnectionSchema = ConnectionOut
