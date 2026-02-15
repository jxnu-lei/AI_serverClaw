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
              :class="{ 'active': activeSession?.connectionId === conn.id }"
              @click="handleServerClick(conn)"
            >
              <div class="conn-icon">
                <el-icon :size="24"><Monitor /></el-icon>
              </div>
              <div class="conn-info">
                <div class="conn-name">{{ conn.name }}</div>
                <div class="conn-host">{{ conn.host }}:{{ conn.port }}</div>
              </div>
              <div class="conn-actions" @click.stop>
                <!-- 点击 + 号明确调用新建 -->
                <el-icon @click.stop="createNewSession(conn)" title="开新窗口"><Plus /></el-icon>
                <el-icon @click.stop="editConnection(conn)"><Edit /></el-icon>
                <el-icon @click.stop="deleteConnection(conn.id)" class="delete-icon"><Delete /></el-icon>
              </div>
              <div class="conn-status" v-if="activeSession?.connectionId === conn.id">
                <span class="status-dot"></span>
              </div>
            </div>
            
            <el-empty v-if="!loadingConnections && connections.length === 0" description="暂无连接" :image-size="60" />
          </div>
        </div>
      </aside>
      
      <!-- 主内容区：终端 -->
      <main class="terminal-main">
        <!-- 标签栏 -->
        <div class="terminal-tabs" v-if="sessions.length > 0">
          <div 
            v-for="s in sessions" 
            :key="s.id" 
            class="tab-item" 
            :class="{ active: activeSessionId === s.id }"
            @click="switchSession(s.id)"
          >
            <span 
              class="status-dot" 
              :class="s.status"
              @click="s.status === 'disconnected' && reconnectSession(s)"
              :title="s.status === 'disconnected' ? '点击重连' : ''"
            ></span>
            <span class="tab-name">{{ s.displayName }}</span>
            <el-icon class="close-icon" @click.stop="closeSession(s.id)"><Close /></el-icon>
          </div>
        </div>

        <!-- 欢迎界面 (无会话时) -->
        <div class="welcome-panel" v-if="sessions.length === 0">
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

        <!-- 终端面板 (动态切换) -->
        <div class="terminal-container" v-show="sessions.length > 0">
          <div 
            v-for="s in sessions" 
            :key="s.id" 
            v-show="activeSessionId === s.id"
            class="terminal-instance-wrapper"
          >
            <!-- 终端头部 -->
            <div class="terminal-header">
              <div class="terminal-info">
                <span class="server-name">{{ s.displayName }}</span>
                <el-tag size="small" :type="s.agentMode ? 'success' : 'info'">
                  {{ s.agentMode ? 'Agent' : 'Shell' }}
                </el-tag>
                <el-tag size="small" type="info">{{ s.wsLatency }}ms</el-tag>
              </div>
              <div class="terminal-controls">
                <el-switch 
                  v-model="s.agentMode" 
                  active-text="Agent" 
                  inactive-text="Shell"
                  size="small"
                  @change="updateSessionAgentMode(s.id, s.agentMode)"
                />
                <el-button type="danger" size="small" @click="disconnectServer(s.id)">
                  断开
                </el-button>
              </div>
            </div>

            <!-- 终端内容 -->
            <div class="terminal-wrapper">
              <div :id="'terminal-' + s.id" class="terminal"></div>
            </div>

            <!-- 底部区域 -->
            <div class="terminal-bottom-bar" v-if="s.agentMode">
              <!-- 命令确认栏 -->
              <div class="command-confirm-bar" v-if="s.showCommandConfirm">
                <div class="confirm-label">是否同意执行以下命令并查看输出？</div>
                <div class="confirm-command-wrapper">
                  <el-input
                    v-if="s.isEditingCommand"
                    v-model="s.editableCommand"
                    type="textarea"
                    :autosize="{ minRows: 1, maxRows: 6 }"
                    class="command-edit-input"
                    @keyup.enter.ctrl="confirmEditedCommand(s.id)"
                    @keyup.escape="cancelEditCommand(s.id)"
                  />
                  <code v-else class="confirm-command-text">{{ s.aiSuggestedCommand }}</code>
                </div>
                <div class="confirm-actions">
                  <template v-if="!s.isEditingCommand">
                    <el-button type="success" size="small" @click="confirmAICommand(s.id)">
                      执行 <span class="shortcut">Ctrl+D</span>
                    </el-button>
                    <el-button type="warning" size="small" @click="enterEditMode(s.id)">
                      修改 <span class="shortcut">Ctrl+E</span>
                    </el-button>
                    <el-button type="danger" size="small" @click="rejectCommand(s.id)">
                      拒绝 <span class="shortcut">Ctrl+I</span>
                    </el-button>
                  </template>
                  <template v-else>
                    <el-button type="primary" size="small" @click="confirmEditedCommand(s.id)">
                      确认修改 <span class="shortcut">Ctrl+Enter</span>
                    </el-button>
                    <el-button size="small" @click="cancelEditCommand(s.id)">
                      取消 <span class="shortcut">Esc</span>
                    </el-button>
                  </template>
                </div>
              </div>
              
              <!-- 交互式操作栏 -->
              <div class="interactive-bar" v-else-if="s.interactiveState">
                <div class="interactive-header">
                  <el-icon color="#e6a23c"><WarningFilled /></el-icon>
                  <span class="interactive-message">{{ s.interactiveHint.message }}</span>
                  <span class="interactive-elapsed">({{ s.waitingElapsed }}s)</span>
                </div>
                <div class="interactive-actions">
                  <el-button
                    v-for="action in s.interactiveHint.actions"
                    :key="action.label"
                    size="small"
                    type="primary"
                    @click="sendInteractiveInput(s.id, action.data)"
                  >
                    {{ action.label }}
                  </el-button>
                  <el-divider direction="vertical" />
                  <el-input
                    v-model="s.customInteractiveInput"
                    placeholder="自定义输入..."
                    size="small"
                    style="width: 200px;"
                    @keyup.enter="sendCustomInteractiveInput(s.id)"
                  >
                    <template #append>
                      <el-button size="small" @click="sendCustomInteractiveInput(s.id)">发送</el-button>
                    </template>
                  </el-input>
                  <el-divider direction="vertical" />
                  <el-button size="small" type="info" @click="sendInteractiveInput(s.id, '\x03')">
                    中断 Ctrl+C
                  </el-button>
                  <el-button size="small" type="danger" text @click="forceStopWaiting(s.id)">
                    强制结束
                  </el-button>
                </div>
              </div>
              
              <!-- 等待提示 -->
              <div class="waiting-bar" v-else-if="s.isWaitingCommandFinish">
                <el-icon class="is-loading"><Loading /></el-icon>
                <span>命令执行中，等待完成... ({{ s.waitingElapsed }}s)</span>
                <el-button size="small" text @click="sendCtrlC(s.id)">中断 Ctrl+C</el-button>
                <el-button size="small" text type="danger" @click="forceStopWaiting(s.id)">强制结束</el-button>
              </div>
              
              <!-- AI分析中 -->
              <div class="waiting-bar" v-else-if="s.isProcessingAI">
                <el-icon class="is-loading"><Loading /></el-icon>
                <span>AI 正在分析...</span>
              </div>

              <!-- 普通输入栏 -->
              <div class="input-area" v-else>
                <el-input
                  v-model="s.userInputText"
                  :placeholder="s.agentMode ? '输入自然语言或命令，AI将智能响应' : '输入命令...'"
                  @keyup.enter="handleUserSubmit(s.id)"
                  clearable
                  size="large"
                >
                  <template #prefix>
                    <span class="prompt-prefix">{{ s.promptPrefix }}</span>
                  </template>
                  <template #append>
                    <el-button @click="handleUserSubmit(s.id)">
                      <el-icon><Promotion /></el-icon>
                    </el-button>
                  </template>
                </el-input>
              </div>
            </div>
            
            <!-- Shell模式下不显示底部栏 -->
            <!-- 这样终端会自动占满整个空间 -->
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
import { ref, computed, onMounted, onUnmounted, nextTick, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading, Plus, Edit, Delete, Monitor, DArrowLeft, DArrowRight, WarningFilled, Promotion, Close } from '@element-plus/icons-vue'
import { http } from '@/utils/api'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'

