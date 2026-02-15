from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import asyncssh

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
    
    # 创建新连接
    # 记录请求上下文，便于排查
    try:
        payload: dict[str, Any] = {
            "name": connection_create.name,
            "host": connection_create.host,
            "port": int(connection_create.port),
            "username": connection_create.username,
            "password": connection_create.password,
            "private_key": connection_create.private_key,
            "auth_method": connection_create.auth_method,
            "description": connection_create.description,
            "tags": connection_create.tags,
            "user_id": current_user.id
        }
    except Exception as e:
        logger.exception("Invalid connection payload")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid connection payload")

    # tags 可能为列表，数据库模型为 Text，转为逗号分隔字符串
    tags_val = payload.get("tags")
    if isinstance(tags_val, (list, tuple)):
        try:
            payload["tags"] = ",".join([str(t) for t in tags_val])
        except Exception:
            payload["tags"] = str(tags_val)

    try:
        # logger.debug('Creating connection for user %s', current_user.id)

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
        tb = traceback.format_exc()
        logger.exception("Error creating connection: %s", e)
        # 额外写入文件，便于在无控制台输出时排查
        try:
            from pathlib import Path
            root = Path(__file__).resolve().parents[3]
            log_path = root / 'create_connection_error.log'
            with open(str(log_path), 'a', encoding='utf-8') as f:
                f.write(f"--- {__import__('datetime').datetime.utcnow().isoformat()} UTC ---\n")
                f.write(tb + '\n')
        except Exception:
            pass
        # 返回更明确的错误信息（避免泄露敏感信息）
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create connection")
    
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
    
    # 更新连接信息
    update_data = connection_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(connection, field, value)
    
    await db.commit()
    await db.refresh(connection)
    
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
    
    await db.delete(connection)
    await db.commit()
    
    return {"message": "Connection deleted successfully"}


@router.post("/test", response_model=ConnectionTestResponse)
async def test_connection(
    connection_test: ConnectionTest,
    current_user: User = Depends(get_current_active_user)
):
    """测试服务器连接"""
    try:
        # 测试SSH连接
        async with asyncssh.connect(
            host=connection_test.host,
            port=connection_test.port,
            username=connection_test.username,
            password=connection_test.password if connection_test.auth_method == "password" else None,
            client_keys=None if connection_test.auth_method == "password" or not connection_test.private_key else [connection_test.private_key],
            known_hosts=None,  # 不验证主机密钥（仅用于测试）
            timeout=10
        ) as conn:
            # 连接成功
            return ConnectionTestResponse(
                status="success",
                message="连接测试成功",
                host=connection_test.host
            )
    except asyncssh.ConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"连接失败: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"测试失败: {str(e)}"
        )
