from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any, Optional, List
import httpx
import json
import logging

from app.database import get_db
from app.models.user import User
from app.models.llm_config import LLMConfig, LLMProvider
from app.schemas.llm import LLMRequest, LLMResponse, LLMConfigUpdate
from app.routes.auth import get_current_active_user
from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


# ========== 提供商管理 API ==========

@router.get("/providers", response_model=List[Dict[str, Any]])
async def list_providers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取提供商列表（系统默认 + 用户自定义）"""
    # 获取系统默认提供商
    result = await db.execute(
        select(LLMProvider).where(LLMProvider.is_default == True)
    )
    system_providers = result.scalars().all()
    
    # 获取用户自定义提供商
    result = await db.execute(
        select(LLMProvider).where(LLMProvider.user_id == current_user.id, LLMProvider.is_default == False)
    )
    user_providers = result.scalars().all()
    
    def to_dict(p: LLMProvider) -> Dict[str, Any]:
        return {
            "id": str(p.id),
            "name": p.name,
            "code": p.code,
            "default_model": p.default_model,
            "default_url": p.default_url,
            "is_default": p.is_default
        }
    
    return [to_dict(p) for p in list(system_providers) + list(user_providers)]


@router.post("/providers", response_model=Dict[str, Any], status_code=201)
async def create_provider(
    name: str,
    code: str,
    default_model: Optional[str] = None,
    default_url: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """创建自定义提供商"""
    # 检查code是否已存在
    result = await db.execute(
        select(LLMProvider).where(LLMProvider.code == code)
    )
    existing = result.scalars().one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="提供商代码已存在"
        )
    
    provider = LLMProvider(
        user_id=current_user.id,
        name=name,
        code=code.lower().replace(" ", "-"),
        default_model=default_model,
        default_url=default_url,
        is_default=False
    )
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    
    return {
        "id": str(provider.id),
        "name": provider.name,
        "code": provider.code,
        "default_model": provider.default_model,
        "default_url": provider.default_url,
        "is_default": provider.is_default
    }


@router.delete("/providers/{provider_id}", status_code=204)
async def delete_provider(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """删除自定义提供商（不能删除系统默认）"""
    result = await db.execute(
        select(LLMProvider).where(
            LLMProvider.id == provider_id,
            LLMProvider.user_id == current_user.id
        )
    )
    provider = result.scalars().one_or_none()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="提供商不存在"
        )
    
    if provider.is_default:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除系统默认提供商"
        )
    
    await db.delete(provider)
    await db.commit()
    return None


# ========== 辅助函数：获取用户当前激活的配置 ==========

async def _get_active_config(db: AsyncSession, user_id: str) -> Optional[LLMConfig]:
    """获取用户当前激活的配置，自动修复多个激活的情况"""
    result = await db.execute(
        select(LLMConfig)
        .where(LLMConfig.user_id == user_id, LLMConfig.is_active == True)
    )
    configs = result.scalars().all()
    
    if len(configs) > 1:
        # 只保留第一个激活
        for c in configs[1:]:
            c.is_active = False
        await db.commit()
        return configs[0]
    elif len(configs) == 1:
        return configs[0]
    
    return None


# ========== 配置 API ==========

@router.get("/config", response_model=Dict[str, Any])
async def get_llm_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取用户当前激活的LLM配置"""
    config = await _get_active_config(db, current_user.id)
    
    if not config:
        # 没有激活的，返回默认配置
        return {
            "provider": settings.DEFAULT_LLM_PROVIDER,
            "model": settings.DEFAULT_LLM_MODEL,
            "api_key": "",
            "base_url": settings.DEFAULT_LLM_API_URL,
            "temperature": 0.7
        }

    return {
        "provider": config.provider,
        "model": config.model,
        "api_key": config.api_key or "",
        "base_url": getattr(config, "api_url", "") or settings.DEFAULT_LLM_API_URL,
        "temperature": config.temperature or 0.7
    }


