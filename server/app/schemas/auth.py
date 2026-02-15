from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    """登录请求模型"""
    username: str
    password: str


class RegisterRequest(BaseModel):
    """注册请求模型"""
    username: str
    email: str
    password: str


class Token(BaseModel):
    """令牌模型"""
    access_token: str
    token_type: str
    user: Optional[dict] = None


class TokenData(BaseModel):
    """令牌数据模型"""
    username: Optional[str] = None
