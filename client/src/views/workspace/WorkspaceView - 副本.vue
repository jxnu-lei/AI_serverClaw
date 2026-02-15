<template>
  <div class="workspace-container">
    <div class="workspace-layout">
      <!-- 左侧边栏：连接管理 -->
      <aside class="connections-sidebar" :class="{ 'collapsed': sidebarCollapsed }">
        <div class="sidebar-header">
          <h2 v-if="!sidebarCollapsed">连接</h2>
          <el-icon class="collapse-btn" @click="sidebarCollapsed = !sidebarCollapsed">
            <DArrowLeft v-if="!sidebarCollapsed" />
            <DArrowRight v-else />
          </el-icon>
        </div>
        
        <div class="sidebar-content" v-show="!sidebarCollapsed">
          <!-- 添加连接按钮 -->
          <el-button type="primary" class="add-connection-btn" @click="openAddConnectionDialog">
            <el-icon><Plus /></el-icon>
            <span>添加服务器</span>
          </el-button>
          
          <!-- 连接列表 -->
          <div class="connections-list" v-loading="loadingConnections">
            <div 
              v-for="conn in connections" 
              :key="conn.id"
              class="connection-item"
              :class="{ 'active': activeConnection?.id === conn.id }"
              @click="connectToServer(conn)"
            >
              <div class="conn-icon">
                <el-icon :size="24"><Monitor /></el-icon>
              </div>
              <div class="conn-info">
                <div class="conn-name">{{ conn.name }}</div>
                <div class="conn-host">{{ conn.host }}:{{ conn.port }}</div>
              </div>
              <div class="conn-actions" @click.stop>
                <el-icon @click="editConnection(conn)"><Edit /></el-icon>
                <el-icon @click="deleteConnection(conn.id)" class="delete-icon"><Delete /></el-icon>
              </div>
              <div class="conn-status" v-if="activeConnection?.id === conn.id">
                <span class="status-dot"></span>
              </div>
            </div>
            
            <el-empty v-if="!loadingConnections && connections.length === 0" description="暂无连接" :image-size="60" />
          </div>
        </div>
      </aside>
      
      <!-- 主内容区：终端 -->
      <main class="terminal-main">
        <!-- 未连接时的欢迎界面 -->
        <div class="welcome-panel" v-if="!activeConnection">
          <div class="welcome-content">
            <el-icon class="welcome-icon"><Monitor /></el-icon>
            <h2>连接到服务器</h2>
            <p>从左侧选择一个服务器连接，或添加新的连接开始使用终端</p>
            <el-button type="primary" size="large" @click="openAddConnectionDialog">
              <el-icon><Plus /></el-icon>
              添加服务器
            </el-button>
          </div>
        </div>
        
        <!-- 已连接：显示终端 -->
        <div class="terminal-panel" v-else>
          <div class="terminal-header">
            <div class="terminal-info">
              <span class="server-name">{{ activeConnection.name }}</span>
              <el-tag size="small" :type="agentMode ? 'success' : 'info'">
                {{ agentMode ? 'Agent' : 'Shell' }}
              </el-tag>
              <el-tag size="small" type="info">{{ wsLatency }}ms</el-tag>
            </div>
            <div class="terminal-controls">
              <el-switch 
                v-model="agentMode" 
                active-text="Agent" 
                inactive-text="Shell"
                size="small"
              />
              <el-button type="danger" size="small" @click="disconnectServer">
                断开
              </el-button>
            </div>
          </div>
          
          <div class="terminal-wrapper">
            <div ref="terminalRef" class="terminal"></div>
            
            <!-- 底部区域 -->
            <div class="terminal-bottom-bar">
              <!-- 命令确认栏 -->
              <div class="command-confirm-bar" v-if="showCommandConfirm">
                <div class="confirm-label">是否同意执行以下命令并查看输出？</div>
                <div class="confirm-command-wrapper">
                  <el-input
                    v-if="isEditingCommand"
                    ref="commandEditRef"
                    v-model="editableCommand"
                    type="textarea"
                    :autosize="{ minRows: 1, maxRows: 6 }"
                    class="command-edit-input"
                    @keyup.enter.ctrl="confirmEditedCommand"
                    @keyup.escape="cancelEditCommand"
                  />
                  <code v-else class="confirm-command-text">{{ aiSuggestedCommand }}</code>
                </div>
                <div class="confirm-actions">
                  <template v-if="!isEditingCommand">
                    <el-button type="success" size="small" @click="confirmExecute">
                      执行 <span class="shortcut">Ctrl+D</span>
                    </el-button>
                    <el-button type="warning" size="small" @click="enterEditMode">
                      修改 <span class="shortcut">Ctrl+E</span>
                    </el-button>
                    <el-button type="danger" size="small" @click="rejectCommand">
                      拒绝 <span class="shortcut">Ctrl+I</span>
                    </el-button>
                  </template>
                  <template v-else>
                    <el-button type="primary" size="small" @click="confirmEditedCommand">
                      确认修改 <span class="shortcut">Ctrl+Enter</span>
                    </el-button>
                    <el-button size="small" @click="cancelEditCommand">
                      取消 <span class="shortcut">Esc</span>
                    </el-button>
                  </template>
                </div>
              </div>
              
              <!-- 交互式操作栏 -->
              <div class="interactive-bar" v-else-if="interactiveState">
                <div class="interactive-header">
                  <el-icon color="#e6a23c"><WarningFilled /></el-icon>
                  <span class="interactive-message">{{ interactiveHint.message }}</span>
                  <span class="interactive-elapsed">({{ waitingElapsed }}s)</span>
                </div>
                <div class="interactive-actions">
                  <el-button
                    v-for="action in interactiveHint.actions"
                    :key="action.label"
                    size="small"
                    type="primary"
                    @click="sendInteractiveInput(action.data)"
                  >
                    {{ action.label }}
                  </el-button>
                  <el-divider direction="vertical" />
                  <el-input
                    v-model="customInteractiveInput"
                    placeholder="自定义输入..."
                    size="small"
                    style="width: 200px;"
                    @keyup.enter="sendCustomInteractiveInput"
                  >
                    <template #append>
                      <el-button size="small" @click="sendCustomInteractiveInput">发送</el-button>
                    </template>
                  </el-input>
                  <el-divider direction="vertical" />
                  <el-button size="small" type="info" @click="sendInteractiveInput('\x03')">
                    中断 Ctrl+C
                  </el-button>
                  <el-button size="small" type="danger" text @click="forceStopWaiting">
                    强制结束
                  </el-button>
                </div>
              </div>
              
              <!-- 等待提示 -->
              <div class="waiting-bar" v-else-if="isWaitingCommandFinish">
                <el-icon class="is-loading"><Loading /></el-icon>
                <span>命令执行中，等待完成... ({{ waitingElapsed }}s)</span>
                <el-button size="small" text @click="sendCtrlC">中断 Ctrl+C</el-button>
                <el-button size="small" text type="danger" @click="forceStopWaiting">强制结束</el-button>
              </div>
              
              <!-- AI分析中 -->
              <div class="waiting-bar" v-else-if="isProcessingAI">
                <el-icon class="is-loading"><Loading /></el-icon>
                <span>AI 正在分析...</span>
              </div>

              <!-- 普通输入栏 -->
              <div class="input-area" v-else>
                <el-input
                  ref="inputRef"
                  v-model="userInputText"
                  :placeholder="agentMode ? '输入自然语言或命令，AI将智能响应' : '输入命令...'"
                  @keyup.enter="handleUserSubmit"
                  clearable
                  size="large"
                >
                  <template #prefix>
                    <span class="prompt-prefix">{{ promptPrefix }}</span>
                  </template>
                  <template #append>
                    <el-button @click="handleUserSubmit">
                      <el-icon><Promotion /></el-icon>
                    </el-button>
                  </template>
                </el-input>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
    
    <!-- 添加/编辑连接对话框 -->
    <el-dialog v-model="showConnectionDialog" :title="isEditing ? '编辑连接' : '添加连接'" width="600px">
      <el-form :model="connectionForm" label-width="120px">
        <el-form-item label="名称">
          <el-input v-model="connectionForm.name" placeholder="请输入连接名称" />
        </el-form-item>
        <el-form-item label="分组">
          <el-input v-model="connectionForm.group_name" placeholder="default" />
        </el-form-item>
        <el-form-item label="协议">
          <el-select v-model="connectionForm.protocol" style="width: 100%">
            <el-option label="SSH" value="ssh" />
            <el-option label="SFTP" value="sftp" />
          </el-select>
        </el-form-item>
        <el-form-item label="主机">
          <el-input v-model="connectionForm.host" placeholder="请输入主机地址或IP" />
        </el-form-item>
        <el-form-item label="端口">
          <el-input-number v-model="connectionForm.port" :min="1" :max="65535" style="width: 100%" />
        </el-form-item>
        <el-form-item label="用户名">
          <el-input v-model="connectionForm.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="认证方式">
          <el-radio-group v-model="connectionForm.auth_method">
            <el-radio label="password">密码认证</el-radio>
            <el-radio label="privatekey">私钥认证</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="密码" v-if="connectionForm.auth_method === 'password'">
          <el-input v-model="connectionForm.password" type="password" placeholder="请输入密码" show-password />
        </el-form-item>
        <el-form-item label="私钥" v-if="connectionForm.auth_method === 'privatekey'">
          <el-input type="textarea" v-model="connectionForm.private_key" :rows="4" placeholder="请输入SSH私钥内容" />
        </el-form-item>
        <el-form-item label="密钥密码" v-if="connectionForm.auth_method === 'privatekey'">
          <el-input v-model="connectionForm.passphrase" type="password" placeholder="如果私钥有密码保护，请输入" show-password />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="connectionForm.tags" placeholder="多个标签用逗号分隔" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input type="textarea" v-model="connectionForm.description" :rows="2" placeholder="可选描述信息" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showConnectionDialog = false">取消</el-button>
        <el-button type="primary" @click="saveConnection">保存</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading, Plus, Edit, Delete, Monitor, DArrowLeft, DArrowRight, WarningFilled, Promotion } from '@element-plus/icons-vue'