@router.put("/config", response_model=Dict[str, Any])
async def update_llm_config(
    config_update: LLMConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """更新当前激活的模型配置（不改变激活状态）"""
    config = await _get_active_config(db, current_user.id)
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先在下方添加模型配置并激活"
        )
    
    # 更新配置；需要将外部的 base_url 映射到数据库的 api_url
    try:
        update_data = config_update.model_dump(exclude_unset=True)
    except Exception:
        update_data = config_update.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        if field == "base_url":
            setattr(config, "api_url", value or "")
        elif field == "name" or field == "is_active":
            # 不通过此接口修改name和is_active
            continue
        else:
            setattr(config, field, value)
    
    await db.commit()
    await db.refresh(config)
    
    return {
        "provider": config.provider,
        "model": config.model,
        "api_key": config.api_key,
        "base_url": getattr(config, "api_url", ""),
        "temperature": config.temperature,
        "message": "配置已更新"
    }


@router.get("/configs", response_model=List[Dict[str, Any]])
async def list_llm_configs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """列出当前用户的所有 LLM 配置"""
    result = await db.execute(
        select(LLMConfig).where(LLMConfig.user_id == current_user.id)
    )
    configs = result.scalars().all()

    def to_dict(c: LLMConfig) -> Dict[str, Any]:
        return {
            "id": str(c.id),
            "name": c.name,
            "provider": c.provider,
            "model": c.model,
            "api_key": c.api_key,
            "base_url": getattr(c, "api_url", ""),
            "temperature": c.temperature,
            "is_active": c.is_active
        }

    return [to_dict(c) for c in configs]


@router.post("/configs", response_model=Dict[str, Any], status_code=201)
async def create_llm_config(
    config_update: LLMConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """为当前用户创建一个新的 LLM 配置"""
    api_url = config_update.base_url or ""
    name = config_update.name or (
        f"{config_update.provider}-{config_update.model}"
        if config_update.provider and config_update.model
        else "default"
    )
    
    # 如果要激活这个新配置，先取消其他配置的激活状态
    if config_update.is_active:
        result = await db.execute(
            select(LLMConfig).where(LLMConfig.user_id == current_user.id)
        )
        for c in result.scalars().all():
            c.is_active = False
    
    config = LLMConfig(
        user_id=current_user.id,
        name=name,
        provider=config_update.provider,
        api_url=api_url,
        api_key=config_update.api_key,
        model=config_update.model,
        temperature=config_update.temperature or 0.7,
        is_active=config_update.is_active or False
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)

    return {
        "id": str(config.id),
        "name": config.name,
        "provider": config.provider,
        "model": config.model,
        "api_key": config.api_key,
        "base_url": getattr(config, "api_url", ""),
        "temperature": config.temperature,
        "is_active": config.is_active
    }


@router.delete("/configs/{config_id}", status_code=204)
async def delete_llm_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """删除指定的 LLM 配置"""
    result = await db.execute(
        select(LLMConfig).where(
            LLMConfig.id == config_id,
            LLMConfig.user_id == current_user.id
        )
    )
    config = result.scalars().one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="配置不存在"
        )
    
    await db.delete(config)
    await db.commit()
    
    return None


@router.put("/configs/{config_id}/activate", response_model=Dict[str, Any])
async def activate_llm_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """激活指定的 LLM 配置（同时取消其他配置的激活状态）"""
    # 先找到要激活的配置
    result = await db.execute(
        select(LLMConfig).where(
            LLMConfig.id == config_id,
            LLMConfig.user_id == current_user.id
        )
    )
    config = result.scalars().one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="配置不存在"
        )
    
    # 取消该用户所有配置的激活状态
    all_result = await db.execute(
        select(LLMConfig).where(LLMConfig.user_id == current_user.id)
    )
    for c in all_result.scalars().all():
        c.is_active = False
    
    # 激活选中的配置
    config.is_active = True
    await db.commit()
    await db.refresh(config)
    
    return {
        "id": str(config.id),
        "name": config.name,
        "provider": config.provider,
        "model": config.model,
        "api_key": config.api_key or "",
        "base_url": getattr(config, "api_url", ""),
        "temperature": config.temperature,
        "is_active": config.is_active
    }


