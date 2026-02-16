"""
WebSocket 终端处理模块（v7 - 基于 v4 备份修复）
架构：read_ssh_output 内嵌 monitor（已验证能工作的架构）
改进：增加心跳、安全发送、详细状态提示、连接池清理
"""
import asyncio
import json
import re
import uuid
import time
from typing import Optional
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
MAX_OUTPUT_BUFFER = 50000


class ConnectionPool:
    def __init__(self, max_size: int = MAX_CONNECTIONS):
        self._pool: OrderedDict[str, dict] = OrderedDict()
        self._lock = asyncio.Lock()
        self._max_size = max_size

    async def add(self, client_id: str, info: dict):
        async with self._lock:
            if len(self._pool) >= self._max_size:
                oldest_id, oldest = self._pool.popitem(last=False)
                await self._cleanup_single(oldest_id, oldest)
                logger.warning(f"Pool full, removed: {oldest_id}")
            self._pool[client_id] = info

    async def remove(self, client_id: str) -> Optional[dict]:
        async with self._lock:
            return self._pool.pop(client_id, None)

    def get(self, client_id: str) -> Optional[dict]:
        return self._pool.get(client_id)

    def __contains__(self, client_id: str) -> bool:
        return client_id in self._pool

    async def _cleanup_single(self, cid: str, info: dict):
        try:
            for tn in ("output_task",):
                t = info.get(tn)
                if t and not t.done():
                    t.cancel()
            if info.get("ssh_process"):
                try:
                    info["ssh_process"].close()
                except Exception:
                    pass
            if info.get("ssh_conn"):
                try:
                    info["ssh_conn"].close()
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Cleanup error {cid}: {e}")


active_connections = ConnectionPool()


# ==================== 交互式检测 ====================

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
        rf'root@[^\s:]+:[^\$#\n]*[#]\s*$',
    ]
    combined = '|'.join(f'(?:{p})' for p in patterns)
    return re.compile(combined, re.MULTILINE)


def strip_ansi(text: str) -> str:
    ansi_re = re.compile(
        r'\x1b\[[0-9;]*[a-zA-Z]'
        r'|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)'
        r'|\x1b[()][AB012]'
        r'|\x1b[>=<]'
        r'|\r'
    )
    return ansi_re.sub('', text)


async def get_current_user_from_token(token: str, db: AsyncSession) -> Optional[User]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            return None
        result = await db.execute(select(User).where(User.username == username))
        return result.scalars().one_or_none()
    except (JWTError, Exception):
        return None


async def send_ws_safe(websocket: WebSocket, data: dict):
    try:
        await websocket.send_json(data)
    except Exception as e:
        logger.debug(f"WS send failed: {e}")


async def cleanup_connection(client_id: str, db: AsyncSession):
    info = await active_connections.remove(client_id)
    if not info:
        return

    task = info.get("output_task")
    if task and not task.done():
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    try:
        proc = info.get("ssh_process")
        if proc:
            proc.close()
    except Exception:
        pass
    try:
        conn = info.get("ssh_conn")
        if conn:
            conn.close()
    except Exception:
        pass

    session_log_id = info.get("session_log_id")
    if session_log_id:
        try:
            result = await db.execute(
                select(SessionLog).where(SessionLog.id == session_log_id)
            )
            sl = result.scalars().one_or_none()
            if sl:
                sl.end_time = datetime.now()
                cmds = info.get("commands_log", [])
                sl.commands_executed = json.dumps(cmds[-100:])
                await db.commit()
        except Exception as e:
            logger.warning(f"Session log update failed: {e}")
            try:
                await db.rollback()
            except Exception:
                pass


# ==================== 核心：SSH输出读取 + 内嵌监控 ====================