import { http } from '@/utils/api'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'

// ==================== 基础状态 ====================
const connections = ref<any[]>([])
const terminalWs = ref<WebSocket | null>(null)
const activeConnection = ref<any>(null)
const terminalRef = ref<HTMLElement>()
const terminal = ref<Terminal | null>(null)
const fitAddon = ref<FitAddon>(new FitAddon())
const loadingConnections = ref(false)
const showConnectionDialog = ref(false)
const isEditing = ref(false)
const connectionForm = ref<any>({})
const wsLatency = ref(0)

// ==================== Agent 模式状态 ====================
const agentMode = ref(true)
const showCommandConfirm = ref(false)
const aiSuggestedCommand = ref('')
const lastAICommand = ref('')

// 内联编辑状态
const isEditingCommand = ref(false)
const editableCommand = ref('')
const commandEditRef = ref<any>(null)

// 用户输入状态
const userInputText = ref('')
const inputRef = ref<any>(null)

// 交互式输入状态
const customInteractiveInput = ref('')

// 命令执行等待机制（由后端驱动）
const isWaitingCommandFinish = ref(false)
const waitingStartTime = ref(0)
const waitingElapsed = ref(0)
let waitingTimer: ReturnType<typeof setInterval> | null = null
// 最大等待时间（秒）
const MAX_WAIT_SECONDS = 300

// ==================== 交互式程序状态 ====================
const interactiveState = ref<string | null>(null)  // null | 'pager' | 'interactive' | 'confirm'
const interactiveHint = ref<any>({ message: '', actions: [] })

// ==================== 终端输出缓冲 ====================
const recentTerminalOutput = ref('')

// ==================== AI 助手状态 ====================
const isProcessingAI = ref(false)
const conversationHistory = ref<{role: string, content: string}[]>([])
const currentSessionId = ref<string | null>(null)  // 当前对话会话ID

// 命令预处理配置 - 避免进入交互式分页器
const PAGEBOUND_COMMANDS: Record<string, string> = {
  'dpkg': 'dpkg -l | head -200',
  'journalctl': 'journalctl --no-pager -n 100',
  'systemctl': 'systemctl --no-pager',
  'git log': 'git --no-pager log --oneline -20',
  'git diff': 'git --no-pager diff',
  'git show': 'git --no-pager show',
  'ps aux': 'ps aux | head -50',
  'netstat': 'netstat -tlnp 2>/dev/null || ss -tlnp',
  'lsof': 'lsof | head -100',
}

/**
 * 预处理命令，添加非交互式标志避免进入分页器
 */
