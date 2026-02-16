from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from app.config import settings
import uuid

# 创建异步引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True
)

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# 创建基类
Base = declarative_base()


# 依赖项：获取数据库会话
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# 初始化数据库
async def init_db():
    # 导入所有模型，确保它们被注册到Base.metadata
    from app.models.user import User
    from app.models.connection import Connection
    from app.models.session_log import SessionLog
    from app.models.llm_config import LLMConfig, LLMProvider
    from app.models.audit_log import AuditLog
    from app.models.chat_session import ChatSession, ChatMessage
    from passlib.context import CryptContext
    from sqlalchemy import text  # 移到这里避免作用域问题
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # 创建默认管理员
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        def _create_default_admin(sync_conn):
            # 检查是否已有管理员
            try:
                result = sync_conn.execute(text("SELECT COUNT(*) FROM users WHERE role = 'admin'"))
                count = result.scalar()
                if count == 0:
                    # 创建默认管理员
                    admin_username = settings.DEFAULT_ADMIN_USERNAME
                    admin_password = pwd_context.hash(settings.DEFAULT_ADMIN_PASSWORD)
                    admin_email = settings.DEFAULT_ADMIN_EMAIL
                    
                    sync_conn.execute(text(
                        "INSERT INTO users (id, username, email, password, role, is_active, created_at, updated_at) "
                        "VALUES (:id, :username, :email, :password, :role, 1, datetime('now'), datetime('now'))"
                    ), {
                        "id": "00000000-0000-0000-0000-000000000001",
                        "username": admin_username,
                        "email": admin_email,
                        "password": admin_password,
                        "role": "admin"
                    })
                    print(f"默认管理员已创建: {admin_username} / {settings.DEFAULT_ADMIN_PASSWORD}")
            except Exception as e:
                print(f"检查/创建默认管理员时出错: {e}")
        
        await conn.run_sync(_create_default_admin)
        
        # Ensure new columns exist in session_logs for existing DBs (SQLite)
        def _ensure_sessionlog_columns(sync_conn):
            try:
                res = sync_conn.execute(text("PRAGMA table_info('session_logs')"))
                existing = [row[1] for row in res.fetchall()]
            except Exception:
                existing = []

            expected = {
                'type': 'VARCHAR(16)',
                'content': 'TEXT',
                'role': 'VARCHAR(16)',
                'host': 'VARCHAR(256)',
                'username': 'VARCHAR(128)',
                'start_time': 'DATETIME',
                'end_time': 'DATETIME',
                'duration': 'INTEGER',
                'commands_executed': 'TEXT',
                'error_message': 'TEXT'
            }

            for col, coltype in expected.items():
                if col not in existing:
                    try:
                        sync_conn.execute(text(f'ALTER TABLE session_logs ADD COLUMN {col} {coltype}'))
                    except Exception:
                        # ignore failures; table may not exist yet or DB engine differs
                        pass
            # If content column exists but has NOT NULL constraint, make it nullable
            try:
                # Check if content is NOT NULL and fix it
                res = sync_conn.execute(text("PRAGMA table_info('session_logs')"))
                columns = {row[1]: row for row in res.fetchall()}
                if 'content' in columns and columns['content'][3] == 1:  # 3 = notnull
                    # SQLite doesn't support dropping NOT NULL directly, we need a workaround
                    # For SQLite, we need to recreate the table or skip this
                    pass
            except Exception:
                pass

        await conn.run_sync(_ensure_sessionlog_columns)
        
        # 创建默认AI提供商
        def _create_default_providers(sync_conn):
            try:
                result = sync_conn.execute(text("SELECT COUNT(*) FROM llm_providers WHERE is_default = 1"))
                count = result.scalar()
                if count == 0:
                    default_providers = [
                        ("DeepSeek", "deepseek", "deepseek-chat", "https://api.deepseek.com/v1"),
                        ("OpenAI", "openai", "gpt-4o", "https://api.openai.com/v1"),
                        ("Ollama", "ollama", "llama2", "http://localhost:11434"),
                    ]
                    for name, code, default_model, default_url in default_providers:
                        sync_conn.execute(text(
                            "INSERT INTO llm_providers (id, user_id, name, code, default_model, default_url, is_default, created_at) "
                            "VALUES (:id, :user_id, :name, :code, :default_model, :default_url, 1, datetime('now'))"
                        ), {
                            "id": str(uuid.uuid4()),
                            "user_id": "00000000-0000-0000-0000-000000000001",
                            "name": name,
                            "code": code,
                            "default_model": default_model,
                            "default_url": default_url
                        })
                    print(f"默认AI提供商已创建: {len(default_providers)} 个")
            except Exception as e:
                print(f"创建默认AI提供商时出错: {e}")
        
        await conn.run_sync(_create_default_providers)