// ==================== 会话接口定义 ====================
interface TerminalSession {
  id: string;             // 唯一实例ID
  connectionId: number;   // 关联的服务器ID
  displayName: string;    // 显示名称，如 "本地 #2"
  status: 'connected' | 'disconnected' | 'connecting';
  terminal: Terminal | null;          // xterm 实例
  fitAddon: FitAddon | null;          // 适应插件
  socket: WebSocket | null;
  agentMode: boolean;
  history: {role: string, content: string}[];         // 对话历史
  isWaitingCommandFinish: boolean;     // 是否正在等待AI/命令
  wsLatency: number;                   // WebSocket延迟
  recentTerminalOutput: string;        // 最近终端输出
  aiSuggestedCommand: string;          // AI建议命令
  lastAICommand: string;               // 最后执行的AI命令
  showCommandConfirm: boolean;         // 显示命令确认
  isEditingCommand: boolean;           // 正在编辑命令
  editableCommand: string;             // 可编辑命令
  userInputText: string;               // 用户输入文本
  customInteractiveInput: string;      // 自定义交互输入
  waitingStartTime: number;            // 等待开始时间
  waitingElapsed: number;              // 等待已用时间
  waitingTimer: ReturnType<typeof setInterval> | null;
  interactiveState: string | null;     // 交互状态
  interactiveHint: { message: string, actions: any[] };  // 交互提示
  isProcessingAI: boolean;             // AI处理中
  currentSessionId: string | null;     // 当前对话会话ID
  promptPrefix: string;                // 提示符前缀
  latencyTimer: ReturnType<typeof setInterval> | null;  // 延迟检测定时器
}

// ==================== 基础状态 ====================
const connections = ref<any[]>([])
const sessions = ref<TerminalSession[]>([]);
const activeSessionId = ref<string | null>(null);
const loadingConnections = ref(false)
const showConnectionDialog = ref(false)
const isEditing = ref(false)
const connectionForm = ref<any>({})

// 最大等待时间（秒）
const MAX_WAIT_SECONDS = 300