const preprocessCommand = (cmd: string): string => {
  const trimmed = cmd.trim()
  
  // 检查是否在预配置列表中
  for (const [key, replacement] of Object.entries(PAGEBOUND_COMMANDS)) {
    if (trimmed.startsWith(key)) {
      // 如果命令本身已经包含分页控制，则不替换
      if (trimmed.includes('--no-pager') || trimmed.includes('less') || trimmed.includes('more')) {
        return cmd
      }
      return replacement
    }
  }
  
  // 通用处理：为常用命令添加环境变量
  if (/^\s*(cat|grep|awk|sed|find|ls|ps|df|du)\s/.test(trimmed)) {
    // 这些命令通常不会进入分页，保持不变
    return cmd
  }
  
  return cmd
}

// 当前prompt前缀
const promptPrefix = computed(() => {
  if (!activeConnection.value) return '$'
  return `${activeConnection.value.username}@${activeConnection.value.name}:~$`
})

// ==================== 命令识别（增强版） ====================
const isCommand = (input: string): boolean => {
  if (!input.trim()) return false
  
  const commandPatterns = [
    /^(sudo\s+)?[a-z_][a-z0-9_-]*\s/i,  // 以常规命令开头
    /^\.\//,  // ./script
    /^\//,    // /usr/bin/xxx
    /^~/,     // ~/script
  ]
  
  const commandKeywords = [
    'ls', 'cd', 'pwd', 'cat', 'echo', 'mkdir', 'rm', 'cp', 'mv', 'chmod', 'chown',
    'apt', 'yum', 'dnf', 'npm', 'yarn', 'pnpm', 'pip', 'pip3',
    'git', 'curl', 'wget', 'ssh', 'scp', 'rsync', 'tar', 'zip', 'unzip',
    'grep', 'awk', 'sed', 'find', 'which', 'ps', 'top', 'kill', 'df', 'du', 'free',
    'uname', 'whoami', 'id', 'su', 'sudo', 'systemctl', 'service',
    'docker', 'kubectl', 'node', 'python', 'python3', 'java',
    'make', 'gcc', 'vim', 'nano', 'less', 'head', 'tail', 'exit', 'clear',
    'ping', 'ifconfig', 'ip', 'netstat', 'ss', 'dig', 'nslookup',
    'export', 'source', 'alias', 'history', 'man',
  ]
  
  const firstWord = input.trim().split(/\s+/)[0]?.toLowerCase() || ''
  
  // 检查是否包含中文（中文 = 自然语言）
  if (/[\u4e00-\u9fff]/.test(input)) {
    return false
  }
  
  return commandKeywords.includes(firstWord) || 
         commandPatterns.some(p => p.test(input.trim()))
}

// ==================== 终端写入辅助函数 ====================
const writeCommandBox = (command: string) => {
  if (!terminal.value) return
  terminal.value.writeln('')
  terminal.value.writeln('\x1b[33m是否同意执行以下命令并查看输出？\x1b[0m')
  terminal.value.writeln('')
  terminal.value.writeln(`  \x1b[32;1m${command}\x1b[0m`)
  terminal.value.writeln('')
  terminal.value.writeln('\x1b[33m  执行 Ctrl+D  │  修改 Ctrl+E  │  拒绝 Ctrl+I\x1b[0m')
  terminal.value.writeln('')
}

const writeUserInput = (input: string) => {
  if (!terminal.value) return
  terminal.value.writeln(`\x1b[37;1m${promptPrefix.value}\x1b[0m ${input}`)
}

const writeExecutionMarker = (command: string) => {
  if (!terminal.value) return
  terminal.value.writeln(`\x1b[32m✓ 已同意\x1b[0m  ${command}`)
  terminal.value.writeln('')
}

const writeRejectionMarker = () => {
  if (!terminal.value) return
  terminal.value.writeln('\x1b[90m✗ 已拒绝执行命令\x1b[0m')
}

// ==================== 命令确认操作 ====================
const confirmExecute = async () => {
  if (!aiSuggestedCommand.value) return

  const cmd = aiSuggestedCommand.value
  showCommandConfirm.value = false
  isEditingCommand.value = false

  writeExecutionMarker(cmd)

  // 记录这是AI建议的命令，执行完成后需要反馈给AI
  lastAICommand.value = cmd

  // 保存命令执行消息
  await saveChatMessage({
    role: 'command',
    content: `执行命令: ${cmd}`,
    command: cmd,
    command_status: 'executed',
    message_type: 'command_execute'
  })

  // 进入等待状态
  startWaiting()

  // 通知后端开始监视命令输出
  if (terminalWs.value && terminalWs.value.readyState === WebSocket.OPEN) {
    terminalWs.value.send(JSON.stringify({ type: 'watch_command' }))
  }

  // 发送命令到终端
  sendCommandToTerminal(cmd)

  aiSuggestedCommand.value = ''
}

const rejectCommand = async () => {
  const cmd = aiSuggestedCommand.value
  showCommandConfirm.value = false
  isEditingCommand.value = false
  aiSuggestedCommand.value = ''
  writeRejectionMarker()

  // 保存拒绝执行的消息
  await saveChatMessage({
    role: 'command',
    content: `拒绝执行命令: ${cmd}`,
    command: cmd,
    command_status: 'rejected',
    message_type: 'command_reject'
  })
}



// ==================== 改动2：内联编辑命令 ====================
const enterEditMode = () => {
  editableCommand.value = aiSuggestedCommand.value
  isEditingCommand.value = true
  nextTick(() => {
    commandEditRef.value?.focus()
  })
}

const confirmEditedCommand = () => {
  if (!editableCommand.value.trim()) {
    ElMessage.warning('命令不能为空')
    return
  }
  
  aiSuggestedCommand.value = editableCommand.value.trim()
  isEditingCommand.value = false
  // 自动执行修改后的命令
  confirmExecute()
}

const cancelEditCommand = () => {
  isEditingCommand.value = false
  editableCommand.value = ''
}

// ==================== 等待命令完成（由后端通知驱动） ====================
const startWaiting = () => {
  isWaitingCommandFinish.value = true
  waitingStartTime.value = Date.now()
  waitingElapsed.value = 0
  
  // 显示计时器
  if (waitingTimer) clearInterval(waitingTimer)
  waitingTimer = setInterval(() => {
    waitingElapsed.value = Math.floor((Date.now() - waitingStartTime.value) / 1000)
    
    // 超过最大等待时间
    if (waitingElapsed.value >= MAX_WAIT_SECONDS) {
      forceStopWaiting()
    }
  }, 1000)
}

const stopWaiting = () => {
  isWaitingCommandFinish.value = false
  if (waitingTimer) {
    clearInterval(waitingTimer)
    waitingTimer = null
  }
}

/**
 * 后端发来 command_finished 时调用
 * 命令完成后，把输出发给AI决定下一步
 */
