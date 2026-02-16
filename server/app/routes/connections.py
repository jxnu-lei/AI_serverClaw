from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import asyncssh
import asyncio

from app.database import get_db
from app.models.connection import Connection
from app.schemas.connection import (
    Connection as ConnectionSchema,
    ConnectionCreate,
    ConnectionUpdate,
    ConnectionTest,
    ConnectionTestResponse
)
from app.routes.auth import get_current_active_user
from app.models.user import User

router = APIRouter()


@router.get("", response_model=List[ConnectionSchema])
async def get_connections(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取用户的服务器连接列表"""
    # 安全限制：最大返回100条
    limit = min(limit, 100)
    skip = max(skip, 0)
    
    result = await db.execute(
        select(Connection)
        .where(Connection.user_id == current_user.id)
        .offset(skip)
        .limit(limit)
    )
    connections = result.scalars().all()

    return [
        ConnectionSchema(
            id=str(conn.id),
            name=conn.name,
            host=conn.host,
            port=conn.port,
            username=conn.username,
            auth_method=conn.auth_method or "password",
            protocol=conn.protocol or "ssh",
            group_name=conn.group_name or "default",
            description=conn.description,
            tags=conn.tags,
            created_at=conn.created_at,
            updated_at=conn.updated_at
        )
        for conn in connections
    ]


@router.get("/{connection_id}", response_model=ConnectionSchema)
async def get_connection(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取连接详情"""
    # 基本格式校验
    if not connection_id or len(connection_id) > 36:
        raise HTTPException(status_code=400, detail="Invalid connection_id")
    
    result = await db.execute(
        select(Connection)
        .where(Connection.id == connection_id)
        .where(Connection.user_id == current_user.id)
    )
    connection = result.scalars().one_or_none()

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found"
        )

    return ConnectionSchema(
        id=str(connection.id),
        name=connection.name,
        host=connection.host,
        port=connection.port,
        username=connection.username,
        auth_method=connection.auth_method or "password",
        protocol=connection.protocol or "ssh",
        group_name=connection.group_name or "default",
        description=connection.description,
        tags=connection.tags,
        created_at=connection.created_at,
        updated_at=connection.updated_at
    )


from fastapi.responses import JSONResponse
import logging
import traceback
from typing import Any

logger = logging.getLogger(__name__)

@router.post("", status_code=201)
async def create_connection(
    connection_create: ConnectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """创建新的服务器连接"""
    # 检查用户连接数量限制（防止滥用）
    count_result = await db.execute(
        select(Connection)
        .where(Connection.user_id == current_user.id)
    )
    existing_count = len(count_result.scalars().all())
    if existing_count >= 50:  # 每用户最多50个连接
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum number of connections reached (50)"
        )
    
    # 检查连接名称是否已存在
    result = await db.execute(
        select(Connection)
        .where(Connection.name == connection_create.name)
        .where(Connection.user_id == current_user.id)
    )
    if result.scalars().one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connection name already exists"
        )

    try:
        payload: dict[str, Any] = {
            "name": connection_create.name.strip(),
            "host": connection_create.host.strip(),
            "port": int(connection_create.port),
            "username": connection_create.username.strip(),
            "password": connection_create.password,
            "private_key": connection_create.private_key,
            "auth_method": connection_create.auth_method,
            "description": connection_create.description,
            "tags": connection_create.tags,
            "user_id": current_user.id
        }
    except Exception:
        logger.exception("Invalid connection payload")
        raise HTTPException(status_code=400, detail="Invalid connection payload")

    # 端口范围校验
    if not (1 <= payload["port"] <= 65535):
        raise HTTPException(status_code=400, detail="Port must be between 1 and 65535")

    # tags处理
    tags_val = payload.get("tags")
    if isinstance(tags_val, (list, tuple)):
        try:
            payload["tags"] = ",".join([str(t).strip() for t in tags_val if str(t).strip()])
        except Exception:
            payload["tags"] = ""

    try:
        new_connection = Connection(
            name=payload["name"],
            host=payload["host"],
            port=payload["port"],
            username=payload["username"],
            password=payload.get("password"),
            private_key=payload.get("private_key"),
            auth_method=payload.get("auth_method"),
            description=payload.get("description"),
            tags=payload.get("tags"),
            user_id=payload.get("user_id")
        )
        db.add(new_connection)
        await db.commit()
        await db.refresh(new_connection)
    except Exception as e:
        logger.exception("Error creating connection: %s", e)
        try:
            await db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to create connection")

    return JSONResponse({
        "id": str(new_connection.id),
        "name": new_connection.name,
        "host": new_connection.host,
        "port": new_connection.port,
        "username": new_connection.username,
        "auth_method": new_connection.auth_method,
        "description": new_connection.description,
        "tags": new_connection.tags,
        "created_at": new_connection.created_at.isoformat() if new_connection.created_at else None,
        "updated_at": new_connection.updated_at.isoformat() if new_connection.updated_at else None
    })


