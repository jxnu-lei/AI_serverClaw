<template>
  <div class="ai-assistant-container">
    <div class="ai-assistant-header">
      <h1>AI 助手</h1>
      <p>与AI助手进行智能对话</p>
    </div>

    <el-card class="chat-card">
      <div class="chat-messages" ref="messagesContainer">
        <div
          v-for="(msg, index) in messages"
          :key="index"
          :class="['message', msg.role]"
        >
          <div class="message-avatar">
            <el-avatar v-if="msg.role === 'user'" :size="36" class="user-avatar">
              {{ userInitial }}
            </el-avatar>
            <el-avatar v-else :size="36" class="ai-avatar">
              <el-icon><ChatDotRound /></el-icon>
            </el-avatar>
          </div>
          <div class="message-content">
            <div class="message-bubble">
              <div v-if="msg.role === 'assistant'" class="ai-response" v-html="formatMessage(msg.content)"></div>
              <div v-else class="user-message">{{ msg.content }}</div>
            </div>
            <div class="message-time">{{ formatTime(msg.timestamp) }}</div>
          </div>
        </div>

        <div v-if="isLoading" class="message assistant loading">
          <div class="message-avatar">
            <el-avatar :size="36" class="ai-avatar">
              <el-icon><ChatDotRound /></el-icon>
            </el-avatar>
          </div>
          <div class="message-content">
            <div class="message-bubble">
              <div class="loading-indicator">
                <el-icon class="is-loading"><Loading /></el-icon>
                <span>AI 正在思考...</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="chat-input-area">
        <el-input
          v-model="userInput"
          type="textarea"
          :rows="3"
          placeholder="输入消息与AI助手对话..."
          @keydown.enter.ctrl="sendMessage"
          :disabled="isLoading"
        />
        <el-button
          type="primary"
          :loading="isLoading"
          @click="sendMessage"
          class="send-button"
        >
          <el-icon v-if="!isLoading"><Promotion /></el-icon>
          发送
        </el-button>
      </div>

      <div class="chat-actions">
        <el-button size="small" @click="clearChat">
          <el-icon><Delete /></el-icon>
          清空对话
        </el-button>
        <el-button size="small" @click="showSettingsTip">
          <el-icon><Setting /></el-icon>
          AI 设置
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ChatDotRound, Loading, Promotion, Delete, Setting } from '@element-plus/icons-vue'

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

const router = useRouter()
const messages = ref<Message[]>([])
const userInput = ref('')
const isLoading = ref(false)
const messagesContainer = ref<HTMLElement>()

const userName = computed(() => {
  return sessionStorage.getItem('user_name') || '用户'
})

const userInitial = computed(() => {
  return userName.value.charAt(0).toUpperCase()
})

// 加载聊天历史
const loadChatHistory = () => {
  try {
    const saved = localStorage.getItem('ai_assistant_messages')
    if (saved) {
      messages.value = JSON.parse(saved)
    }
  } catch (e) {
    console.error('加载聊天历史失败:', e)
  }
}

// 保存聊天历史
const saveChatHistory = () => {
  try {
    // 只保留最近50条消息
    const messagesToSave = messages.value.slice(-50)
    localStorage.setItem('ai_assistant_messages', JSON.stringify(messagesToSave))
  } catch (e) {
    console.error('保存聊天历史失败:', e)
  }
}