const onCommandFinished = async (output: string) => {
  stopWaiting()

  // 通知后端停止监视
  if (terminalWs.value && terminalWs.value.readyState === WebSocket.OPEN) {
    terminalWs.value.send(JSON.stringify({ type: 'stop_watch' }))
  }

  // 更新最近输出
  recentTerminalOutput.value = output || recentTerminalOutput.value

  const cmd = lastAICommand.value

  // 保存命令输出到后端
  if (cmd) {
    await saveChatMessage({
      role: 'output',
      content: output.slice(-4000),
      command: cmd,
      command_output: output.slice(-4000),
      command_status: 'executed',
      message_type: 'output'
    })
  }

  // 只有AI触发的命令才自动反馈给AI继续对话
  if (cmd && agentMode.value && conversationHistory.value.length > 0) {
    isProcessingAI.value = true

    // 构建结果消息，让AI决定下一步
    const resultMessage = `命令 \`${cmd}\` 已执行完成，完整输出如下：
\`\`\`
${output.slice(-4000)}
\`\`\`
请根据执行结果判断下一步操作。如果任务已完成请说明已完成；如果还需要继续，请给出下一个命令（继续遵循单条命令原则）。`

    // 添加到对话历史
    conversationHistory.value.push({ role: 'user', content: resultMessage })

    // 继续调用AI处理
    await processWithAI(resultMessage)

    lastAICommand.value = ''
    isProcessingAI.value = false
  } else {
    // 非AI触发的命令，只是显示分析
    if (cmd && terminal.value) {
      terminal.value.writeln('')
      terminal.value.writeln(`\x1b[90m[命令执行完成]\x1b[0m`)
      terminal.value.writeln('')
    }
    lastAICommand.value = ''
  }
}

const forceStopWaiting = () => {
  // 通知后端停止监视
  if (terminalWs.value && terminalWs.value.readyState === WebSocket.OPEN) {
    terminalWs.value.send(JSON.stringify({ type: 'stop_watch' }))
  }
  
  stopWaiting()
  lastAICommand.value = ''
  
  // 清除交互状态
  interactiveState.value = null
  interactiveHint.value = { message: '', actions: [] }
  
  ElMessage.info('已强制结束等待')
  
  if (terminal.value) {
    terminal.value.writeln('\x1b[90m[已强制结束命令等待]\x1b[0m')
  }
}

// ==================== 发送命令到终端 ====================
const sendCommandToTerminal = (cmd: string) => {
  if (terminalWs.value && terminalWs.value.readyState === WebSocket.OPEN) {
    terminalWs.value.send(JSON.stringify({ type: 'data', data: cmd + '\r' }))
  }
}

// ==================== 发送交互式输入 ====================
/**
 * 核心改动：发送交互式输入
 * - 使用和普通输入一样的 data 类型，直接写入 SSH stdin
 * - 暂时清除交互状态（让后端重新检测）
 * - 不发给 AI，等命令完全结束后再一并发给 AI
 */
const sendInteractiveInput = (inputData: string) => {
  if (!terminalWs.value || terminalWs.value.readyState !== WebSocket.OPEN) return

  // 直接用 data 类型，和终端普通输入完全一致
  terminalWs.value.send(JSON.stringify({
    type: 'data',
    data: inputData
  }))

  // 暂时清除交互状态，让后端重新检测
  // 后端收到新输入后会重置检测状态，如果退出了交互模式会检测到 prompt
  // 如果还在交互模式会重新发 interactive_detected
  interactiveState.value = null
}

const sendCustomInteractiveInput = () => {
  const val = customInteractiveInput.value
  if (!val) return
  // 不自动加 \r，让用户决定（有些交互程序单字符就生效）
  sendInteractiveInput(val)
  customInteractiveInput.value = ''
}

const sendCtrlC = () => {
  sendInteractiveInput('\x03')
}

// ==================== 核心：AI助手处理 ====================

/**
 * 调用AI获取响应（流式）
 */
const callAI = async (prompt: string, systemPrompt?: string): Promise<string> => {
  isProcessingAI.value = true
  
  try {
    const token = localStorage.getItem('access_token')
    if (!token) {
      ElMessage.error('请先登录')
      return ''
    }
    
    const response = await fetch('/api/llm/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        prompt,
        system_prompt: systemPrompt,
        conversation_history: conversationHistory.value,
        terminal_context: recentTerminalOutput.value.slice(-2000)
      })
    })
    
    if (!response.ok) {
      const error = await response.text()
      throw new Error(error)
    }
    
    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let fullContent = ''
    
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      
      const chunk = decoder.decode(value, { stream: true })
      buffer += chunk
      
      const lines = buffer.split('\n\n')
      buffer = lines.pop() || ''
      
      for (const line of lines) {
        if (line.startsWith('data:')) {
          const data = line.slice(5).trim()
          if (data === '[DONE]') continue
          
          try {
            const parsed = JSON.parse(data)
            if (parsed.content) {
              fullContent += parsed.content
            } else if (parsed.error) {
              throw new Error(parsed.error)
            }
          } catch (e) {
            // 忽略解析错误，继续读取
          }
        }
      }
    }
    
    return fullContent
  } catch (e: any) {
    ElMessage.error('AI调用失败: ' + (e.message || '未知错误'))
    return ''
  } finally {
    isProcessingAI.value = false
  }
}

/**
 * 解析AI响应（JSON格式）
 */
const parseAIResponse = (content: string): { explanation: string, command: string, needs_more_info: boolean } => {
  try {
    // 尝试解析JSON
    const jsonMatch = content.match(/\{[\s\S]*\}/)
    if (jsonMatch) {
      const parsed = JSON.parse(jsonMatch[0])
      return {
        explanation: parsed.explanation || '',
        command: parsed.command || '',
        needs_more_info: parsed.needs_more_info || false
      }
    }
  } catch (e) {
    // JSON解析失败，尝试文本解析
  }
  
  // 回退：按行解析
  const lines = content.split('\n').filter(l => l.trim())
  const commandLine = lines.find(l => l.startsWith('command:') || l.startsWith('Command:'))
  const explanationLines = lines.filter(l => !l.startsWith('command:') && !l.startsWith('Command:'))
  
  return {
    explanation: explanationLines.join('\n'),
    command: commandLine ? commandLine.replace(/^command:/i, '').trim() : '',
    needs_more_info: false
  }
}

/**
 * 处理AI对话（核心函数）
 * 用于处理用户输入和命令执行结果
 */