// ==================== 计算属性 ====================
const activeSession = computed(() => sessions.value.find(s => s.id === activeSessionId.value));
const activeConnection = computed(() => {
  const session = activeSession.value;
  if (!session) return null;
  return connections.value.find(conn => conn.id === session.connectionId);
});

// ==================== 会话管理函数 ====================
/**
 * 强制新建会话 (点击图标 + 时调用)
 */
const createNewSession = async (connection: any) => {
  // 计算名称序号 (例如: 本地 #2)
  const count = sessions.value.filter(s => s.connectionId === connection.id).length;
  const displayName = count === 0 ? connection.name : `${connection.name} #${count + 1}`;
  
  const sessionId = `sess_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  
  // 创建响应式session对象
  const newSession = reactive<TerminalSession>({
    id: sessionId,
    connectionId: connection.id,
    displayName: displayName,
    status: 'connecting',
    terminal: null,
    fitAddon: null,
    socket: null,
    agentMode: true, // 默认开启 Agent 模式
    history: [],
    isWaitingCommandFinish: false,
    wsLatency: 0,
    recentTerminalOutput: '',
    aiSuggestedCommand: '',
    lastAICommand: '',
    showCommandConfirm: false,
    isEditingCommand: false,
    editableCommand: '',
    userInputText: '',
    customInteractiveInput: '',
    waitingStartTime: 0,
    waitingElapsed: 0,
    waitingTimer: null,
    interactiveState: null,
    interactiveHint: { message: '', actions: [] },
    isProcessingAI: false, // AI处理中
    currentSessionId: null, // 这个由后端 createChatSession 后返回
    promptPrefix: `${connection.username}@${connection.name}:~$`,
    latencyTimer: null // 延迟检测定时器
  });

  sessions.value.push(newSession);
  activeSessionId.value = sessionId;

  await nextTick();
  await initSessionTerminal(newSession, connection);
};

/**
 * 切换会话
 */
const switchSession = (id: string) => {
  activeSessionId.value = id;
  // 必须调用 xterm 的 focus 和 refresh
  nextTick(() => {
    const session = sessions.value.find(s => s.id === id);
    session?.terminal?.focus();
  });
};

/**
 * 关闭会话
 */
const closeSession = async (id: string) => {
  const sessionIndex = sessions.value.findIndex(s => s.id === id);
  if (sessionIndex === -1) return;

  const session = sessions.value[sessionIndex];
  
  // 断开连接
  await disconnectServer(id);
  
  // 从数组中移除
  sessions.value.splice(sessionIndex, 1);
  
  // 如果关闭的是活动会话，切换到第一个会话
  if (activeSessionId.value === id) {
    activeSessionId.value = sessions.value.length > 0 ? sessions.value[0].id : null;
  }
};

/**
 * 更新会话Agent模式
 */
const updateSessionAgentMode = (id: string, mode: boolean) => {
  const session = sessions.value.find(s => s.id === id);
  if (session) {
    session.agentMode = mode;
  }
};

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
// 已移至会话管理函数中

// 断开连接
// 旧版本已删除，保留新版本在下方

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

// ==================== 会话延迟检测 ====================
const startSessionLatencyCheck = (session: TerminalSession) => {
  if (session.latencyTimer) clearInterval(session.latencyTimer)
  session.latencyTimer = setInterval(() => {
    if (session.socket && session.socket.readyState === WebSocket.OPEN) {
      session.socket.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }))
    }
  }, 5000)
}

// ==================== 断开会话连接 ====================
const disconnectServer = async (sessionId?: string) => {
  if (sessionId) {
    // 断开指定会话
    const session = sessions.value.find(s => s.id === sessionId)
    if (!session) return

    if (session.isWaitingCommandFinish) {
      // 通知后端停止监视
      if (session.socket && session.socket.readyState === WebSocket.OPEN) {
        session.socket.send(JSON.stringify({ type: 'stop_watch' }))
      }
      if (session.waitingTimer) {
        clearInterval(session.waitingTimer)
        session.waitingTimer = null
      }
      session.isWaitingCommandFinish = false
    }

    // 完成对话会话
    if (session.currentSessionId) {
      try {
        const token = localStorage.getItem('access_token')
        if (token) {
          await fetch(`/api/chat-history/sessions/${session.currentSessionId}`, {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ status: 'completed' })
          })
        }
      } catch (e) {
        console.error('[ChatSession] Failed to complete:', e)
      }
      session.currentSessionId = null
    }

    if (session.socket) {
      session.socket.send(JSON.stringify({ type: 'disconnect' }))
      session.socket.close()
      session.socket = null
    }
    if (session.terminal) {
      try {
        session.terminal.dispose()
      } catch (e) {
        console.warn('Terminal dispose error:', e)
      }
      session.terminal = null
    }
    session.fitAddon = null

    // 清理AI状态
    session.history = []
    session.recentTerminalOutput = ''
    session.aiSuggestedCommand = ''
    session.lastAICommand = ''
    session.showCommandConfirm = false
    session.interactiveState = null

    if (session.latencyTimer) { 
      clearInterval(session.latencyTimer); 
      session.latencyTimer = null 
    }
    if (session.waitingTimer) {
      clearInterval(session.waitingTimer)
      session.waitingTimer = null
    }
  } else {
    // 兼容旧代码，断开所有会话
    for (const session of sessions.value) {
      await disconnectServer(session.id)
    }
  }
}

// ==================== 全局快捷键 ====================
const handleGlobalKeydown = (e: KeyboardEvent) => {
  // Ctrl+Shift+I 切换 Agent 模式
  if (e.ctrlKey && e.shiftKey && e.key === 'I') {
    e.preventDefault()
    const session = activeSession.value
    if (session) {
      session.agentMode = !session.agentMode
      ElMessage.info(session.agentMode ? 'Agent 模式已开启' : 'Agent 模式已关闭')
    }
  }
}

// ==================== 生命周期 ====================
onMounted(() => {
  loadConnections()
  document.addEventListener('keydown', handleGlobalKeydown)
})

onUnmounted(() => {
  // 移除全局监听器
  document.removeEventListener('keydown', handleGlobalKeydown)
  
  // 不要在这里调用 disconnectServer() 或 session.socket.close()
  // 只有在 closeSession (主动点叉) 时才断开
  console.log('离开工作台，保持后台连接')
})

// ==================== 会话终端初始化 ====================
/**
 * 初始化会话终端
 * @param session 终端会话对象
 * @param connection 连接信息
 */
const initSessionTerminal = async (session: TerminalSession, connection: any) => {
  try {
    // 初始化终端
    const terminal = new Terminal({
      fontSize: 14,
      fontFamily: 'Consolas, "Courier New", monospace',
      theme: {
        background: '#0d0d0d',
        foreground: '#e0e0e0',
      },
      cursorBlink: true,
      cursorStyle: 'underline',
      scrollback: 10000,
    });
    
    const fitAddon = new FitAddon();
    terminal.loadAddon(fitAddon);
    
    // 附加到 DOM
    const terminalElement = document.getElementById(`terminal-${session.id}`);
    if (!terminalElement) {
      throw new Error(`终端元素 #terminal-${session.id} 未找到`);
    }
    
    terminal.open(terminalElement);
    fitAddon.fit();
    
    // 初始化 WebSocket 连接
    // 1. 获取基础 Host
    const envHost = (import.meta.env.VITE_API_HOST as string) || '';
    let proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    let backendHost = window.location.host;
    
    if (envHost) {
      const normalized = envHost.replace(/\/+$/, '');
      if (/^https?:\/\//.test(normalized)) {
        proto = normalized.startsWith('https://') ? 'wss' : 'ws';
        backendHost = normalized.replace(/^https?:\/\//, '');
      } else {
        backendHost = normalized;
      }
    }

    // 2. 获取 Token (非常重要，否则后端会拒绝连接)
    const token = localStorage.getItem('access_token') || '';

    // 3. 构建 URL：恢复使用查询参数模式，保持与后端一致
    // 注意：这里使用 session.id 作为 client_id
    const wsUrl = `${proto}://${backendHost}/ws/terminal?client_id=${session.id}&token=${token}`;
    
    console.log('正在连接 WebSocket:', wsUrl);
    const socket = new WebSocket(wsUrl);
    
    // WebSocket 回调
    socket.onopen = () => {
      session.status = 'connected';
      console.log(`[Session ${session.id}] WebSocket 连接已建立`);
      
      // 发送连接信息
      socket.send(JSON.stringify({
        type: 'connect',
        connection_id: connection.id,
        session_id: session.id
      }));
      
      // 启动延迟检测
      startSessionLatencyCheck(session);
    };
    
    socket.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        switch (msg.type) {
          case 'output':  // 匹配后端 read_ssh_output 逻辑
            if (msg.data) {
              terminal.write(msg.data);
              session.recentTerminalOutput += msg.data;
              // 限制长度防止内存溢出
              if (session.recentTerminalOutput.length > 5000) {
                session.recentTerminalOutput = session.recentTerminalOutput.slice(-5000);
              }
            }
            break;
          case 'command_finished': // 匹配后端 monitor 逻辑
            session.interactiveState = null;
            onCommandFinished(session, msg.output || '');
            break;
          case 'interactive_detected':
            session.interactiveState = msg.interactive_type;
            session.interactiveHint = msg.hint || { message: '检测到交互式程序', actions: [] };
            break;
          case 'connected':
            session.status = 'connected';
            terminal.writeln(`\r\n\x1b[32m[已连接: ${msg.content} ]\x1b[0m\r\n`);
            break;
          case 'error':
            terminal.writeln(`\r\n\x1b[31m[错误: ${msg.content} ]\x1b[0m`);
            ElMessage.error(msg.content);
            if (session.isWaitingCommandFinish) {
              onCommandFinished(session, msg.content || '');
            }
            break;
          case 'pong':
            session.status = 'connected'; // 收到心跳，确认连接正常
            session.wsLatency = Date.now() - (msg.timestamp || Date.now());
            break;
          case 'disconnected':
            terminal.writeln(`\r\n\x1b[31m[SSH会话结束]\x1b[0m`);
            session.status = 'disconnected';
            break;
          case 'ai_suggestion':
            session.aiSuggestedCommand = msg.command;
            session.showCommandConfirm = true;
            break;
        }
      } catch {
        // 非 JSON 格式直接输出
        terminal.write(ev.data);
      }
    };
    
    socket.onclose = () => {
      session.status = 'disconnected';
      console.log(`[Session ${session.id}] WebSocket 连接已关闭`);
    };
    
    socket.onerror = (error) => {
      session.status = 'disconnected';
      ElMessage.error(`${session.displayName} 连接错误`);
      console.error(`[Session ${session.id}] WebSocket 错误:`, error);
    };
    
    // 终端输入处理 (用户直接在黑框输入时)
    terminal.onData((data) => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({
          type: 'data', // 必须改成 data，后端才认识
          data: data,
          session_id: session.id
        }));
      }
    });
    
    // 调整大小处理
    window.addEventListener('resize', () => {
      fitAddon.fit();
    });
    
    // 更新会话状态
    session.terminal = terminal;
    session.fitAddon = fitAddon;
    session.socket = socket;
    
  } catch (e) {
    console.error('终端初始化失败:', e);
    session.status = 'disconnected';
    ElMessage.error(`终端初始化失败: ${(e as Error).message}`);
  }
};