# ========== LLM 调用 ==========

async def generate_llm_response(
    prompt: str,
    config: Dict[str, Any],
    system_prompt: str = None,
    conversation_history: List[Dict[str, str]] = None,
    terminal_context: str = ""
) -> StreamingResponse:
    """生成LLM响应（流式）"""
    provider = config.get("provider", "deepseek")
    model = config.get("model", "deepseek-chat")
    api_key = config.get("api_key")
    base_url = config.get("base_url")
    temperature = config.get("temperature", 0.7)
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LLM API key is required"
        )
    
    # 构建默认系统提示
    default_system = """你是一个专业的Linux服务器运维AI助手。

你的回复必须严格遵循以下JSON格式：
{
  "explanation": "你的自然语言解释，说明你要做什么以及为什么",
  "command": "要执行的shell命令（如果不需要执行命令则为空字符串）",
  "needs_more_info": false
}

规则：
1. 如果用户的请求需要多个步骤，每次只返回一个步骤的命令
2. explanation 中用中文解释你的思路
3. 如果用户只是打招呼或闲聊，command 设为空字符串
4. 始终返回有效的JSON"""

    # 使用传入的系统提示或默认
    final_system = system_prompt if system_prompt else default_system
    
    async def stream_response():
        try:
            # 验证API Key
            if not api_key:
                yield f"data: {json.dumps({'error': 'API Key未配置或为空'})}\n\n"
                return
            
            # 构建消息列表
            messages = []
            messages.append({"role": "system", "content": final_system})
            
            # 添加对话历史
            if conversation_history:
                for msg in conversation_history:
                    messages.append({
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", "")
                    })
            
            # 添加当前用户输入（只添加一次）
            messages.append({"role": "user", "content": prompt})
            
            # 构建请求payload
            if provider in ("deepseek", "openai"):
                # DeepSeek / OpenAI API - 统一处理
                if base_url and base_url.strip():
                    if base_url.rstrip('/').endswith('/v1'):
                        url = base_url.rstrip('/') + '/chat/completions'
                    elif '/chat/completions' not in base_url:
                        url = base_url.rstrip('/') + '/chat/completions'
                    else:
                        url = base_url
                else:
                    if provider == "openai":
                        url = "https://api.openai.com/v1/chat/completions"
                    else:
                        url = "https://api.deepseek.com/v1/chat/completions"
                
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                }
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "stream": True
                }
            
            elif provider == "ollama":
                # Ollama API
                url = base_url or "http://localhost:11434/api/chat"
                headers = {
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": model,
                    "messages": messages,
                    "stream": True,
                    "options": {
                        "temperature": temperature
                    }
                }
            
            else:
                # 对于自定义提供商，默认使用 OpenAI 兼容格式
                if base_url and base_url.strip():
                    if base_url.rstrip('/').endswith('/v1'):
                        url = base_url.rstrip('/') + '/chat/completions'
                    elif '/chat/completions' not in base_url:
                        url = base_url.rstrip('/') + '/chat/completions'
                    else:
                        url = base_url
                else:
                    yield f"data: {json.dumps({'error': f'自定义提供商 {provider} 需要配置 API URL'})}\n\n"
                    return
                
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                }
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "stream": True
                }
            
            try:
                async with httpx.AsyncClient() as client:
                    async with client.stream(
                        "POST",
                        url,
                        headers=headers,
                        json=payload,
                        timeout=30.0
                    ) as response:
                        if response.status_code != 200:
                            error_text = await response.aread()
                            try:
                                error_data = json.loads(error_text) if error_text else {}
                                error_msg = error_data.get('error', {}).get('message', 'Unknown error')
                            except:
                                error_msg = error_text.decode('utf-8') if error_text else 'Unknown error'
                            yield f"data: {json.dumps({'error': f'LLM API错误 ({response.status_code}): {error_msg}'})}\n\n"
                            return
                        
                        content_count = 0
                        async for chunk in response.aiter_text():
                            if chunk.strip():
                                # 处理SSE格式
                                for line in chunk.splitlines():
                                    if line.startswith("data:"):
                                        data = line[5:].strip()
                                        if data == "[DONE]":
                                            continue
                                        try:
                                            chunk_data = json.loads(data)
                                            if "choices" in chunk_data and len(chunk_data["choices"]) > 0:
                                                choice = chunk_data["choices"][0]
                                                if "delta" in choice:
                                                    content = choice["delta"].get("content", "")
                                                    if content:
                                                        content_count += 1
                                                        yield f"data: {json.dumps({'content': content})}\n\n"
                                        except json.JSONDecodeError:
                                            continue
                        
                        if content_count == 0:
                            yield f"data: {json.dumps({'error': 'LLM未返回有效内容，请检查API Key和模型配置'})}\n\n"
                            
            except httpx.HTTPError as e:
                yield f"data: {json.dumps({'error': f'HTTP请求失败: {str(e)}'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': f'请求异常: {str(e)}'})}\n\n"
                
        except Exception as e:
            error_msg = str(e) if str(e) else "未知错误"
            yield f"data: {json.dumps({'error': f'服务器错误: {error_msg}'})}\n\n"
    
    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream"
    )