const processWithAI = async (input: string) => {
  isProcessingAI.value = true
  
  try {
    const systemPrompt = buildSystemPrompt()
    
    const aiResponse = await callAI(input, systemPrompt)
    
    if (!aiResponse) {
      isProcessingAI.value = false
      return
    }
    
    // 添加AI回复到历史
    conversationHistory.value.push({ role: 'assistant', content: aiResponse })
    
    const parsed = parseAIResponse(aiResponse)

    // 显示AI的自然语言解释
    if (parsed.explanation) {
      if (terminal.value) {
        terminal.value.writeln('')
        terminal.value.writeln(`\x1b[36m[AI] ${parsed.explanation}\x1b[0m`)
        terminal.value.writeln('')
      }
    }

    // 保存AI回复到后端
    if (parsed.command) {
      await saveChatMessage({
        role: 'assistant',
        content: parsed.explanation,
        ai_explanation: parsed.explanation,
        ai_suggested_command: parsed.command,
        message_type: 'command_suggest'
      })
    } else {
      await saveChatMessage({
        role: 'assistant',
        content: parsed.explanation,
        message_type: 'text'
      })
    }

    // 如果有命令建议，显示确认框
    if (parsed.command) {
      const processedCmd = preprocessCommand(parsed.command)
      aiSuggestedCommand.value = processedCmd
      lastAICommand.value = processedCmd
      showCommandConfirm.value = true
      writeCommandBox(processedCmd)
    }
  } catch (e: any) {
    ElMessage.error('AI处理失败: ' + (e.message || '未知错误'))
  } finally {
    isProcessingAI.value = false
  }
}

/**
 * 构建系统提示词
 */
const buildSystemPrompt = (): string => {
  const connInfo = activeConnection.value
  return `你是一个专业的Linux服务器运维AI助手，正在帮助用户管理一台服务器。

服务器信息：
- 主机: ${connInfo?.host || '未知'}
- 用户: ${connInfo?.username || '未知'}

最近终端输出:
\`\`\`
${recentTerminalOutput.value.slice(-3000)}
\`\`\`

回复格式（严格JSON）：
{
  "explanation": "中文解释你的思路和计划",
  "command": "shell命令（如果这一步需要执行命令）",
  "needs_more_info": false
}

关键规则：
1. 每次只返回一条命令
2. 系统会自动等待命令执行完毕后将完整输出传给你，你再决定下一步
3. 绝对不要使用 sleep 来等待命令完成
4. 不要把多个命令用 && 或 ; 串联
5. 必须避免命令进入交互式模式（已做预处理）
6. 如果任务已完成，explanation说明已完成，command设为空字符串
7. 如果还需要继续，给出下一个命令`
}

/**
 * 处理用户输入（Agent模式核心）
 */
const handleUserSubmit = async () => {
  const input = userInputText.value.trim()
  if (!input) return

  userInputText.value = ''

  if (!agentMode.value) {
    // Shell 模式：直接发送命令
    sendCommandToTerminal(input)
    return
  }

  // Agent 模式
  writeUserInput(input)

  // 添加到对话历史
  conversationHistory.value.push({ role: 'user', content: input })

  // 保存用户输入到后端
  await saveChatMessage({
    role: 'user',
    content: input,
    message_type: isCommand(input) ? 'command' : 'text'
  })

  // 如果是直接命令，不需要调用AI
  if (isCommand(input)) {
    const processedCmd = preprocessCommand(input)
    sendCommandToTerminal(processedCmd)
    return
  }

  // 调用AI处理
  await processWithAI(input)
}

// ==================== 终端初始化 ====================
const initTerminal = () => {
  if (!terminalRef.value) return

  if (terminal.value) {
    terminal.value.dispose()
  }

  terminal.value = new Terminal({
    cursorBlink: true,
    fontSize: 14,
    fontFamily: 'Consolas, Monaco, "Courier New", monospace',
    rows: 30,
    cols: 120,
    scrollback: 5000,
    theme: {
      background: '#1e1e1e',
      foreground: '#d4d4d4',
      cursor: '#d4d4d4',
      selectionBackground: '#264f78',
    }
  })

  fitAddon.value = new FitAddon()
  terminal.value.loadAddon(fitAddon.value)
  terminal.value.open(terminalRef.value)
  fitAddon.value.fit()

  terminal.value.onData((data) => {
    if (!agentMode.value) {
      // Shell 模式：直接转发所有输入到后端
      if (terminalWs.value && terminalWs.value.readyState === WebSocket.OPEN) {
        terminalWs.value.send(JSON.stringify({ type: 'data', data }))
      }
    } else {
      // Agent 模式：快捷键
      if (showCommandConfirm.value && !isEditingCommand.value) {
        if (data === '\x04') { confirmExecute(); return }     // Ctrl+D
        if (data === '\x05') { enterEditMode(); return }      // Ctrl+E
        if (data === '\t') { rejectCommand(); return }         // Ctrl+I (Tab)
      }
    }
  })

  // 监听窗口大小变化
  const resizeObserver = new ResizeObserver(() => {
    fitAddon.value.fit()
    if (terminalWs.value && terminalWs.value.readyState === WebSocket.OPEN) {
      const dims = fitAddon.value.proposeDimensions()
      if (dims) {
        terminalWs.value.send(JSON.stringify({
          type: 'resize',
          cols: dims.cols,
          rows: dims.rows
        }))
      }
    }
  })
  
  if (terminalRef.value) {
    resizeObserver.observe(terminalRef.value)
  }
}

// ==================== 对话历史管理 ====================
const createChatSession = async (connection: any) => {
  try {
    const token = localStorage.getItem('access_token')
    if (!token) return
    
    const response = await fetch('/api/chat-history/sessions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        connection_id: connection.id,
        host: connection.host,
        username: connection.username,
        title: `${connection.username}@${connection.host}`
      })
    })
    
    if (response.ok) {
      const session = await response.json()
      currentSessionId.value = session.id
      console.log('[ChatSession] Created:', session.id)
    }
  } catch (e) {
    console.error('[ChatSession] Failed to create:', e)
  }
}