/**
 * 处理用户输入提交 - 智能分流核心
 */
const handleUserSubmit = async (sessionId: string) => {
  const session = sessions.value.find(s => s.id === sessionId);
  if (!session) return;
  
  const input = session.userInputText.trim();
  if (!input) return;
  session.userInputText = ''; // 清空输入框

  // 1. 终端回显（让用户知道自己发了什么）
  session.terminal?.write(`\r\n\x1b[37;1m${session.promptPrefix}\x1b[0m ${input}`);
  
  // 2. 添加到历史记录
  session.history.push({ role: 'user', content: input });

  // 3. 智能判断：是命令还是自然语言？
  const isExplicitCommand = /^[a-zA-Z0-9_\-\.\/]+(\s+[a-zA-Z0-9_\-\.\/]+)*$/.test(input) && !/[\u4e00-\u9fa5]/.test(input);
  
  // 4. 分流处理
  if (isExplicitCommand) {
    // 路径 A: 看起来像命令 (e.g. "ls -la", "cd /var/log")
    // 直接发送给终端执行，不经过 AI，也不需要监视（除非你想让 AI 分析结果）
    // 如果你希望 AI 分析所有命令的结果，这里调用 sendCommandToTerminal
    // 如果只是普通执行，直接 socket.send
    
    // 这里我们选择：直接执行，不打扰 AI
    if (session.socket && session.socket.readyState === WebSocket.OPEN) {
        session.socket.send(JSON.stringify({
            type: 'data',
            data: input + '\n',
            session_id: session.id
        }));
    }
  } else {
    // 路径 B: 自然语言 (e.g. "查看内存占用", "怎么解压这个文件")
    // 发送给 AI，让 AI 建议命令
    await processWithAI(session, input);
  }
};