@router.post("/chat")
async def chat_with_llm(
    request: LLMRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """与LLM助手聊天（SSE流式响应）- 始终使用激活的配置"""
    # 获取用户激活的LLM配置
    config = await _get_active_config(db, current_user.id)
    
    # 构建LLM配置
    api_key = None
    if config and config.api_key:
        api_key = config.api_key
    elif hasattr(settings, 'DEFAULT_LLM_API_KEY') and settings.DEFAULT_LLM_API_KEY:
        api_key = settings.DEFAULT_LLM_API_KEY
    
    llm_config = {
        "provider": config.provider if config else settings.DEFAULT_LLM_PROVIDER,
        "model": config.model if config else settings.DEFAULT_LLM_MODEL,
        "api_key": api_key,
        "base_url": (getattr(config, "api_url", "") if config else "") or getattr(settings, 'DEFAULT_LLM_API_URL', ''),
        "temperature": (config.temperature if config else None) or request.temperature or 0.7
    }
    
    if not llm_config["api_key"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先在设置页面配置AI模型的API Key并激活"
        )
    
    # 处理对话历史
    conversation_history = None
    if request.conversation_history:
        conversation_history = []
        for msg in request.conversation_history:
            conversation_history.append({
                "role": msg.role,
                "content": msg.content
            })
    
    return await generate_llm_response(
        prompt=request.prompt,
        config=llm_config,
        system_prompt=request.system_prompt,
        conversation_history=conversation_history,
        terminal_context=request.terminal_context or ""
    )


@router.post("/suggest-command", response_model=Dict[str, str])
async def suggest_command(
    request: Dict[str, str],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """根据描述生成命令建议"""
    task_description = request.get("description", "")
    if not task_description:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task description is required"
        )
    
    # 获取用户的LLM配置
    config = await _get_active_config(db, current_user.id)
    
    if not config or not config.api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LLM configuration not set. Please update your LLM settings first."
        )
    
    # 构建提示
    prompt = f"""You are a server administration assistant. Generate a single command to accomplish the following task:\n\n{task_description}\n\nReturn only the command without any explanation."""
    
    # 调用LLM
    llm_config = {
        "provider": config.provider,
        "model": config.model,
        "api_key": config.api_key,
        "base_url": getattr(config, "api_url", ""),
        "temperature": 0.3  # 降低温度以获得更确定性的命令
    }
    
    try:
        # 这里应该调用流式API，但为了简化，我们使用非流式调用
        # TODO: 实现非流式的命令建议
        return {
            "command": "echo 'Command suggestion feature coming soon'"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Command suggestion failed: {str(e)}"
        )
