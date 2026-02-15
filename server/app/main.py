import sys
import os

# 设置系统默认编码为 UTF-8
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# 删除 .env 文件，避免 Starlette 尝试读取它，从而避免 UnicodeDecodeError 错误
if os.path.exists('.env'):
    os.remove('.env')

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from contextlib import asynccontextmanager

from app.database import engine, Base, init_db
from app.config import settings

# 导入路由
from app.routes import auth, connections, llm, sessions, users
from app.routes import chat_history
from app.ws import terminal

# 创建限流器
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：初始化数据库
    await init_db()
    yield
    # 关闭：清理资源
    await engine.dispose()


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

# 配置中间件
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(users.router, prefix="/api/admin", tags=["用户管理"])
app.include_router(connections.router, prefix="/api/connections", tags=["连接管理"])
app.include_router(llm.router, prefix="/api/llm", tags=["LLM"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["会话"])
app.include_router(chat_history.router, prefix="/api", tags=["对话历史"])
app.include_router(terminal.router, prefix="/ws", tags=["终端"])


# 根路径
@app.get("/")
async def root():
    return {
        "message": "Welcome to AI Terminal API",
        "version": settings.VERSION,
        "docs": "/docs"
    }


# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True
    )