/**
 * 用户确认执行 AI 建议的命令
 */
const confirmExecute = async () => {
  // 获取当前激活的 session
  const session = sessions.value.find(s => s.id === activeSessionId.value);
  if (!session || !session.aiSuggestedCommand) return;

  const cmd = session.aiSuggestedCommand;
  
  // 1. 关闭确认框
  session.showCommandConfirm = false;
  session.isEditingCommand = false;

  // 2. 发送命令并开启监视 (复用之前的 sendCommandToTerminal)
  // 这里必须用 sendCommandToTerminal，因为我们需要后端在执行完后通知我们
  sendCommandToTerminal(session, cmd);

  // 3. 清空暂存
  session.aiSuggestedCommand = '';
};

/**
 * 进入命令编辑模式
 * @param sessionId 会话ID
 */
const enterEditMode = (sessionId: string) => {
  const session = sessions.value.find(s => s.id === sessionId);
  if (!session) return;
  
  session.isEditingCommand = true;
  session.editableCommand = session.aiSuggestedCommand;
};

/**
 * 确认编辑后的命令
 * @param sessionId 会话ID
 */
const confirmEditedCommand = (sessionId: string) => {
  const session = sessions.value.find(s => s.id === sessionId);
  if (!session) return;
  
  if (session.socket && session.socket.readyState === WebSocket.OPEN) {
    session.socket.send(JSON.stringify({
      type: 'execute_command',
      command: session.editableCommand,
      session_id: session.id
    }));
    session.showCommandConfirm = false;
    session.isEditingCommand = false;
    session.isWaitingCommandFinish = true;
    session.waitingStartTime = Date.now();
    session.waitingElapsed = 0;
    
    // 启动等待计时器
    if (session.waitingTimer) {
      clearInterval(session.waitingTimer);
    }
    session.waitingTimer = setInterval(() => {
      session.waitingElapsed = Math.floor((Date.now() - session.waitingStartTime) / 1000);
    }, 1000);
  }
};

/**
 * 取消编辑命令
 * @param sessionId 会话ID
 */
const cancelEditCommand = (sessionId: string) => {
  const session = sessions.value.find(s => s.id === sessionId);
  if (!session) return;
  
  session.isEditingCommand = false;
  session.showCommandConfirm = false;
};

