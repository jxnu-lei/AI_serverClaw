"""
WebSocket 终端处理模块（增强版 v4）
关键改进：交互式输入不中断监视，完整输出收集后才通知完成
"""
import asyncio
import json
import re
import uuid
import time
from typing import Dict, Optional
from datetime import datetime
from collections import OrderedDict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import asyncssh

from app.database import get_db
from app.models.user import User
from app.models.connection import Connection
from app.models.session_log import SessionLog
from app.config import settings
from jose import jwt, JWTError

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_CONNECTIONS = 100

class ConnectionPool:
    """线程安全的连接池，带最大连接数限制"""
    
    def __init__(self, max_size: int = MAX_CONNECTIONS):
        self._pool: OrderedDict[str, dict] = OrderedDict()
        self._lock = asyncio.Lock()
        self._max_size = max_size
    
    async def add(self, client_id: str, info: dict):
        """添加连接，如果超过上限则踢掉最老的连接"""
        async with self._lock:
            if len(self._pool) >= self._max_size:
                # 踢掉最老的连接
                oldest_id, oldest = self._pool.popitem(last=False)
                await self._cleanup_single(oldest_id, oldest)
                logger.warning(f"Connection pool full, removed oldest: {oldest_id}")
            self._pool[client_id] = info
    
    async def remove(self, client_id: str) -> Optional[dict]:
        """移除连接并返回连接信息"""
        async with self._lock:
            return self._pool.pop(client_id, None)
    
    def get(self, client_id: str) -> Optional[dict]:
        """获取连接信息"""
        return self._pool.get(client_id)
    
    def __contains__(self, client_id: str) -> bool:
        """检查连接是否存在"""
        return client_id in self._pool
    
    async def _cleanup_single(self, cid: str, info: dict):
        """清理单个连接"""
        try:
            if info.get("ssh_process"):
                info["ssh_process"].close()
            if info.get("ssh_conn"):
                info["ssh_conn"].close()
        except Exception as e:
            logger.warning(f"Cleanup error for {cid}: {e}")

# 使用线程安全的连接池替换全局字典
active_connections = ConnectionPool()


# ==================== 交互式程序检测 ====================

PAGER_PATTERNS = [
    re.compile(r'lines\s+\d+-\d+', re.IGNORECASE),
    re.compile(r'\(END\)', re.IGNORECASE),
    re.compile(r'--More--', re.IGNORECASE),
    re.compile(r'byte\s+\d+', re.IGNORECASE),
    re.compile(r'^\s*:\s*$', re.MULTILINE),
]

INTERACTIVE_PATTERNS = [
    re.compile(r'>>>\s*$'),
    re.compile(r'\.\.\.\s*$'),
    re.compile(r'mysql>\s*$', re.IGNORECASE),
    re.compile(r'postgres[=#]>\s*$', re.IGNORECASE),
    re.compile(r'redis\s*[\d.]*>\s*$', re.IGNORECASE),
    re.compile(r'\(gdb\)\s*$'),
    re.compile(r'irb\(\w+\):\d+:\d+>\s*$'),
    re.compile(r'node>\s*$'),
]

CONFIRM_PATTERNS = [
    re.compile(r'\[Y/n\]\s*$', re.IGNORECASE),
    re.compile(r'\[y/N\]\s*$', re.IGNORECASE),
    re.compile(r'\(yes/no[/\w]*\)\s*[:\?]?\s*$', re.IGNORECASE),
    re.compile(r'password\s*:\s*$', re.IGNORECASE),
    re.compile(r'passphrase\s*:\s*$', re.IGNORECASE),
    re.compile(r'continue\s*\?\s*', re.IGNORECASE),
    re.compile(r'proceed\s*\?\s*', re.IGNORECASE),
    re.compile(r'Do you want to continue', re.IGNORECASE),
]