async def read_ssh_output(websocket: WebSocket, ssh_process, client_id: str):
    """
    读取 SSH 输出 + 内嵌 monitor 子任务（与备份版相同架构）
    """

    async def monitor():
        """后台监控：prompt检测 + 交互检测 + 超时"""
        PROMPT_IDLE = 2.0
        INTERACTIVE_IDLE = 3.0
        FORCE_IDLE = 30.0
        FORCE_TOTAL = 300.0

        logger.info(f"[{client_id}] monitor started")

        try:
            while client_id in active_connections:
                await asyncio.sleep(0.8)

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
                    if elapsed_idle >= FORCE_IDLE:
                        logger.info(f"[{client_id}] Command finished - empty_timeout | watching_command={ci.get('watching_command')} | output_len=0")
                        ci["watching_command"] = False
                        await send_ws_safe(websocket, {
                            "type": "command_finished",
                            "output": "",
                            "detection": "empty_timeout"
                        })
                        ci["command_output_buffer"] = ""
                    continue

                clean_buf = strip_ansi(buf)
                prompt_pattern = ci.get("prompt_pattern")

                # -------- 1. prompt 检测 --------
                if elapsed_idle >= PROMPT_IDLE and prompt_pattern:
                    last_lines = clean_buf.strip().split('\n')[-5:]
                    last_text = '\n'.join(last_lines)

                    if prompt_pattern.search(last_text):
                        if not detect_interactive_state(clean_buf):
                            logger.info(f"[{client_id}] Command finished - prompt | watching_command={ci.get('watching_command')} | output_len={len(clean_buf)} | idle={elapsed_idle:.1f}s")
                            ci["watching_command"] = False
                            ci["interactive_state"] = None
                            ci["interactive_notified"] = False

                            await send_ws_safe(websocket, {
                                "type": "command_finished",
                                "output": clean_buf,
                                "detection": "prompt"
                            })
                            ci["command_output_buffer"] = ""
                            continue

                # -------- 2. 交互式检测 --------
                if elapsed_idle >= INTERACTIVE_IDLE:
                    itype = detect_interactive_state(clean_buf)
                    if itype:
                        prev = ci.get("interactive_state")
                        ci["interactive_state"] = itype
                        if not ci.get("interactive_notified") or prev != itype:
                            ci["interactive_notified"] = True
                            logger.info(f"[{client_id}] Interactive: {itype}")
                            await send_ws_safe(websocket, {
                                "type": "interactive_detected",
                                "interactive_type": itype,
                                "output": clean_buf,
                                "hint": get_interactive_hint(itype)
                            })
                        continue

                # -------- 3. 强制超时 --------
                if elapsed_idle >= FORCE_IDLE or elapsed_total >= FORCE_TOTAL:
                    reason = "idle_timeout" if elapsed_idle >= FORCE_IDLE else "total_timeout"
                    logger.info(f"[{client_id}] Command finished - {reason} | watching_command={ci.get('watching_command')} | output_len={len(clean_buf)} | idle={elapsed_idle:.1f}s | total={elapsed_total:.1f}s")
                    ci["watching_command"] = False
                    ci["interactive_state"] = None
                    ci["interactive_notified"] = False
                    await send_ws_safe(websocket, {
                        "type": "command_finished",
                        "output": clean_buf,
                        "detection": reason
                    })
                    ci["command_output_buffer"] = ""

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[{client_id}] monitor error: {e}", exc_info=True)

    # ★ 启动 monitor 子任务
    monitor_task = asyncio.create_task(monitor())

    # ★ 主循环：读取 SSH 输出
    try:
        while True:
            try:
                data = await asyncio.wait_for(
                    ssh_process.stdout.read(4096),
                    timeout=0.5
                )
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.debug(f"[{client_id}] SSH read error: {e}")
                break

            if not data:
                logger.info(f"[{client_id}] SSH stdout EOF")
                break

            # 1. 转发到前端
            await send_ws_safe(websocket, {"type": "output", "data": data})

            # 2. ★★★ 更新监视缓冲区 ★★★
            ci = active_connections.get(client_id)
            if ci:
                ci["last_output_time"] = time.time()
                if ci.get("watching_command"):
                    buf = ci.get("command_output_buffer", "") + data
                    if len(buf) > MAX_OUTPUT_BUFFER:
                        buf = buf[-MAX_OUTPUT_BUFFER:]
                    ci["command_output_buffer"] = buf

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.warning(f"[{client_id}] read_ssh_output error: {e}")
    finally:
        monitor_task.cancel()
        try:
            await monitor_task
        except (asyncio.CancelledError, Exception):
            pass
        logger.info(f"[{client_id}] read_ssh_output ended")
        await send_ws_safe(websocket, {
            "type": "disconnected",
            "content": "SSH连接已断开"
        })