/**
 * 拒绝执行命令
 * @param sessionId 会话ID
 */
const rejectCommand = (sessionId: string) => {
  const session = sessions.value.find(s => s.id === sessionId);
  if (!session) return;
  
  session.showCommandConfirm = false;
};

/**
 * 执行 AI 建议的命令
 * @param sessionId 会话ID
 */
const confirmAICommand = (sessionId: string) => {
  const session = sessions.value.find(s => s.id === sessionId);
  if (!session) return;
  
  const cmd = session.aiSuggestedCommand;
  if (!cmd) return;
  
  session.showCommandConfirm = false;
  // 记录这是 AI 触发的命令，以便执行完后自动反馈
  session.lastAICommand = cmd;
  
  // 发送给后端执行
  sendCommandToTerminal(session, cmd);
};

/**
 * 封装统一的发送函数
 * @param session 终端会话对象
 * @param command 命令内容
 */
const sendCommandToTerminal = (session: TerminalSession, command: string) => {
  if (session.socket && session.socket.readyState === WebSocket.OPEN) {
    // 1. 必须先开启监视模式
    session.socket.send(JSON.stringify({ type: 'watch_command' }));
    
    // 2. 发送实际指令 (类型必须是 data)
    session.socket.send(JSON.stringify({
      type: 'data',
      data: command + '\n',
      session_id: session.id
    }));

    // 3. 进入等待状态，此时 UI 显示“命令执行中...”
    session.isWaitingCommandFinish = true;
    session.waitingStartTime = Date.now();
    session.waitingElapsed = 0;
    session.lastAICommand = command; // 记录这个命令，等会要喂给 AI
    
    // 启动等待计时器
    if (session.waitingTimer) {
      clearInterval(session.waitingTimer);
    }
    session.waitingTimer = setInterval(() => {
      session.waitingElapsed = Math.floor((Date.now() - session.waitingStartTime) / 1000);
    }, 1000);
  }
};

/**
 * 发送交互输入
 * @param sessionId 会话ID
 * @param input 输入内容
 */
const sendInteractiveInput = (sessionId: string, input: string) => {
  const session = sessions.value.find(s => s.id === sessionId);
  if (!session) return;
  
  if (session.socket && session.socket.readyState === WebSocket.OPEN) {
    session.socket.send(JSON.stringify({
      type: 'interactive_input',
      input: input,
      session_id: session.id
    }));
    session.interactiveState = null;
  }
};

/**
 * 发送自定义交互输入
 * @param sessionId 会话ID
 */
const sendCustomInteractiveInput = (sessionId: string) => {
  const session = sessions.value.find(s => s.id === sessionId);
  if (!session) return;
  
  const input = session.customInteractiveInput.trim();
  if (input) {
    sendInteractiveInput(sessionId, input);
    session.customInteractiveInput = '';
  }
};

/**
 * 发送 Ctrl+C
 * @param sessionId 会话ID
 */
const sendCtrlC = (sessionId: string) => {
  const session = sessions.value.find(s => s.id === sessionId);
  if (!session) return;
  
  sendInteractiveInput(sessionId, '\x03');
};

/**
 * 强制停止等待
 * @param sessionId 会话ID
 */
const forceStopWaiting = (sessionId: string) => {
  const session = sessions.value.find(s => s.id === sessionId);
  if (!session) return;
  
  session.isWaitingCommandFinish = false;
  if (session.waitingTimer) {
    clearInterval(session.waitingTimer);
    session.waitingTimer = null;
  }
};

/**
 * 保存聊天消息到后端
 * 修复：增加全局 try-catch，确保绝对不会抛出异常阻断主流程
 * @param messageData 消息对象
 */
const saveChatMessage = async (messageData: any) => {
  try {
    const token = localStorage.getItem('access_token');
    if (!token) return;
    
    // 获取当前会话ID
    const session = activeSession.value;
    if (!session || !session.currentSessionId) return;
    
    // 使用正确的接口路径：/api/chat-history/sessions/{session_id}/messages
    await http.post(`/api/chat-history/sessions/${session.currentSessionId}/messages`, messageData, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
  } catch (error) {
    // 关键点：这里只打印警告，绝对不要 throw error
    console.warn('非关键错误：保存聊天记录失败 (接口可能未就绪)，不影响 AI 运行。', error);
  }
};

/**
 * 解码Unicode转义字符
 */
const decodeUnicode = (str: string): string => {
  try {
    // 先将字符串作为JSON解析，这样会自动解码Unicode转义字符
    return JSON.parse(`"${str}"`);
  } catch {
    // 如果解析失败，返回原字符串
    return str;
  }
};

/**
 * 解析AI响应（JSON格式）
 */
const parseAIResponse = (content: string): { explanation: string, command: string, needs_more_info: boolean } => {
  try {
    // 首先尝试将整个content作为JSON解析
    try {
      const parsed = JSON.parse(content);
      return {
        explanation: decodeUnicode(parsed.explanation || ''),
        command: decodeUnicode(parsed.command || ''),
        needs_more_info: parsed.needs_more_info || false
      };
    } catch {
      // 如果整个content不是有效的JSON，尝试提取JSON部分
      const jsonMatch = content.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[0]);
        return {
          explanation: decodeUnicode(parsed.explanation || ''),
          command: decodeUnicode(parsed.command || ''),
          needs_more_info: parsed.needs_more_info || false
        };
      }
    }
  } catch (e) {
    console.error('解析AI响应失败:', e);
    // JSON解析失败，尝试文本解析
  }
  
  // 回退：按行解析
  const lines = content.split('\n').filter(l => l.trim());
  const commandLine = lines.find(l => l.startsWith('command:') || l.startsWith('Command:'));
  const explanationLines = lines.filter(l => !l.startsWith('command:') && !l.startsWith('Command:'));
  
  return {
    explanation: decodeUnicode(explanationLines.join('\n')),
    command: decodeUnicode(commandLine ? commandLine.replace(/^command:/i, '').trim() : ''),
    needs_more_info: false
  };
};