def detect_interactive_state(clean_text: str) -> Optional[str]:
    """检测输出末尾是否处于交互式等待"""
    if not clean_text.strip():
        return None

    lines = clean_text.strip().split('\n')
    last_lines = '\n'.join(lines[-3:])
    last_line = lines[-1].strip() if lines else ''

    for p in PAGER_PATTERNS:
        if p.search(last_line) or p.search(last_lines):
            return 'pager'

    for p in CONFIRM_PATTERNS:
        if p.search(last_line) or p.search(last_lines):
            return 'confirm'

    for p in INTERACTIVE_PATTERNS:
        if p.search(last_line):
            return 'interactive'

    return None


def get_interactive_hint(interactive_type: str) -> dict:
    hints = {
        'pager': {
            'message': '命令输出进入了分页模式（less/more），需要操作后才能继续',
            'actions': [
                {'label': '退出分页 (q)', 'data': 'q'},
                {'label': '下一页 (空格)', 'data': ' '},
                {'label': '到末尾 (G)', 'data': 'G'},
            ]
        },
        'interactive': {
            'message': '命令进入了交互式模式，需要操作后才能退出',
            'actions': [
                {'label': '退出 (exit)', 'data': 'exit\r'},
                {'label': '退出 (Ctrl+D)', 'data': '\x04'},
                {'label': '中断 (Ctrl+C)', 'data': '\x03'},
            ]
        },
        'confirm': {
            'message': '程序正在等待确认输入',
            'actions': [
                {'label': '确认 (Y)', 'data': 'Y\r'},
                {'label': '取消 (n)', 'data': 'n\r'},
                {'label': '中断 (Ctrl+C)', 'data': '\x03'},
            ]
        },
    }
    return hints.get(interactive_type, hints['interactive'])


def build_prompt_pattern(username: str) -> re.Pattern:
    escaped = re.escape(username)
    patterns = [
        rf'{escaped}@[^\s:]+:[^\$#\n]*[\$#]\s*$',
        rf'\[{escaped}@[^\]]+\][\$#]\s*$',
    ]
    combined = '|'.join(f'(?:{p})' for p in patterns)
    return re.compile(combined, re.MULTILINE)


def strip_ansi(text: str) -> str:
    """去除 ANSI 转义序列和控制字符"""
    ansi_re = re.compile(
        r'\x1b\[[0-9;]*[a-zA-Z]'
        r'|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)'
        r'|\x1b[()][AB012]'
        r'|\x1b[>=<]'
        r'|\r'
    )
    return ansi_re.sub('', text)