# ==================== WebSocket 主处理 ====================

@router.websocket("/terminal")
@router.websocket("/ws/terminal")
async def terminal_websocket(
    websocket: WebSocket,
    client_id: str = Query(...),
    token: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    user = await get_current_user_from_token(token, db)
    if not user:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()
    logger.info(f"[{client_id}] WebSocket accepted for {user.username}")

    try:
        while True:
            try:
                message = await websocket.receive_text()
                data = json.loads(message)
            except json.JSONDecodeError:
                await send_ws_safe(websocket, {"type": "error", "content": "Invalid JSON"})
                continue

            msg_type = data.get("type")
            logger.debug(f"[{client_id}] ws msg: {msg_type}")

            # ===== ping =====
            if msg_type == "ping":
                await send_ws_safe(websocket, {
                    "type": "pong",
                    "timestamp": data.get("timestamp", int(time.time() * 1000))
                })
                continue

            # ===== connect =====
            if msg_type == "connect":
                connection_id = data.get("connection_id")

                await send_ws_safe(websocket, {
                    "type": "status", "content": "正在查询连接配置..."
                })

                result = await db.execute(
                    select(Connection)
                    .where(Connection.id == connection_id)
                    .where(Connection.user_id == user.id)
                )
                conn = result.scalars().one_or_none()

                if not conn:
                    await send_ws_safe(websocket, {"type": "error", "content": "Connection not found"})
                    continue

                await send_ws_safe(websocket, {
                    "type": "status",
                    "content": f"正在连接 {conn.host}:{conn.port or 22} ..."
                })

                try:
                    ssh_options = {
                        "host": conn.host,
                        "port": conn.port or 22,
                        "username": conn.username,
                        "known_hosts": None,
                    }

                    key_file = None
                    try:
                        if conn.auth_method == "password":
                            ssh_options["password"] = conn.password
                        elif conn.auth_method == "private_key":
                            import tempfile, os, stat
                            if not conn.private_key:
                                await send_ws_safe(websocket, {"type": "error", "content": "Private key empty"})
                                continue
                            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.key') as f:
                                f.write(conn.private_key)
                                key_file = f.name
                            os.chmod(key_file, stat.S_IRUSR)
                            ssh_options["client_keys"] = [key_file]
                            if conn.passphrase:
                                ssh_options["passphrase"] = conn.passphrase
                        else:
                            ssh_options["password"] = conn.password

                        await send_ws_safe(websocket, {"type": "status", "content": "正在建立SSH连接..."})

                        ssh_conn = await asyncio.wait_for(
                            asyncssh.connect(**ssh_options), timeout=15
                        )

                        await send_ws_safe(websocket, {"type": "status", "content": "SSH已连接，正在创建终端会话..."})

                        ssh_process = await ssh_conn.create_process(
                            term_type='xterm-256color', term_size=(120, 30)
                        )

                    finally:
                        if key_file:
                            try:
                                os.unlink(key_file)
                            except Exception:
                                pass

                    # 会话日志
                    session_log_id = None
                    try:
                        session_log = SessionLog(
                            id=str(uuid.uuid4()),
                            user_id=user.id,
                            connection_id=conn.id,
                            type='terminal', content='',
                            host=conn.host, username=conn.username,
                            start_time=datetime.now(), commands_executed=''
                        )
                        db.add(session_log)
                        await db.commit()
                        session_log_id = session_log.id
                    except Exception as e:
                        try:
                            await db.rollback()
                        except Exception:
                            pass
                        logger.warning(f"Session log failed: {e}")

                    prompt_pattern = build_prompt_pattern(conn.username)

                    conn_info = {
                        "ssh_conn": ssh_conn,
                        "ssh_process": ssh_process,
                        "connection": conn,
                        "session_log_id": session_log_id,
                        "db": db,
                        "commands_log": [],
                        "prompt_pattern": prompt_pattern,
                        "watching_command": False,
                        "command_output_buffer": "",
                        "last_output_time": 0.0,
                        "watch_start_time": 0.0,
                        "interactive_state": None,
                        "interactive_notified": False,
                    }

                    await active_connections.add(client_id, conn_info)

                    # ★ 只启动一个 task（内含 monitor）
                    output_task = asyncio.create_task(
                        read_ssh_output(websocket, ssh_process, client_id)
                    )
                    conn_info["output_task"] = output_task

                    await send_ws_safe(websocket, {
                        "type": "connected",
                        "content": f"Connected to {conn.host} as {conn.username}"
                    })
                    logger.info(f"[{client_id}] Connected to {conn.host}")

                except asyncio.TimeoutError:
                    await send_ws_safe(websocket, {"type": "error", "content": f"连接超时: {conn.host}"})
                except asyncssh.PermissionDenied:
                    await send_ws_safe(websocket, {"type": "error", "content": f"认证失败: {conn.username}@{conn.host}"})
                except asyncssh.Error as e:
                    await send_ws_safe(websocket, {"type": "error", "content": f"SSH错误: {e}"})
                except Exception as e:
                    logger.exception(f"[{client_id}] Connection error")
                    await send_ws_safe(websocket, {"type": "error", "content": f"连接失败: {e}"})

            # ===== data/input =====
            elif msg_type in ("data", "input"):
                ci = active_connections.get(client_id)
                if ci:
                    proc = ci["ssh_process"]
                    data_content = data.get("data", "")
                    try:
                        proc.stdin.write(data_content)
                    except Exception as e:
                        logger.warning(f"[{client_id}] SSH write failed: {e}")
                        continue

                    if ci.get("watching_command"):
                        ci["interactive_notified"] = False
                        ci["interactive_state"] = None
                        ci["last_output_time"] = time.time()

                    if '\r' in data_content or '\n' in data_content:
                        cmd = data_content.strip().replace('\r', '').replace('\n', '')
                        if cmd:
                            ci["commands_log"].append({
                                "command": cmd,
                                "timestamp": datetime.now().isoformat()
                            })

            # ===== watch_command =====
            elif msg_type == "watch_command":
                ci = active_connections.get(client_id)
                if ci:
                    logger.info(f"[{client_id}] watch_command ON")
                    ci["watching_command"] = True
                    ci["command_output_buffer"] = ""
                    ci["last_output_time"] = time.time()
                    ci["watch_start_time"] = time.time()
                    ci["interactive_state"] = None
                    ci["interactive_notified"] = False

            # ===== stop_watch =====
            elif msg_type == "stop_watch":
                ci = active_connections.get(client_id)
                if ci:
                    logger.info(f"[{client_id}] watch_command OFF")
                    ci["watching_command"] = False
                    ci["command_output_buffer"] = ""
                    ci["interactive_state"] = None
                    ci["interactive_notified"] = False

            # ===== resize =====
            elif msg_type == "resize":
                ci = active_connections.get(client_id)
                if ci:
                    try:
                        ci["ssh_process"].change_terminal_size(
                            data.get("cols", 120), data.get("rows", 30)
                        )
                    except Exception:
                        pass

            # ===== disconnect =====
            elif msg_type == "disconnect":
                break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"[{client_id}] WS error: {e}")
    finally:
        await cleanup_connection(client_id, db)