// ==================== 核心修复：AI 响应处理 ====================
/**
 * 调用 AI 接口 - 修复流式 JSON 解析问题
 */
const processWithAI = async (session: TerminalSession, input: string) => {
  session.isProcessingAI = true;
  
  // 用于累积 AI 返回的完整字符串
  let fullContent = '';
  
  try {
    const token = localStorage.getItem('access_token');
    
    // 构造系统提示词
    const connInfo = connections.value.find(c => c.id === session.connectionId);
    const systemPrompt = `你是一个专业的Linux服务器运维助手。
主机: ${connInfo?.host || '未知'}
用户: ${connInfo?.username || '未知'}
最近终端输出:
\`\`\`
${session.recentTerminalOutput.slice(-1000)}
\`\`\`
回复必须是严格的JSON格式，不要包含Markdown代码块标记: {"explanation": "你的解释...", "command": "ls -la"}`;

    const response = await fetch('/api/llm/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        prompt: input,
        system_prompt: systemPrompt,
        conversation_history: session.history
      })
    });

    if (!response.ok) throw new Error(`AI 接口异常: ${response.status}`);

    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    
    // 显示 AI 正在思考的提示
    session.terminal?.write(`\r\n\x1b[36m[AI]: 正在分析...\x1b[0m`);

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');
      
      for (const line of lines) {
        // 过滤 SSE 的 data: 前缀
        if (line.trim().startsWith('data: ')) {
          const contentStr = line.replace('data: ', '').trim();
          if (contentStr === '[DONE]') break;
          
          try {
            // 1. 解析 SSE 的包装层 (例如: {"content": "x"})
            const jsonLine = JSON.parse(contentStr);
            
            // 2. 获取真正的文本片段 (兼容不同的后端返回格式)
            // 根据你的截图，字段名应该是 content
            const token = jsonLine.content || jsonLine.delta?.content || '';
            
            // 3. 拼接到总缓冲区
            fullContent += token;
            
          } catch (e) {
            // 忽略非 JSON 行
          }
        }
      }
    }

    // ========== 循环结束，此时 fullContent 应该是完整的 JSON 字符串 ==========
    console.log('AI 返回的完整内容:', fullContent);

    // 清除"正在分析..."的提示行 (将光标移回行首并清除该行)
    session.terminal?.write('\r\x1b[K');

    try {
      // 4. 尝试解析最终的 JSON
      // 有时候 AI 会包裹 ```json ... ```，需要清理一下
      const cleanJson = fullContent.replace(/```json/g, '').replace(/```/g, '').trim();
      const result = JSON.parse(cleanJson);
      
      // 5. 处理解释 (Explanation)
      if (result.explanation) {
        session.history.push({ role: 'assistant', content: result.explanation });
        // 在终端漂亮地显示出来
        session.terminal?.writeln(`\x1b[36m[AI]: ${result.explanation}\x1b[0m`);
      }
      
      // 6. 处理命令 (Command)
      if (result.command) {
        session.lastAICommand = result.command;
        session.aiSuggestedCommand = result.command;
        session.showCommandConfirm = true; // 弹出确认框
        
        session.terminal?.writeln(`\r\n\x1b[33m[AI 建议]: ${result.command}\x1b[0m`);
        session.terminal?.writeln(`\x1b[90m(请在下方确认或修改命令)\x1b[0m\r\n`);
      } else {
        // 如果 AI 没给命令，说明可能是纯问答
        if (!result.explanation) {
            // 如果 JSON 解析了但没内容，可能是格式不对，把原始内容打出来作为兜底
            session.terminal?.writeln(`\x1b[36m[AI]: ${fullContent}\x1b[0m`);
        }
      }

    } catch (parseError) {
      console.error('JSON 解析失败，AI 可能返回了纯文本:', parseError);
      // 兜底逻辑：如果解析 JSON 失败，就直接当成普通文本显示
      session.history.push({ role: 'assistant', content: fullContent });
      session.terminal?.writeln(`\x1b[36m[AI]: ${fullContent}\x1b[0m\r\n`);
    }

  } catch (e: any) {
    console.error('AI Error:', e);
    session.terminal?.writeln(`\r\n\x1b[31m[错误]: ${e.message}\x1b[0m`);
  } finally {
    session.isProcessingAI = false;
  }
};