@router.put("/{connection_id}", response_model=ConnectionSchema)
async def update_connection(
    connection_id: str,
    connection_update: ConnectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """更新服务器连接"""
    if not connection_id or len(connection_id) > 36:
        raise HTTPException(status_code=400, detail="Invalid connection_id")
    
    result = await db.execute(
        select(Connection)
        .where(Connection.id == connection_id)
        .where(Connection.user_id == current_user.id)
    )
    connection = result.scalars().one_or_none()

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found"
        )

    update_data = connection_update.model_dump(exclude_unset=True)
    
    # 安全过滤：不允许通过update修改user_id
    update_data.pop('user_id', None)
    
    # 端口校验
    if 'port' in update_data:
        port = int(update_data['port'])
        if not (1 <= port <= 65535):
            raise HTTPException(status_code=400, detail="Port must be between 1 and 65535")
    
    for field, value in update_data.items():
        if hasattr(connection, field):
            setattr(connection, field, value)

    try:
        await db.commit()
        await db.refresh(connection)
    except Exception as e:
        logger.exception("Error updating connection: %s", e)
        try:
            await db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to update connection")

    return ConnectionSchema(
        id=str(connection.id),
        name=connection.name,
        host=connection.host,
        port=connection.port,
        username=connection.username,
        auth_method=connection.auth_method or "password",
        protocol=connection.protocol or "ssh",
        group_name=connection.group_name or "default",
        description=connection.description,
        tags=connection.tags,
        created_at=connection.created_at,
        updated_at=connection.updated_at
    )


@router.delete("/{connection_id}")
async def delete_connection(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """删除服务器连接"""
    if not connection_id or len(connection_id) > 36:
        raise HTTPException(status_code=400, detail="Invalid connection_id")
    
    result = await db.execute(
        select(Connection)
        .where(Connection.id == connection_id)
        .where(Connection.user_id == current_user.id)
    )
    connection = result.scalars().one_or_none()

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found"
        )

    try:
        await db.delete(connection)
        await db.commit()
    except Exception as e:
        logger.exception("Error deleting connection: %s", e)
        try:
            await db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to delete connection")

    return {"message": "Connection deleted successfully"}


@router.post("/test", response_model=ConnectionTestResponse)
async def test_connection(
    connection_test: ConnectionTest,
    current_user: User = Depends(get_current_active_user)
):
    """测试服务器连接"""
    import tempfile
    import os
    import stat
    
    key_file = None
    
    try:
        ssh_options = {
            "host": connection_test.host,
            "port": connection_test.port or 22,
            "username": connection_test.username,
            "known_hosts": None,
        }
        
        if connection_test.auth_method == "password":
            if not connection_test.password:
                raise HTTPException(status_code=400, detail="密码不能为空")
            ssh_options["password"] = connection_test.password
        elif connection_test.auth_method == "private_key":
            if not connection_test.private_key:
                raise HTTPException(status_code=400, detail="私钥不能为空")
            # 创建临时私钥文件
            with tempfile.NamedTemporaryFile(
                mode='w', delete=False, suffix='.key', prefix='ssh_test_'
            ) as f:
                f.write(connection_test.private_key)
                key_file = f.name
            os.chmod(key_file, stat.S_IRUSR)
            ssh_options["client_keys"] = [key_file]
            if hasattr(connection_test, 'passphrase') and connection_test.passphrase:
                ssh_options["passphrase"] = connection_test.passphrase
        else:
            # 默认密码认证
            if connection_test.password:
                ssh_options["password"] = connection_test.password
            else:
                raise HTTPException(status_code=400, detail="请提供密码或私钥")
        
        # 测试连接（注意：必须在key_file删除之前完成）
        async with asyncssh.connect(**ssh_options) as conn:
            return ConnectionTestResponse(
                status="success",
                message="连接测试成功",
                host=connection_test.host
            )
    
    except asyncssh.PermissionDenied:
        raise HTTPException(status_code=400, detail="认证失败：用户名或密码/密钥错误")
    except asyncssh.DisconnectError as e:
        raise HTTPException(status_code=400, detail=f"SSH连接被拒绝: {str(e)}")
    except asyncio.TimeoutError:
        raise HTTPException(status_code=400, detail="连接超时（10秒）")
    except OSError as e:
        raise HTTPException(status_code=400, detail=f"网络错误: 无法连接到 {connection_test.host}:{connection_test.port} ({str(e)})")
    except Exception as e:
        logger.warning(f"Connection test failed: {type(e).__name__}: {e}")
        raise HTTPException(status_code=400, detail=f"测试失败: {str(e)}")
    finally:
        # 确保清理临时密钥文件
        if key_file:
            try:
                os.unlink(key_file)
            except OSError:
                pass