const saveChatMessage = async (message: {
  role: string
  content?: string
  command?: string
  command_output?: string
  command_status?: string
  ai_explanation?: string
  ai_suggested_command?: string
  message_type?: string
}) => {
  if (!currentSessionId.value) return
  
  try {
    const token = localStorage.getItem('access_token')
    if (!token) return
    
    const response = await fetch(`/api/chat-history/sessions/${currentSessionId.value}/messages`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        role: message.role,
        content: message.content || '',
        command: message.command,
        command_output: message.command_output,
        command_status: message.command_status,
        ai_explanation: message.ai_explanation,
        ai_suggested_command: message.ai_suggested_command,
        message_type: message.message_type || 'text',
        extra_data: {}
      })
    })
    
    if (!response.ok) {
      console.error('[ChatMessage] Failed to save:', await response.text())
    }
  } catch (e) {
    console.error('[ChatMessage] Error:', e)
  }
}

const completeChatSession = async () => {
  if (!currentSessionId.value) return
  
  try {
    const token = localStorage.getItem('access_token')
    if (!token) return
    
    await fetch(`/api/chat-history/sessions/${currentSessionId.value}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        status: 'completed'
      })
    })
    
    currentSessionId.value = null
  } catch (e) {
    console.error('[ChatSession] Failed to complete:', e)
  }
}

// ==================== WebSocket 连接 ====================
const connectToServer = async (connection: any) => {
  const token = localStorage.getItem('access_token')
  if (!token) {
    ElMessage.error('请先登录')
    return
  }

  activeConnection.value = connection
  
  // 重置AI状态
  conversationHistory.value = []
  recentTerminalOutput.value = ''
  aiSuggestedCommand.value = ''
  lastAICommand.value = ''
  showCommandConfirm.value = false
  
  // 创建新的对话会话（仅在Agent模式下）
  if (agentMode.value) {
    await createChatSession(connection)
  }
  
  await nextTick()
  initTerminal()
  
  if (!terminal.value) {
    ElMessage.error('终端初始化失败')
    activeConnection.value = null
    return
  }

  const clientId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

  const envHost = (import.meta.env.VITE_API_HOST as string) || ''
  let proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  let backendHost = window.location.host

  if (envHost && envHost.length > 0) {
    const normalized = envHost.replace(/\/+$/, '')
    if (/^https?:\/\//.test(normalized)) {
      proto = normalized.startsWith('https://') ? 'wss' : 'ws'
      backendHost = normalized.replace(/^https?:\/\//, '')
    } else {
      backendHost = normalized
    }
  }

  const wsUrl = `${proto}://${backendHost}/ws/terminal?client_id=${clientId}&token=${token}`
  
  const connectStart = Date.now()

  try {
    terminalWs.value = new WebSocket(wsUrl)
  } catch (err: any) {
    ElMessage.error('无法创建 WebSocket：' + (err?.message || err))
    return
  }

  terminalWs.value.onopen = () => {
    wsLatency.value = Date.now() - connectStart
    terminalWs.value?.send(JSON.stringify({ type: 'connect', connection_id: connection.id }))
    terminal.value?.writeln(`\r\n\x1b[32m[正在连接到 ${connection.name}...]\x1b[0m`)
    ElMessage.success(`正在连接到 ${connection.name}`)
    
    // 启动延迟检测
    startLatencyCheck()
  }

  // ==================== WebSocket 消息处理 ====================
  const handleWsMessage = (ev: MessageEvent) => {
    try {
      const msg = JSON.parse(ev.data)

      switch (msg.type) {
        case 'output':
          if (terminal.value && msg.data) terminal.value.write(msg.data)
          recentTerminalOutput.value += msg.data || ''
          if (recentTerminalOutput.value.length > 5000) {
            recentTerminalOutput.value = recentTerminalOutput.value.slice(-5000)
          }
          break

        case 'connected':
          terminal.value?.writeln(`\r\n\x1b[32m[已连接: ${msg.content}]\x1b[0m\r\n`)
          break

        case 'error':
          terminal.value?.writeln(`\r\n\x1b[31m[错误: ${msg.content}]\x1b[0m`)
          ElMessage.error(msg.content)
          if (isWaitingCommandFinish.value) onCommandFinished(msg.content || '')
          break

        case 'pong':
          wsLatency.value = Date.now() - (msg.timestamp || Date.now())
          break

        case 'disconnected':
          terminal.value?.writeln(`\r\n\x1b[31m[SSH会话结束]\x1b[0m`)
          if (isWaitingCommandFinish.value) stopWaiting()
          interactiveState.value = null
          break

        // 命令执行完毕（后端检测到 prompt）
        case 'command_finished':
          console.log('[command_finished]', msg.detection)
          interactiveState.value = null
          onCommandFinished(msg.output || '')
          break

        // 检测到交互式程序
        case 'interactive_detected':
          console.log('[interactive]', msg.interactive_type, msg.hint?.message)
          interactiveState.value = msg.interactive_type
          interactiveHint.value = msg.hint || { message: '检测到交互式程序', actions: [] }
          // 不中断等待，只是切换底部栏显示
          break
      }
    } catch {
      if (terminal.value) terminal.value.write(ev.data)
    }
  }

  terminalWs.value.onmessage = handleWsMessage

  terminalWs.value.onclose = () => {
    terminal.value?.writeln('\r\n\x1b[31m[连接已断开]\x1b[0m')
    ElMessage.warning('连接已断开')
    if (isWaitingCommandFinish.value) stopWaiting()
    interactiveState.value = null
  }

  terminalWs.value.onerror = () => {
    ElMessage.error('WebSocket 连接错误')
  }
}

// 延迟检测
let latencyTimer: ReturnType<typeof setInterval> | null = null

const startLatencyCheck = () => {
  if (latencyTimer) clearInterval(latencyTimer)
  latencyTimer = setInterval(() => {
    if (terminalWs.value && terminalWs.value.readyState === WebSocket.OPEN) {
      terminalWs.value.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }))
    }
  }, 5000)
}

// 断开连接
const disconnectServer = async () => {
  if (isWaitingCommandFinish.value) {
    // 通知后端停止监视
    if (terminalWs.value && terminalWs.value.readyState === WebSocket.OPEN) {
      terminalWs.value.send(JSON.stringify({ type: 'stop_watch' }))
    }
    stopWaiting()
  }

  // 完成对话会话
  if (currentSessionId.value) {
    await completeChatSession()
  }

  if (terminalWs.value) {
    terminalWs.value.send(JSON.stringify({ type: 'disconnect' }))
    terminalWs.value.close()
    terminalWs.value = null
  }
  if (terminal.value) {
    try {
      terminal.value.dispose()
    } catch (e) {
      console.warn('Terminal dispose error:', e)
    }
    terminal.value = null
  }
  fitAddon.value = new FitAddon()
  activeConnection.value = null

  // 清理AI状态
  conversationHistory.value = []
  recentTerminalOutput.value = ''
  aiSuggestedCommand.value = ''
  lastAICommand.value = ''
  showCommandConfirm.value = false
  interactiveState.value = null
  currentSessionId.value = null

  if (latencyTimer) { clearInterval(latencyTimer); latencyTimer = null }
}