/**
 * 命令执行完成回调 - 复刻老代码逻辑
 * @param sessionParam 终端会话对象
 * @param output 命令输出
 */
const onCommandFinished = async (sessionParam: TerminalSession, output: string) => {
  // 1. 【解决响应性丢失】重新从源头获取 session 对象
  const session = sessions.value.find(s => s.id === sessionParam.id);
  if (!session) return;

  console.log(`[Session ${session.id}] 命令执行完成`);

  // 2. 【回归老代码逻辑】第一件事：无条件清除等待状态
  // 无论后面发生什么，界面必须先恢复
  session.isWaitingCommandFinish = false;
  if (session.waitingTimer) {
    clearInterval(session.waitingTimer);
    session.waitingTimer = null;
  }

  // 3. 更新输出
  session.recentTerminalOutput = output || session.recentTerminalOutput;
  const cmd = session.lastAICommand;

  // 4. 【异步隔离】保存历史 (不使用 await，避免 404 阻塞)
  if (cmd) {
    saveChatMessage({
      role: 'output',
      content: output.slice(-4000),
      command: cmd,
      command_status: 'executed',
      session_id: session.currentSessionId
    }).catch(e => console.warn('历史保存失败(忽略)', e));
  }

  // 5. 【状态切换】如果是 Agent 模式，开启 AI 状态
  if (cmd && session.agentMode) {
    // 立即开启 AI 状态，让用户看到"AI 正在分析..."
    session.isProcessingAI = true;

    const resultMessage = `命令 \`${cmd}\` 已执行完成，输出如下：\n\`\`\`\n${output.slice(-2000)}\n\`\`\`\n请分析结果并决定下一步。`;
    
    // 添加用户消息到历史
    session.history.push({ role: 'user', content: resultMessage });

    // 调用 AI (这里内部有 try-catch，不会崩)
    await processWithAI(session, resultMessage);
    
    // 清理命令记录
    session.lastAICommand = '';
  } else {
    // 普通模式，打印完成标记
    session.terminal?.writeln('\r\n\x1b[90m[执行完成]\x1b[0m\r\n');
  }
};

/**
 * 处理服务器列表点击 (工作台左侧列表)
 */
const handleServerClick = (connection: any) => {
  // 查找是否已经打开了属于该 connection 的会话
  const existingSession = sessions.value.find(s => s.connectionId === connection.id);
  
  if (existingSession) {
    // 如果已打开，直接切换 activeId
    activeSessionId.value = existingSession.id;
  } else {
    // 没打开过，才执行新建
    createNewSession(connection);
  }
};

/**
 * 连接到服务器（保持兼容）
 * @param connection 连接信息
 */
const connectToServer = (connection: any) => {
  // 调用新的处理函数
  handleServerClick(connection);
};

/**
 * 重新连接会话
 * @param session 终端会话对象
 */
const reconnectSession = async (session: TerminalSession) => {
  if (session.socket) {
    session.socket.close();
  }
  const connection = connections.value.find(c => c.id === session.connectionId);
  if (connection) {
    await initSessionTerminal(session, connection);
  }
};

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

// ==================== 标签页样式 ====================
.terminal-tabs {
  display: flex;
  background: #1a1a2e;
  border-bottom: 1px solid #2a2a4a;
  padding: 5px 10px 0;
  gap: 4px;
  overflow-x: auto;
  flex-shrink: 0;

  .tab-item {
    display: flex;
    align-items: center;
    padding: 6px 15px;
    background: #2a2a40;
    color: #909399;
    border-radius: 4px 4px 0 0;
    cursor: pointer;
    font-size: 13px;
    transition: all 0.3s;
    position: relative;
    min-width: 120px;
    white-space: nowrap;

    &.active {
      background: #0a0a0f;
      color: #fff;
    }

    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      margin-right: 8px;
      flex-shrink: 0;
      display: inline-block;
      background: #909399; // 默认灰色
      
      &.connected {
        background: #67c23a;
        box-shadow: 0 0 5px #67c23a;
      }
      &.connecting {
        background: #e6a23c;
        animation: blink 1s infinite;
      }
      &.disconnected {
        background: #f56c6c;
      }
    }

    @keyframes blink {
      50% { opacity: 0.5; }
    }

    .tab-name {
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .close-icon {
      margin-left: 8px;
      border-radius: 50%;
      padding: 2px;
      flex-shrink: 0;
      
      &:hover {
        background: rgba(255,255,255,0.2);
      }
    }
  }
}

// ==================== 终端容器样式 ====================
.terminal-container {
  flex: 1;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  
  .terminal-instance-wrapper {
    height: 100%;
    display: flex;
    flex-direction: column;
  }
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

/* Shell模式下的样式 */
.shell-mode {
  background: #16162a;
  border-top: 1px solid #2a2a4a;
  padding: 8px 12px;
}

/* 确保在shell模式下，终端占满屏幕 */
.terminal-instance-wrapper {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.terminal-instance-wrapper > .terminal-header {
  flex-shrink: 0;
}

.terminal-instance-wrapper > .terminal-wrapper {
  flex: 1;
}

.terminal-instance-wrapper > .terminal-bottom-bar {
  flex-shrink: 0;
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
  z-index: 1000;
  position: relative;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
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