// 发送消息
const sendMessage = async () => {
  const input = userInput.value.trim()
  if (!input || isLoading.value) return

  // 添加用户消息
  const userMessage: Message = {
    role: 'user',
    content: input,
    timestamp: Date.now()
  }
  messages.value.push(userMessage)
  userInput.value = ''

  isLoading.value = true
  saveChatHistory()
  scrollToBottom()

  try {
    // 获取AI配置
    const configRes = await fetch('/api/llm/config', {
      headers: {
        'Authorization': `Bearer ${sessionStorage.getItem('access_token')}`
      }
    })

    const config = await configRes.json()
    
    if (!config.provider || !config.api_key) {
      ElMessage.warning('请先在设置页面配置AI')
      showSettingsTip()
      return
    }

    // 调用AI聊天接口
    const res = await fetch('/api/llm/chat', {
      method: 'POST',
      headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${sessionStorage.getItem('access_token')}`
        },
      body: JSON.stringify({
        prompt: input,
        system_prompt: getSystemPrompt(),
        conversation_history: messages.value
          .filter(m => m.role !== 'system')
          .map(m => ({ role: m.role, content: m.content }))
      })
    })

    if (!res.ok) {
      throw new Error('AI 请求失败')
    }

    // 解析SSE流
    const reader = res.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let aiContent = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) break

      const chunk = decoder.decode(value, { stream: true })
      buffer += chunk

      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''

      for (const part of parts) {
        if (part.startsWith('data:')) {
          const jsonStr = part.slice(5).trim()
          if (jsonStr === '[DONE]') continue

          try {
            const data = JSON.parse(jsonStr)
            if (data.content) {
              aiContent += data.content
            }
          } catch {
            // ignore
          }
        }
      }
    }

    // 添加AI回复
    const aiMessage: Message = {
      role: 'assistant',
      content: aiContent || '抱歉，我没有收到有效的回复',
      timestamp: Date.now()
    }
    messages.value.push(aiMessage)

  } catch (e: any) {
    const errorMessage: Message = {
      role: 'assistant',
      content: `❌ 错误: ${e.message || '未知错误'}`,
      timestamp: Date.now()
    }
    messages.value.push(errorMessage)
    ElMessage.error('AI 响应失败: ' + (e.message || '未知错误'))
  } finally {
    isLoading.value = false
    saveChatHistory()
    scrollToBottom()
  }
}

// 获取系统提示词
const getSystemPrompt = (): string => {
  return `你是一个专业的AI助手，专门为用户提供帮助。请用中文回答用户的问题。

如果你需要执行服务器命令，请在回复中说明。但这是一个纯聊天界面，无法直接执行命令。
如需执行服务器命令，请前往"工作台"连接服务器后使用AI助手功能。

你的职责：
1. 回答用户的技术问题
2. 提供编程和运维建议
3. 解释概念和原理
4. 帮助排查问题

请用友好、专业的方式回答问题。`
}

// 格式化消息（简单处理换行和代码块）
const formatMessage = (content: string): string => {
  if (!content) return ''
  
  // 转义HTML
  let formatted = content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  // 处理代码块
  formatted = formatted.replace(/```(\w*)\n?([\s\S]*?)```/g, (match, lang, code) => {
    return `<pre><code class="language-${lang}">${code.trim()}</code></pre>`
  })

  // 处理行内代码
  formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>')

  // 处理换行
  formatted = formatted.replace(/\n/g, '<br>')

  return formatted
}

// 格式化时间
const formatTime = (timestamp: number): string => {
  const date = new Date(timestamp)
  const hours = date.getHours().toString().padStart(2, '0')
  const minutes = date.getMinutes().toString().padStart(2, '0')
  return `${hours}:${minutes}`
}

// 滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

// 清空对话
const clearChat = () => {
  messages.value = []
  localStorage.removeItem('ai_assistant_messages')
  ElMessage.success('对话已清空')
}

// 提示去设置
const showSettingsTip = () => {
  ElMessage.info('前往设置页面配置AI助手')
  router.push('/settings')
}

onMounted(() => {
  loadChatHistory()
  scrollToBottom()
})
</script>

<style scoped lang="scss">
.ai-assistant-container {
  max-width: 900px;
  margin: 0 auto;
  padding: 20px;
}

.ai-assistant-header {
  margin-bottom: 20px;

  h1 {
    font-size: 24px;
    margin: 0 0 8px 0;
    color: #303133;
  }

  p {
    color: #606266;
    margin: 0;
  }
}

.chat-card {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 200px);
  min-height: 500px;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.message {
  display: flex;
  gap: 12px;
  max-width: 85%;

  &.user {
    align-self: flex-end;
    flex-direction: row-reverse;

    .message-bubble {
      background: #409eff;
      color: #fff;
    }

    .message-time {
      text-align: right;
    }
  }

  &.assistant {
    align-self: flex-start;
  }

  &.loading {
    .message-bubble {
      background: #f4f4f5;
    }
  }
}

.message-avatar {
  flex-shrink: 0;
}

.user-avatar {
  background: #409eff;
}

.ai-avatar {
  background: #67c23a;
  color: #fff;
}

.message-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.message-bubble {
  padding: 12px 16px;
  border-radius: 12px;
  background: #f4f4f5;
  color: #303133;
  word-break: break-word;
  line-height: 1.6;
}

.user-message {
  white-space: pre-wrap;
}

.ai-response {
  white-space: pre-wrap;

  :deep(pre) {
    background: #1e1e1e;
    color: #d4d4d4;
    padding: 12px;
    border-radius: 6px;
    overflow-x: auto;
    margin: 8px 0;
  }

  :deep(code) {
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 13px;
  }
}

.message-time {
  font-size: 12px;
  color: #909399;
  padding: 0 4px;
}

.loading-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #909399;

  .el-icon {
    font-size: 16px;
  }
}

.chat-input-area {
  padding: 16px 20px;
  border-top: 1px solid #e4e7ed;
  display: flex;
  gap: 12px;
  align-items: flex-end;

  .el-textarea {
    flex: 1;
  }

  .send-button {
    height: auto;
    padding: 12px 24px;
  }
}

.chat-actions {
  padding: 12px 20px;
  border-top: 1px solid #e4e7ed;
  display: flex;
  gap: 12px;
}
</style>