// ==================== 连接管理 CRUD ====================
const loadConnections = async () => {
  loadingConnections.value = true
  try {
    const res = await http.get('/api/connections')
    connections.value = res.data || res || []
  } catch (e: any) {
    ElMessage.error('加载连接列表失败')
  } finally {
    loadingConnections.value = false
  }
}

const openAddConnectionDialog = () => {
  isEditing.value = false
  connectionForm.value = {
    name: '', host: '', port: 22, username: 'root',
    protocol: 'ssh', auth_method: 'password',
    password: '', private_key: '', passphrase: '',
    group_name: 'default', tags: '', description: ''
  }
  showConnectionDialog.value = true
}

const editConnection = (conn: any) => {
  isEditing.value = true
  connectionForm.value = { ...conn }
  showConnectionDialog.value = true
}

const saveConnection = async () => {
  try {
    if (isEditing.value) {
      await http.put(`/api/connections/${connectionForm.value.id}`, connectionForm.value)
      ElMessage.success('更新成功')
    } else {
      await http.post('/api/connections', connectionForm.value)
      ElMessage.success('添加成功')
    }
    showConnectionDialog.value = false
    loadConnections()
  } catch (e: any) {
    ElMessage.error('保存失败: ' + (e.message || '未知错误'))
  }
}

const deleteConnection = async (id: string) => {
  try {
    await ElMessageBox.confirm('确定删除此连接？', '确认')
    await http.delete(`/api/connections/${id}`)
    ElMessage.success('删除成功')
    loadConnections()
  } catch { /* cancelled */ }
}



// ==================== 全局快捷键 ====================
const handleGlobalKeydown = (e: KeyboardEvent) => {
  // Ctrl+Shift+I 切换 Agent 模式
  if (e.ctrlKey && e.shiftKey && e.key === 'I') {
    e.preventDefault()
    agentMode.value = !agentMode.value
    ElMessage.info(agentMode.value ? 'Agent 模式已开启' : 'Agent 模式已关闭')
  }
}

// ==================== 生命周期 ====================
onMounted(() => {
  loadConnections()
  document.addEventListener('keydown', handleGlobalKeydown)
})

onUnmounted(async () => {
  disconnectServer()
  document.removeEventListener('keydown', handleGlobalKeydown)
  if (latencyTimer) clearInterval(latencyTimer)
  if (waitingTimer) clearInterval(waitingTimer)
})

// 侧边栏状态
const sidebarCollapsed = ref(false)
</script>

<style scoped lang="scss">
// ==================== 现代工作台布局 ====================
.workspace-container {
  height: calc(100vh - 85px);
  padding: 0;
  max-width: none;
}

.workspace-layout {
  display: flex;
  height: 100%;
  gap: 0;
  background: #0f0f0f;
}

// ==================== 左侧边栏 ====================
.connections-sidebar {
  width: 280px;
  min-width: 280px;
  background: linear-gradient(180deg, #1a1a2e 0%, #16162a 100%);
  border-right: 1px solid #2a2a4a;
  display: flex;
  flex-direction: column;
  transition: all 0.3s ease;
  
  &.collapsed {
    width: 48px;
    min-width: 48px;
  }
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid #2a2a4a;
  
  h2 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: #e0e0e0;
  }
  
  .collapse-btn {
    cursor: pointer;
    color: #888;
    font-size: 24px;
    padding: 4px;
    border-radius: 4px;
    transition: all 0.2s;
    
    &:hover {
      background: #2a2a4a;
      color: #fff;
    }
  }
}

.sidebar-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.add-connection-btn {
  width: 100%;
  margin-bottom: 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  font-weight: 500;
  
  &:hover {
    opacity: 0.9;
  }
  
  .el-icon {
    margin-right: 6px;
  }
}

.connections-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.connection-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
  
  &:hover {
    background: rgba(255, 255, 255, 0.06);
    border-color: #3a3a5a;
    
    .conn-actions {
      opacity: 1;
    }
  }
  
  &.active {
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.2) 0%, rgba(118, 75, 162, 0.2) 100%);
    border-color: #667eea;
    
    .conn-icon {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: #fff;
    }
  }
}

.conn-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: #2a2a4a;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #888;
  min-width: 40px;
  min-height: 40px;

  // 关键修复：穿透 scoped 强制设置 el-icon 和内部 svg 的尺寸
  :deep(.el-icon) {
    font-size: 24px !important;
    width: 24px;
    height: 24px;

    svg {
      width: 24px !important;
      height: 24px !important;
    }
  }
}

.conn-info {
  flex: 1;
  min-width: 0;
}

.conn-name {
  font-size: 14px;
  font-weight: 500;
  color: #e0e0e0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conn-host {
  font-size: 12px;
  color: #666;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conn-actions {
  display: flex;
  gap: 10px;
  opacity: 0;
  transition: opacity 0.2s;

  :deep(.el-icon) {
    padding: 6px;
    border-radius: 6px;
    cursor: pointer;
    color: #888;
    font-size: 24px;
    width: 24px;
    height: 24px;

    svg {
      width: 24px !important;
      height: 24px !important;
    }

    &:hover {
      background: #3a3a5a;
      color: #fff;
    }

    &.delete-icon:hover {
      color: #f56c6c;
    }
  }
}

.conn-status {
  position: absolute;
  top: 8px;
  right: 8px;
  
  .status-dot {
    display: block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #67c23a;
    animation: pulse 2s infinite;
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

// ==================== 主终端区 ====================
.terminal-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: #0a0a0f;
}

// 欢迎面板
.welcome-panel {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(ellipse at center, #1a1a2e 0%, #0a0a0f 100%);
}

.welcome-content {
  text-align: center;
  padding: 40px;
  
  .welcome-icon {
    font-size: 72px;
    color: #3a3a5a;
    margin-bottom: 24px;
  }
  
  h2 {
    font-size: 28px;
    font-weight: 300;
    color: #e0e0e0;
    margin: 0 0 12px 0;
  }
  
  p {
    font-size: 14px;
    color: #666;
    margin: 0 0 32px 0;
    max-width: 320px;
  }
  
  .el-button {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border: none;
    padding: 12px 32px;
    font-size: 15px;
    
    .el-icon {
      margin-right: 8px;
    }
  }
}

// 终端面板
.terminal-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.terminal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: #16162a;
  border-bottom: 1px solid #2a2a4a;
}

.terminal-info {
  display: flex;
  align-items: center;
  gap: 12px;
  
  .server-name {
    font-size: 14px;
    font-weight: 500;
    color: #e0e0e0;
  }
}

.terminal-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.terminal-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: #0f0f0f;
}