async def get_current_user_from_token(token: str, db: AsyncSession) -> Optional[User]:
    """从 token 获取当前用户"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            return None
        
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalars().one_or_none()
        return user
    except JWTError:
        return None
    except Exception:
        return None


@router.websocket("/terminal")
async def terminal_websocket(
    websocket: WebSocket,
    client_id: str = Query(...),
    token: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """WebSocket 终端连接处理"""
    
    # 验证用户
    user = await get_current_user_from_token(token, db)
    if not user:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    
    await websocket.accept()
    
    ssh_conn = None
    ssh_process = None
    connection_id = None
    session_log_id = None
    
    try:
        while True:
            # 接收消息
            try:
                message = await websocket.receive_text()
                data = json.loads(message)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "content": "Invalid JSON message"
                })
                continue
            
            msg_type = data.get("type")
            
            # ===== ping/pong 延迟检测 =====
            if msg_type == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": data.get("timestamp", int(time.time() * 1000))
                })
                continue
            
            if msg_type == "connect":
                # 建立 SSH 连接
                connection_id = data.get("connection_id")
                
                # 获取连接配置
                result = await db.execute(
                    select(Connection)
                    .where(Connection.id == connection_id)
                    .where(Connection.user_id == user.id)
                )
                conn = result.scalars().one_or_none()
                
                if not conn:
                    await websocket.send_json({
                        "type": "error",
                        "content": "Connection not found"
                    })
                    continue
                
                try:
                    # 建立 SSH 连接
                    ssh_options = {
                        "host": conn.host,
                        "port": conn.port or 22,
                        "username": conn.username,
                        "known_hosts": None,  # 开发环境，生产环境应该验证主机密钥
                    }
                    
                    key_file = None
                    try:
                        # 根据认证方式设置密码或密钥
                        if conn.auth_method == "password":
                            ssh_options["password"] = conn.password
                        elif conn.auth_method == "private_key":
                            # 使用私钥认证 - 安全处理
                            import tempfile
                            import os
                            import stat
                            
                            # 创建临时私钥文件，使用安全前缀
                            with tempfile.NamedTemporaryFile(
                                mode='w', delete=False, suffix='.key', prefix='ssh_'
                            ) as f:
                                f.write(conn.private_key)
                                key_file = f.name
                            
                            # 设置仅所有者可读权限
                            os.chmod(key_file, stat.S_IRUSR)
                            
                            ssh_options["client_keys"] = [key_file]
                            if conn.passphrase:
                                ssh_options["passphrase"] = conn.passphrase
                        
                        # 建立连接
                        ssh_conn = await asyncio.wait_for(
                            asyncssh.connect(**ssh_options),
                            timeout=10
                        )
                        
                        # 启动 shell
                        ssh_process = await ssh_conn.create_process(
                            term_type='xterm-256color',
                            term_size=(120, 30)  # 增大默认终端尺寸
                        )
                    finally:
                        # 无论成功失败都清理私钥文件
                        if key_file:
                            try:
                                os.unlink(key_file)
                            except OSError as e:
                                logger.warning(f"Failed to remove temp key file: {key_file}, error: {e}")
                    
                    # 记录会话日志（容错处理，避免 DB 错误导致整体回滚）
                    try:
                        session_log = SessionLog(
                            id=str(uuid.uuid4()),
                            user_id=user.id,
                            connection_id=conn.id,
                            type='terminal',
                            content='',  # Required by DB schema but not used for terminal sessions
                            host=conn.host,
                            username=conn.username,
                            start_time=datetime.now(),
                            commands_executed=''  # 使用字符串存储命令列表或空
                        )
                        db.add(session_log)
                        await db.commit()
                        session_log_id = session_log.id
                    except Exception as e:
                        # 记录错误并通知前端，但不要让整个 WebSocket 流程崩溃
                        try:
                            await db.rollback()
                        except Exception:
                            pass
                        session_log_id = None
                        # 记录详细异常到服务器日志以便排查
                        logger.exception("Failed to create session log")
                        await websocket.send_json({
                            "type": "error",
                            "content": f"Session log create failed: {str(e)}"
                        })
                    
                    # 存储连接信息
                    # 构建 prompt 检测正则
                    prompt_pattern = build_prompt_pattern(conn.username)
                    
                    await active_connections.add(client_id, {
                        "ssh_conn": ssh_conn,
                        "ssh_process": ssh_process,
                        "connection": conn,
                        "session_log_id": session_log_id,
                        "db": db,
                        "commands_log": [],
                        "prompt_pattern": prompt_pattern,
                        # 监视状态
                        "watching_command": False,
                        "command_output_buffer": "",
                        "last_output_time": 0.0,
                        "watch_start_time": 0.0,
                        "interactive_state": None,
                        "interactive_notified": False,  # 是否已通知过前端
                    })
                    
                    # 启动输出读取任务
                    asyncio.create_task(
                        read_ssh_output(websocket, ssh_process, client_id)
                    )
                    
                    await websocket.send_json({
                        "type": "connected",
                        "content": f"Connected to {conn.host} as {conn.username}"
                    })
                    
                except asyncio.TimeoutError:
                    await websocket.send_json({
                        "type": "error",
                        "content": "Connection timeout"
                    })
                except asyncssh.Error as e:
                    await websocket.send_json({
                        "type": "error",
                        "content": f"SSH Error: {str(e)}"
                    })
                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "content": f"Connection failed: {str(e)}"
                    })
            
            elif msg_type == "data" or msg_type == "input":
                # 统一处理：所有输入都直接写入 SSH stdin
                ci = active_connections.get(client_id)
                if ci:
                    proc = ci["ssh_process"]
                    data_content = data.get("data", "") or data.get("data", "")
                    proc.stdin.write(data_content)
                    
                    # 如果在监视状态，收到输入说明用户在交互
                    # 重置交互通知标记，后续输出可能变化
                    if ci.get("watching_command"):
                        ci["interactive_notified"] = False
                        ci["interactive_state"] = None
                        ci["last_output_time"] = time.time()
                    
                    # 记录命令
                    if '\r' in data_content or '\n' in data_content:
                        cmd = data_content.strip().replace('\r', '').replace('\n', '')
                        if cmd:
                            ci["commands_log"].append({
                                "command": cmd,
                                "timestamp": datetime.now().isoformat()
                            })
            
            elif msg_type == "watch_command":
                ci = active_connections.get(client_id)
                if ci:
                    ci["watching_command"] = True
                    ci["command_output_buffer"] = ""
                    ci["last_output_time"] = time.time()
                    ci["watch_start_time"] = time.time()
                    ci["interactive_state"] = None
                    ci["interactive_notified"] = False

            elif msg_type == "stop_watch":
                ci = active_connections.get(client_id)
                if ci:
                    ci["watching_command"] = False
                    ci["command_output_buffer"] = ""
                    ci["interactive_state"] = None
                    ci["interactive_notified"] = False
            
            elif msg_type == "resize":
                # 调整终端大小
                ci = active_connections.get(client_id)
                if ci:
                    ssh_process = ci["ssh_process"]
                    cols = data.get("cols", 120)
                    rows = data.get("rows", 30)
                    try:
                        ssh_process.change_terminal_size(cols, rows)
                    except AttributeError:
                        # 某些版本的 asyncssh 方法名不同
                        try:
                            if hasattr(ssh_process, 'terminal'):
                                ssh_process.terminal.change_size(cols, rows)
                        except Exception as e:
                            logger.warning(f"Resize error: {e}")
            
            elif msg_type == "disconnect":
                # 断开连接
                break
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # 清理资源
        await cleanup_connection(client_id, db)


async def read_ssh_output(
    websocket: WebSocket, ssh_process, client_id: str
):
    """
    读取 SSH 输出 + 三重完成检测
    """

    async def monitor():
        """后台监控：prompt检测 + 交互检测 + 超时"""
        PROMPT_IDLE = 3           # prompt检测需要空闲的秒数
        INTERACTIVE_IDLE = 3      # 交互检测需要空闲的秒数
        FORCE_IDLE = 20           # 强制超时空闲秒数
        FORCE_TOTAL = 120         # 强制超时总秒数

        while client_id in active_connections:
            await asyncio.sleep(1)

            ci = active_connections.get(client_id)
            if not ci or not ci.get("watching_command"):
                continue

            last_time = ci.get("last_output_time", 0)
            if last_time == 0:
                continue

            elapsed_idle = time.time() - last_time
            elapsed_total = time.time() - ci.get("watch_start_time", time.time())
            buf = ci.get("command_output_buffer", "")

            if not buf.strip():
                continue

            clean_buf = strip_ansi(buf)
            prompt_pattern = ci.get("prompt_pattern")

            # -------- 1. 检测 shell prompt（命令正常结束） --------
            if elapsed_idle >= PROMPT_IDLE and prompt_pattern:
                last_lines = clean_buf.strip().split('\n')[-3:]
                last_text = '\n'.join(last_lines)

                if prompt_pattern.search(last_text):
                    # 二次确认不是交互式
                    if not detect_interactive_state(clean_buf):
                        logger.info(f"[{client_id}] Command finished (prompt)")
                        ci["watching_command"] = False
                        ci["interactive_state"] = None
                        ci["interactive_notified"] = False

                        try:
                            await websocket.send_json({
                                "type": "command_finished",
                                "output": clean_buf,
                                "detection": "prompt"
                            })
                        except Exception as e:
                            logger.error(f"Send finished failed: {e}")

                        ci["command_output_buffer"] = ""
                        continue

            # -------- 2. 检测交互式程序（通知前端操作） --------
            if elapsed_idle >= INTERACTIVE_IDLE:
                itype = detect_interactive_state(clean_buf)

                if itype:
                    prev = ci.get("interactive_state")
                    ci["interactive_state"] = itype

                    # 只在状态变化时通知，或首次检测到时通知
                    if not ci.get("interactive_notified") or prev != itype:
                        ci["interactive_notified"] = True
                        logger.info(f"[{client_id}] Interactive: {itype}")

                        try:
                            await websocket.send_json({
                                "type": "interactive_detected",
                                "interactive_type": itype,
                                "output": clean_buf,
                                "hint": get_interactive_hint(itype)
                            })
                        except Exception as e:
                            logger.error(f"Send interactive failed: {e}")
                    continue
                else:
                    # 不再是交互式状态（用户可能已操作退出）
                    if ci.get("interactive_state"):
                        ci["interactive_state"] = None
                        ci["interactive_notified"] = False

            # -------- 3. 超时兜底 --------
            if elapsed_idle >= FORCE_IDLE and elapsed_total >= FORCE_TOTAL:
                logger.warning(f"[{client_id}] Force timeout idle={elapsed_idle:.0f}s total={elapsed_total:.0f}s")
                ci["watching_command"] = False
                ci["interactive_state"] = None
                ci["interactive_notified"] = False

                try:
                    await websocket.send_json({
                        "type": "command_finished",
                        "output": clean_buf,
                        "detection": "force_timeout"
                    })
                except Exception as e:
                    logger.warning(f"Send force_timeout failed: {e}")

                ci["command_output_buffer"] = ""

    task = asyncio.create_task(monitor())

    try:
        while True:
            try:
                output = await asyncio.wait_for(
                    ssh_process.stdout.read(4096), timeout=0.5
                )
                if output:
                    await websocket.send_json({"type": "output", "data": output})

                    ci = active_connections.get(client_id)
                    if ci and ci.get("watching_command"):
                        ci["command_output_buffer"] += output
                        ci["last_output_time"] = time.time()

                elif output == '':
                    # SSH 进程结束
                    ci = active_connections.get(client_id)
                    if ci and ci.get("watching_command"):
                        clean = strip_ansi(ci.get("command_output_buffer", ""))
                        ci["watching_command"] = False
                        try:
                            await websocket.send_json({
                                "type": "command_finished",
                                "output": clean,
                                "detection": "process_exit"
                            })
                        except Exception as e:
                            logger.warning(f"Send process_exit failed: {e}")

                    await websocket.send_json({
                        "type": "disconnected",
                        "content": "SSH session ended"
                    })
                    break

            except asyncio.TimeoutError:
                if client_id not in active_connections:
                    break
                continue
            except Exception:
                break
    except Exception as e:
        logger.error(f"SSH output error: {e}")
    finally:
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass


async def cleanup_connection(client_id: str, db: AsyncSession):
    """清理连接资源"""
    conn_info = await active_connections.remove(client_id)
    if not conn_info:
        return
    
    # 关闭 SSH 进程
    ssh_process = conn_info.get("ssh_process")
    if ssh_process:
        try:
            ssh_process.close()
            await ssh_process.wait_closed()
        except Exception as e:
            logger.warning(f"Close SSH process error: {e}")
    
    # 关闭 SSH 连接
    ssh_conn = conn_info.get("ssh_conn")
    if ssh_conn:
        try:
            ssh_conn.close()
            await ssh_conn.wait_closed()
        except Exception as e:
            logger.warning(f"Close SSH connection error: {e}")
    
    # 更新会话日志，包括执行的命令
    session_log_id = conn_info.get("session_log_id")
    db = conn_info.get("db")
    commands_log = conn_info.get("commands_log", [])
    
    if session_log_id and db:
        try:
            result = await db.execute(
                select(SessionLog).where(SessionLog.id == session_log_id)
            )
            session_log = result.scalars().one_or_none()
            if session_log:
                session_log.end_time = datetime.now()
                if session_log.start_time:
                    duration = (session_log.end_time - session_log.start_time).total_seconds()
                    session_log.duration = int(duration)
                # 保存命令日志
                if commands_log:
                    session_log.commands_executed = json.dumps(commands_log, ensure_ascii=False)
                await db.commit()
        except Exception as e:
            logger.error(f"Error updating session log: {e}")
    
    logger.info(f"Connection {client_id} cleaned up")