.terminal {
  flex: 1;
  background: #0d0d0d !important;
  border-radius: 0;
  min-height: 400px;
}

.terminal-bottom-bar {
  flex-shrink: 0;
  background: #16162a;
  border-top: 1px solid #2a2a4a;
  padding: 8px 12px;
}

/* 交互式操作栏样式 */
.interactive-bar {
  padding: 10px 12px;
  background: #2d2d30;
  border-radius: 4px;
  border: 1px solid #e6a23c;
}

.interactive-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  color: #e6a23c;
  font-size: 14px;
}

.interactive-message { flex: 1; }
.interactive-elapsed { color: #999; font-size: 12px; }

.interactive-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.interactive-actions .el-divider--vertical {
  border-color: #555;
  height: 20px;
}

.interactive-actions :deep(.el-input__wrapper) {
  background: #1e1e1e;
  border-color: #555;
}

.interactive-actions :deep(.el-input__inner) {
  color: #d4d4d4;
}

/* 普通输入栏样式 */
.input-area {
  display: flex;
  align-items: center;
}

.input-area :deep(.el-input__wrapper) {
  background: #1e1e1e;
  border-color: #3c3c3c;
}

.input-area :deep(.el-input__inner) {
  color: #d4d4d4;
}

.prompt-prefix {
  color: #6a9955;
  font-family: 'Consolas', monospace;
  font-size: 13px;
  white-space: nowrap;
}

/* 命令确认栏样式增强 */
.command-confirm-bar {
  margin-bottom: 8px;
  padding: 10px 12px;
  background: #2d2d30;
  border-radius: 4px;
  border: 1px solid #ffc107;
}

.confirm-label {
  color: #ffc107;
  font-size: 13px;
  margin-bottom: 6px;
}

.confirm-command-wrapper {
  margin-bottom: 8px;
}

.command-edit-input {
  background: #1e1e1e !important;
  border-color: #3c3c3c !important;
}

.command-edit-input :deep(.el-textarea__inner) {
  color: #d4d4d4;
  font-family: 'Consolas', monospace;
  font-size: 14px;
}

.confirm-command-text {
  display: block;
  background: #1e1e1e;
  padding: 8px 12px;
  border-radius: 4px;
  color: #4ec9b0;
  font-family: 'Consolas', monospace;
  font-size: 14px;
  white-space: pre-wrap;
  word-break: break-all;
}

.confirm-actions {
  display: flex;
  gap: 8px;
}

.shortcut {
  font-size: 11px;
  opacity: 0.7;
  margin-left: 4px;
}

/* 等待提示样式 */
.waiting-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #252526;
  border-radius: 4px;
  color: #d4d4d4;
  font-size: 13px;
}

.waiting-bar .is-loading {
  animation: rotate 1s linear infinite;
}

// ==================== 保留原有样式兼容 ====================

.workspace-header {
  margin-bottom: 20px;
  
  h1 {
    margin: 0;
    font-size: 24px;
  }
  
  p {
    color: #666;
    margin-top: 4px;
  }
}

.workspace-content {
  display: grid;
  grid-template-columns: 1fr;
  gap: 20px;
}

.connection-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.connection-name {
  font-weight: bold;
  font-size: 16px;
}

.mode-tag {
  font-size: 12px;
}

/* 终端区域样式 */
.terminal-card {
  margin-bottom: 20px;
}

.terminal-wrapper {
  display: flex;
  flex-direction: column;
}

.terminal {
  background: #1e1e1e;
  border-radius: 4px 4px 0 0;
  height: 500px;
}

/* ==================== 底部栏通用 ==================== */
.terminal-bottom-bar {
  background: #252526;
  border: 1px solid #3c3c3c;
  border-top: none;
  border-radius: 0 0 4px 4px;
  padding: 8px 12px;
  min-height: 48px;
}

/* 普通输入区 */
.input-area :deep(.el-input__wrapper) {
  background: #1e1e1e;
  border-color: #3c3c3c;
}

.input-area :deep(.el-input__inner) {
  color: #d4d4d4;
}

.prompt-prefix {
  color: #6a9955;
  font-family: 'Consolas', monospace;
  font-size: 13px;
  white-space: nowrap;
}

/* 命令确认栏 */
.command-confirm-bar {
  padding: 10px 12px;
  background: #2d2d30;
  border-radius: 4px;
  border: 1px solid #ffc107;
}

.confirm-label {
  color: #ffc107;
  font-size: 13px;
  margin-bottom: 8px;
}

.confirm-command-wrapper {
  background: #1e1e1e;
  padding: 8px 12px;
  border-radius: 4px;
  margin-bottom: 8px;
  min-height: 32px;
}

.confirm-command-text {
  color: #4ec9b0;
  font-family: 'Consolas', monospace;
  font-size: 14px;
  word-break: break-all;
  white-space: pre-wrap;
}

/* 内联编辑输入框样式 */
.command-edit-input :deep(.el-textarea__inner) {
  background: transparent;
  border: 1px solid #4ec9b0;
  color: #4ec9b0;
  font-family: 'Consolas', monospace;
  font-size: 14px;
  padding: 4px 8px;
}

.confirm-actions {
  display: flex;
  gap: 8px;
}

.shortcut {
  font-size: 11px;
  opacity: 0.7;
  margin-left: 4px;
}

/* 等待提示栏 */
.waiting-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #aaa;
  font-size: 13px;
  padding: 8px 0;
}

.waiting-bar .is-loading {
  color: #409eff;
}

/* 交互式程序检测提示栏 */
.interactive-bar {
  padding: 10px 12px;
  background: #2d2d30;
  border-radius: 4px;
  border: 1px solid #e6a23c;
}

.interactive-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  color: #e6a23c;
  font-size: 14px;
}

.interactive-message {
  flex: 1;
}

.interactive-elapsed {
  color: #999;
  font-size: 12px;
}

.interactive-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.interactive-actions .el-divider--vertical {
  border-color: #555;
  height: 20px;
}

.interactive-actions :deep(.el-input__wrapper) {
  background: #1e1e1e;
  border-color: #555;
}

.interactive-actions :deep(.el-input__inner) {
  color: #d4d4d4;
}
</style>
