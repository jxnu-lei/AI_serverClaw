<template>
  <div class="workspace-container">
    <!-- 侧边栏：连接管理 -->
    <aside class="sidebar" :class="{ collapsed: isSidebarCollapsed }">
      <div class="sidebar-header">
        <div class="sidebar-header-left">
          <h3>服务器</h3>
          <el-button
            type="text"
            size="small"
            @click="toggleSidebar"
            class="sidebar-toggle"
            :class="{ collapsed: isSidebarCollapsed }"
          >
            <template #icon>
              <el-icon v-if="isSidebarCollapsed">
                <svg viewBox="0 0 1024 1024" width="16" height="16" fill="currentColor">
                  <path d="M768 192l-256 256 256 256z" />
                  <path d="M768 192l-256 256 256 256z" />
                </svg>
              </el-icon>
              <ArrowLeft v-else />
            </template>
          </el-button>
        </div>
        <el-button type="primary" size="small" @click="openAddConnectionDialog" :icon="Plus">
          添加
        </el-button>
      </div>

      <div class="connections-list">
        <div class="loading-wrapper" v-if="loadingConnections">
          <el-skeleton :rows="3" animated />
        </div>
        <div v-else>
          <div
            v-for="conn in connections"
            :key="conn.id"
            class="conn-item"
            :class="{ active: hasTabForConnection(conn.id) }"
            @click="connectToServer(conn)"
          >
            <div class="conn-info">
              <el-icon class="conn-icon"><Monitor /></el-icon>
              <div class="conn-details">
                <span class="conn-name">{{ conn.name }}</span>
                <span class="conn-host">{{ conn.host }}</span>
              </div>
            </div>
            <div class="conn-actions" @click.stop>
              <!-- 新增：在同一连接上再开一个终端 -->
              <el-tooltip content="新开终端" placement="top" :show-after="500">
                <el-icon @click="openNewTab(conn)" class="action-icon add-icon"><Plus /></el-icon>
              </el-tooltip>
              <el-tooltip content="编辑" placement="top" :show-after="500">
                <el-icon @click="editConnection(conn)" class="action-icon"><Edit /></el-icon>
              </el-tooltip>
              <el-tooltip content="删除" placement="top" :show-after="500">
                <el-icon @click="deleteConnection(conn.id)" class="action-icon delete-icon"><Delete /></el-icon>
              </el-tooltip>
            </div>
            <!-- 连接状态指示（如果有此连接的标签） -->
            <div class="conn-status" v-if="hasTabForConnection(conn.id)">
              <span class="status-dot" :class="getConnectionStatusClass(conn.id)"></span>
            </div>
          </div>

          <el-empty v-if="connections.length === 0" description="暂无连接" :image-size="60" />
        </div>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="terminal-main">
      <!-- 终端标签栏 -->
      <div class="terminal-tabs" v-if="tabs.length > 0">
        <div
          v-for="tab in tabs"
          :key="tab.id"
          class="tab-item"
          :class="{ active: tab.id === activeTabId }"
          @click="switchTab(tab.id)"
        >
          <span class="tab-status-dot" :class="getTabStatusClass(tab)"></span>
          <span class="tab-name">{{ tab.name }}</span>
          <span class="tab-index" v-if="getTabCountForConnection(tab.connectionId) > 1">
            #{{ getTabIndexForConnection(tab) }}
          </span>
          <el-icon class="tab-close" @click.stop="closeTab(tab.id)"><Close /></el-icon>
        </div>
        <div class="tab-add" @click.stop="toggleNewTabMenu">
          <el-icon><Plus /></el-icon>
        </div>
        <!-- 新标签菜单 -->
        <div class="new-tab-menu" v-if="showNewTabMenu" ref="newTabMenuRef">
          <div
            v-for="conn in connections"
            :key="conn.id"
            class="menu-item"
            @click="openNewTab(conn); showNewTabMenu = false"
          >
            <el-icon><Monitor /></el-icon>
            <span>{{ conn.name }} ({{ conn.host }})</span>
          </div>
          <el-empty v-if="connections.length === 0" description="暂无连接" :image-size="40" />
        </div>
      </div>

      <!-- 未连接时的欢迎界面 -->
      <div class="welcome-panel" v-if="tabs.length === 0">
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

      <!-- 终端面板 - 每个tab一个，用v-show保持DOM不销毁 -->
      <div
        v-for="tab in tabs"
        :key="tab.id"
        class="terminal-panel"
        v-show="tab.id === activeTabId"
      >
        <div class="terminal-header">
          <div class="terminal-info">
            <span class="server-name">{{ tab.name }}</span>
            <el-tag size="small" :type="getStatusTagType(tab)">
              {{ getStatusText(tab) }}
            </el-tag>
            <el-tag size="small" :type="tab.agentMode ? 'success' : 'info'">
              {{ tab.agentMode ? 'Agent' : 'Shell' }}
            </el-tag>
            <el-tag size="small" type="info" v-if="tab.connectionStatus === 'connected'">{{ tab.wsLatency }}ms</el-tag>
          </div>
          <div class="terminal-controls">
            <el-switch
              v-model="tab.agentMode"
              active-text="Agent"
              inactive-text="Shell"
              size="small"
            />
            <el-button
              v-if="tab.connectionStatus === 'disconnected'"
              type="warning"
              size="small"
              @click="reconnectTab(tab)"
            >
              <el-icon><RefreshRight /></el-icon>
              重连
            </el-button>
            <el-button type="danger" size="small" @click="closeTab(tab.id)">
              断开
            </el-button>
          </div>
        </div>

        <!-- 连接状态提示 -->
        <div class="status-banner connecting" v-if="tab.connectionStatus === 'connecting'">
          <el-icon class="rotating"><Loading /></el-icon>
          <span>{{ tab.statusMessage || '正在连接...' }}</span>
        </div>
        <div class="status-banner error" v-if="tab.connectionStatus === 'disconnected' && tab.errorMessage">
          <el-icon><WarningFilled /></el-icon>
          <span>{{ tab.errorMessage }}</span>
          <el-button size="small" type="warning" @click="reconnectTab(tab)">重连</el-button>
        </div>

        <!-- 终端容器 -->
        <div class="terminal-container" :ref="(el) => setTerminalRef(tab.id, el as HTMLElement)"></div>

        <!-- 等待指示器 -->
        <div class="waiting-indicator" v-if="tab.isWaitingCommandFinish && !tab.showCommandConfirm">
          <el-icon class="rotating"><Loading /></el-icon>
          <span>等待命令执行完成...</span>
          <span class="waiting-time">{{ formatWaitingTime(tab) }}</span>
          <el-button size="small" type="warning" @click="forceStopWaiting(tab)">强制结束</el-button>
        </div>

        <!-- 交互式提示 -->
        <div class="interactive-hint" v-if="tab.interactiveHint?.message">
          <el-alert :title="tab.interactiveHint.message" type="warning" :closable="false" show-icon>
            <template #default>
              <div class="hint-actions">
                <el-button
                  v-for="action in tab.interactiveHint.actions"
                  :key="action.label"
                  size="small"
                  @click="sendInteractiveAction(tab, action.data)"
                >
                  {{ action.label }}
                </el-button>
              </div>
            </template>
          </el-alert>
        </div>

        <!-- 命令确认框 -->
        <div class="command-confirm" v-if="tab.showCommandConfirm">
          <div class="confirm-header">
            <el-icon><WarningFilled /></el-icon>
            <span>是否同意执行以下命令？</span>
          </div>
          <div class="confirm-command">
            <code>{{ tab.aiSuggestedCommand }}</code>
          </div>
          <div class="confirm-actions">
            <el-button type="primary" size="small" @click="confirmCommand(tab)">
              <el-icon><Check /></el-icon> 执行
            </el-button>
            <el-button size="small" @click="rejectCommand(tab)">
              <el-icon><Close /></el-icon> 拒绝
            </el-button>
          </div>
        </div>

        <!-- 输入框 -->
        <div class="input-bar" v-if="tab.agentMode">
          <el-input
            v-model="tab.userInputText"
            :placeholder="'输入自然语言指令或直接命令...'"
            @keyup.enter="handleUserSubmit(tab)"
            :disabled="tab.isProcessingAI"
            clearable
          >
            <template #prefix>
              <el-icon><Promotion /></el-icon>
            </template>
            <template #append>
              <el-button
                @click="handleUserSubmit(tab)"
                :loading="tab.isProcessingAI"
                type="primary"
              >
                发送
              </el-button>
            </template>
          </el-input>
        </div>
      </div>
    </main>

    <!-- 添加/编辑连接对话框 -->
    <el-dialog
      v-model="showConnectionDialog"
      :title="editingConnection ? '编辑连接' : '添加连接'"
      width="520px"
      :close-on-click-modal="false"
    >
      <el-form :model="connectionForm" :rules="connectionRules" ref="connectionFormRef" label-width="100px">
        <el-form-item label="连接名称" prop="name">
          <el-input v-model="connectionForm.name" placeholder="例：生产服务器" />
        </el-form-item>
        <el-form-item label="主机地址" prop="host">
          <el-input v-model="connectionForm.host" placeholder="例：192.168.1.100" />
        </el-form-item>
        <el-form-item label="端口" prop="port">
          <el-input-number v-model="connectionForm.port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="用户名" prop="username">
          <el-input v-model="connectionForm.username" placeholder="例：root" />
        </el-form-item>
        <el-form-item label="认证方式" prop="auth_method">
          <el-radio-group v-model="connectionForm.auth_method">
            <el-radio value="password">密码</el-radio>
            <el-radio value="private_key">私钥</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="connectionForm.auth_method === 'password'" label="密码" prop="password">
          <el-input v-model="connectionForm.password" type="password" show-password placeholder="输入密码" />
        </el-form-item>
        <el-form-item v-if="connectionForm.auth_method === 'private_key'" label="私钥" prop="private_key">
          <el-input v-model="connectionForm.private_key" type="textarea" :rows="4" placeholder="粘贴私钥内容" />
        </el-form-item>
        <el-form-item v-if="connectionForm.auth_method === 'private_key'" label="密钥密码">
          <el-input v-model="connectionForm.passphrase" type="password" show-password placeholder="私钥密码（可选）" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="connectionForm.description" type="textarea" :rows="2" placeholder="连接描述（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showConnectionDialog = false">取消</el-button>
        <el-button type="info" @click="testConnectionClick" :loading="testingConnection">测试连接</el-button>
        <el-button type="primary" @click="saveConnection" :loading="savingConnection">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount, onActivated, onDeactivated, nextTick, watch, computed } from 'vue'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { WebLinksAddon } from '@xterm/addon-web-links'
import '@xterm/xterm/css/xterm.css'
import {
  Monitor, Plus, Edit, Delete, Close, Check, Promotion,
  WarningFilled, Loading, RefreshRight, ArrowLeft, ArrowRight
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '@/utils/http'

// 声明组件名称，供 keep-alive 使用
defineOptions({
  name: 'WorkspaceView'
})

// ==================== 类型定义 ====================
interface ServerConnection {
  id: string
  name: string
  host: string
  port: number
  username: string
  auth_method: string
  description?: string
  tags?: string
}

interface TerminalTab {
  id: string
  name: string
  connectionId: string
  connection: ServerConnection
  terminal: Terminal | null
  fitAddon: FitAddon | null
  ws: WebSocket | null
  clientId: string
  connectionStatus: 'connecting' | 'connected' | 'disconnected'
  statusMessage: string
  errorMessage: string
  wsLatency: number
  agentMode: boolean
  isProcessingAI: boolean
  conversationHistory: { role: string; content: string }[]
  currentSessionId: string | null
  recentTerminalOutput: string
  aiSuggestedCommand: string
  lastAICommand: string
  showCommandConfirm: boolean
  userInputText: string
  isWaitingCommandFinish: boolean
  waitingStartTime: number
  waitingTimer: ReturnType<typeof setInterval> | null
  interactiveState: string | null
  interactiveHint: { message: string; actions: { label: string; data: string }[] }
  isManualCommand?: boolean
}

// ==================== 连接管理状态 ====================
const connections = ref<ServerConnection[]>([])
const loadingConnections = ref(false)
const showConnectionDialog = ref(false)
const editingConnection = ref<ServerConnection | null>(null)
const connectionFormRef = ref()
const testingConnection = ref(false)
const savingConnection = ref(false)

const connectionForm = reactive({
  name: '',
  host: '',
  port: 22,
  username: 'root',
  auth_method: 'password',
  password: '',
  private_key: '',
  passphrase: '',
  description: '',
  tags: '',
})

const connectionRules = {
  name: [{ required: true, message: '请输入连接名称', trigger: 'blur' }],
  host: [{ required: true, message: '请输入主机地址', trigger: 'blur' }],
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
}

// ==================== 多标签终端管理 ====================
const tabs = ref<TerminalTab[]>([])
const activeTabId = ref<string | null>(null)
const showNewTabMenu = ref(false)
const newTabMenuRef = ref<HTMLElement | null>(null)
const terminalRefs = ref<Record<string, HTMLElement | null>>({})

// ==================== 侧边栏管理 ====================
const isSidebarCollapsed = ref(false)

const toggleSidebar = () => {
  isSidebarCollapsed.value = !isSidebarCollapsed.value
}

// 命令预处理
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

// 计算属性
const activeTab = computed(() => tabs.value.find(t => t.id === activeTabId.value) || null)

// ==================== 辅助函数 ====================
const setTerminalRef = (tabId: string, el: HTMLElement | null) => {
  if (el) {
    terminalRefs.value[tabId] = el
  }
}

const hasTabForConnection = (connId: string) => {
  return tabs.value.some(t => t.connectionId === connId)
}

const getTabCountForConnection = (connId: string) => {
  return tabs.value.filter(t => t.connectionId === connId).length
}

const getTabIndexForConnection = (tab: TerminalTab) => {
  const sameTabs = tabs.value.filter(t => t.connectionId === tab.connectionId)
  return sameTabs.indexOf(tab) + 1
}

const getConnectionStatusClass = (connId: string) => {
  // 找到该连接下状态最好的那个tab
  const relatedTabs = tabs.value.filter(t => t.connectionId === connId)
  const hasConnected = relatedTabs.some(t => t.connectionStatus === 'connected')
  const hasConnecting = relatedTabs.some(t => t.connectionStatus === 'connecting')

  if (hasConnected) return 'status-connected'
  if (hasConnecting) return 'status-connecting'
  return 'status-disconnected'
}

const getTabStatusClass = (tab: TerminalTab) => ({
  'status-connected': tab.connectionStatus === 'connected',
  'status-connecting': tab.connectionStatus === 'connecting',
  'status-disconnected': tab.connectionStatus === 'disconnected',
})

const getStatusTagType = (tab: TerminalTab) => {
  switch (tab.connectionStatus) {
    case 'connected': return 'success'
    case 'connecting': return 'warning'
    case 'disconnected': return 'danger'
    default: return 'info'
  }
}

const getStatusText = (tab: TerminalTab) => {
  switch (tab.connectionStatus) {
    case 'connected': return '已连接'
    case 'connecting': return '连接中...'
    case 'disconnected': return '已断开'
    default: return '未知'
  }
}

const formatWaitingTime = (tab: TerminalTab) => {
  if (!tab.waitingStartTime) return ''
  return `${Math.floor((Date.now() - tab.waitingStartTime) / 1000)}s`
}

const generateTabId = () => `tab-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

// ==================== 新标签菜单 ====================
const toggleNewTabMenu = () => {
  showNewTabMenu.value = !showNewTabMenu.value
}

// 点击外部关闭菜单
const handleDocumentClick = (e: MouseEvent) => {
  if (showNewTabMenu.value && newTabMenuRef.value && !newTabMenuRef.value.contains(e.target as Node)) {
    showNewTabMenu.value = false
  }
}

// ==================== 加载连接 ====================
const loadConnections = async () => {
  loadingConnections.value = true
  try {
    const res = await http.get('/api/connections')
    // http 拦截器已经返回 response.data，所以 res 就是数据
    // 但要兼容两种情况：拦截器解包和未解包
    if (Array.isArray(res)) {
      connections.value = res
    } else if (res?.data && Array.isArray(res.data)) {
      connections.value = res.data
    } else {
      connections.value = []
    }
  } catch (e: any) {
    ElMessage.error('加载连接列表失败')
  } finally {
    loadingConnections.value = false
  }
}

// ==================== 连接CRUD ====================
const openAddConnectionDialog = () => {
  editingConnection.value = null
  Object.assign(connectionForm, {
    name: '', host: '', port: 22, username: 'root',
    auth_method: 'password', password: '', private_key: '',
    passphrase: '', description: '', tags: ''
  })
  showConnectionDialog.value = true
}

const editConnection = (conn: ServerConnection) => {
  editingConnection.value = conn
  Object.assign(connectionForm, {
    name: conn.name, host: conn.host, port: conn.port,
    username: conn.username, auth_method: conn.auth_method || 'password',
    password: '', private_key: '', passphrase: '',
    description: conn.description || '', tags: conn.tags || ''
  })
  showConnectionDialog.value = true
}

const saveConnection = async () => {
  if (!connectionFormRef.value) return
  await connectionFormRef.value.validate()
  savingConnection.value = true
  try {
    const payload = { ...connectionForm }
    if (editingConnection.value) {
      await http.put(`/api/connections/${editingConnection.value.id}`, payload)
      ElMessage.success('连接已更新')
    } else {
      await http.post('/api/connections', payload)
      ElMessage.success('连接已创建')
    }
    showConnectionDialog.value = false
    await loadConnections()
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e?.data?.detail || '保存失败'
    ElMessage.error(detail)
  } finally {
    savingConnection.value = false
  }
}

const deleteConnection = async (connId: string) => {
  try {
    await ElMessageBox.confirm('确定要删除此连接吗？关联的终端标签页也将关闭。', '确认删除', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning'
    })
    const relatedTabs = tabs.value.filter(t => t.connectionId === connId)
    for (const tab of relatedTabs) {
      await doCloseTab(tab.id, false)
    }
    await http.delete(`/api/connections/${connId}`)
    ElMessage.success('连接已删除')
    await loadConnections()
  } catch (e: any) {
    // 用户取消时 e === 'cancel'
    if (e !== 'cancel' && e?.toString() !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const testConnectionClick = async () => {
  testingConnection.value = true
  try {
    await http.post('/api/connections/test', {
      host: connectionForm.host,
      port: connectionForm.port,
      username: connectionForm.username,
      password: connectionForm.password,
      private_key: connectionForm.private_key,
      auth_method: connectionForm.auth_method,
    })
    ElMessage.success('连接测试成功')
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e?.data?.detail || '连接测试失败'
    ElMessage.error(detail)
  } finally {
    testingConnection.value = false
  }
}

// ==================== 终端标签操作 ====================
const connectToServer = (conn: ServerConnection) => {
  // 点击左侧连接列表项时的行为：
  // 如果已有此连接的标签，切换到第一个
  const existing = tabs.value.find(t => t.connectionId === conn.id)
  if (existing) {
    switchTab(existing.id)
    return
  }
  // 否则新建标签
  openNewTab(conn)
}

const openNewTab = async (conn: ServerConnection) => {
  showNewTabMenu.value = false

  const tabId = generateTabId()
  const clientId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

  // 计算标签名（同连接多开时显示序号）
  const sameCount = tabs.value.filter(t => t.connectionId === conn.id).length
  const tabName = sameCount > 0 ? `${conn.name} #${sameCount + 1}` : conn.name

  // 检查是否已经有相同连接的标签存在，如果有，则复用其会话ID
  const existingTabWithSameConnection = tabs.value.find(t => t.connectionId === conn.id);
  const existingSessionId = existingTabWithSameConnection?.currentSessionId || null;

  const newTab: TerminalTab = {
    id: tabId,
    name: tabName,
    connectionId: conn.id,
    connection: conn,
    terminal: null,
    fitAddon: null,
    ws: null,
    clientId,
    connectionStatus: 'connecting',
    statusMessage: '正在初始化...',
    errorMessage: '',
    wsLatency: 0,
    agentMode: false,
    isProcessingAI: false,
    conversationHistory: [],
    currentSessionId: existingSessionId, // 复用已有的会话ID
    recentTerminalOutput: '',
    aiSuggestedCommand: '',
    lastAICommand: '',
    showCommandConfirm: false,
    userInputText: '',
    isWaitingCommandFinish: false,
    waitingStartTime: 0,
    waitingTimer: null,
    interactiveState: null,
    interactiveHint: { message: '', actions: [] },
    isManualCommand: false,
  }

  tabs.value.push(newTab)
  activeTabId.value = tabId

  await nextTick()
  // 等两帧确保DOM完全渲染
  await nextTick()

  initTerminalForTab(newTab)
  connectWebSocket(newTab)
}

const switchTab = (tabId: string) => {
  activeTabId.value = tabId
  nextTick(() => {
    const tab = tabs.value.find(t => t.id === tabId)
    if (tab?.fitAddon && tab.terminal) {
      try {
        tab.fitAddon.fit()
      } catch { /* ignore */ }
    }
  })
}

const closeTab = async (tabId: string) => {
  const tab = tabs.value.find(t => t.id === tabId)
  if (!tab) return

  if (tab.connectionStatus === 'connected') {
    try {
      await ElMessageBox.confirm(
        `确定断开与 ${tab.name} 的连接？`,
        '断开连接',
        { confirmButtonText: '断开', cancelButtonText: '取消', type: 'warning' }
      )
    } catch {
      return
    }
  }

  await doCloseTab(tabId, true)
}

const doCloseTab = async (tabId: string, switchToNext: boolean) => {
  const idx = tabs.value.findIndex(t => t.id === tabId)
  if (idx === -1) return

  const tab = tabs.value[idx]
  
  // 【新增】关闭标签页前，如果还有活跃会话，强制结束
  if (tab.currentSessionId) {
    await endChatSession(tab);
  }
  
  cleanupTab(tab)
  tabs.value.splice(idx, 1)
  delete terminalRefs.value[tabId]

  // 清理心跳定时器
  const timer = tabLatencyTimers.get(tabId)
  if (timer) {
    clearInterval(timer)
    tabLatencyTimers.delete(tabId)
  }

  if (switchToNext && activeTabId.value === tabId) {
    if (tabs.value.length > 0) {
      const newIdx = Math.min(idx, tabs.value.length - 1)
      activeTabId.value = tabs.value[newIdx].id
      nextTick(() => {
        const nt = tabs.value[newIdx]
        if (nt?.fitAddon) {
          try { nt.fitAddon.fit() } catch { /* ignore */ }
        }
      })
    } else {
      activeTabId.value = null
    }
  }

  // 更新同连接的其它标签名序号
  updateTabNamesForConnection(tab.connectionId)
}

const updateTabNamesForConnection = (connId: string) => {
  const sameTabs = tabs.value.filter(t => t.connectionId === connId)
  const conn = connections.value.find(c => c.id === connId)
  if (!conn) return

  if (sameTabs.length === 1) {
    sameTabs[0].name = conn.name
  } else {
    sameTabs.forEach((t, i) => {
      t.name = `${conn.name} #${i + 1}`
    })
  }
}

const cleanupTab = (tab: TerminalTab) => {
  if (tab.ws) {
    try {
      if (tab.ws.readyState === WebSocket.OPEN) {
        tab.ws.send(JSON.stringify({ type: 'disconnect' }))
      }
      tab.ws.close()
    } catch { /* ignore */ }
    tab.ws = null
  }

  if (tab.waitingTimer) {
    clearInterval(tab.waitingTimer)
    tab.waitingTimer = null
  }

  if (tab.terminal) {
    tab.terminal.dispose()
    tab.terminal = null
  }

  tab.fitAddon = null
  tab.connectionStatus = 'disconnected'
}

// ==================== 重连 ====================
const reconnectTab = async (tab: TerminalTab) => {
  cleanupTab(tab)
  tab.connectionStatus = 'connecting'
  tab.statusMessage = '正在重连...'
  tab.errorMessage = ''
  tab.clientId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

  await nextTick()
  initTerminalForTab(tab)
  connectWebSocket(tab)
}

// ==================== 终端初始化 ====================
const initTerminalForTab = (tab: TerminalTab) => {
  const container = terminalRefs.value[tab.id]
  if (!container) {
    console.error('Terminal container not found for tab:', tab.id)
    tab.errorMessage = '终端容器未找到，请刷新页面'
    tab.connectionStatus = 'disconnected'
    return
  }

  if (tab.terminal) {
    tab.terminal.dispose()
  }

  const term = new Terminal({
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

  const fitAddon = new FitAddon()
  term.loadAddon(fitAddon)
  term.loadAddon(new WebLinksAddon())

  term.open(container)

  try {
    fitAddon.fit()
  } catch { /* ignore first fit */ }

  // Shell模式输入处理（包括Tab键补全）
  term.onData((data: string) => {
    // Shell模式下所有输入直接发给后端
    if (!tab.agentMode && tab.ws && tab.ws.readyState === WebSocket.OPEN) {
      tab.ws.send(JSON.stringify({ type: 'data', data }))
    }
  })

  // 二进制数据处理
  term.onBinary((data: string) => {
    if (!tab.agentMode && tab.ws && tab.ws.readyState === WebSocket.OPEN) {
      tab.ws.send(JSON.stringify({ type: 'data', data }))
    }
  })

  tab.terminal = term
  tab.fitAddon = fitAddon
}

// ==================== WebSocket ====================
const connectWebSocket = (tab: TerminalTab) => {
  const token = sessionStorage.getItem('token') || sessionStorage.getItem('access_token')
  if (!token) {
    ElMessage.error('请先登录')
    tab.connectionStatus = 'disconnected'
    tab.errorMessage = '未登录'
    return
  }

  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const backendHost = window.location.host
  const wsUrl = `${proto}://${backendHost}/api/ws/terminal?client_id=${tab.clientId}&token=${token}`

  console.log(`[${tab.id}] Connecting WebSocket: ${wsUrl.replace(token, '***')}`)
  tab.statusMessage = '正在建立WebSocket连接...'

  try {
    tab.ws = new WebSocket(wsUrl)
  } catch (e) {
    console.error('WebSocket creation failed:', e)
    tab.connectionStatus = 'disconnected'
    tab.errorMessage = 'WebSocket创建失败'
    return
  }

  tab.ws.onopen = () => {
    console.log(`[${tab.id}] WebSocket opened, sending connect request`)
    tab.statusMessage = 'WebSocket已连接，正在SSH连接...'

    tab.ws!.send(JSON.stringify({
      type: 'connect',
      connection_id: tab.connectionId
    }))

    startTabLatencyCheck(tab)
  }

  tab.ws.onmessage = (event) => {
    handleTabWsMessage(tab, event)
  }

  tab.ws.onclose = (event) => {
    console.log(`[${tab.id}] WebSocket closed, code=${event.code}, reason=${event.reason}`)
    if (tab.connectionStatus !== 'disconnected') {
      tab.connectionStatus = 'disconnected'
      tab.errorMessage = `WebSocket关闭 (${event.code})`
      tab.terminal?.writeln('\r\n\x1b[31m[WebSocket连接已关闭]\x1b[0m')
      if (tab.isWaitingCommandFinish) stopTabWaiting(tab)
    }
  }

  tab.ws.onerror = (event) => {
    console.error(`[${tab.id}] WebSocket error:`, event)
    tab.connectionStatus = 'disconnected'
    tab.errorMessage = 'WebSocket连接错误'
    tab.terminal?.writeln('\r\n\x1b[31m[WebSocket连接错误]\x1b[0m')
  }
}

// ==================== 消息处理 ====================
const handleTabWsMessage = async (tab: TerminalTab, event: MessageEvent) => {
  try {
    const msg = JSON.parse(event.data)
    console.log('[WS]', tab.id, msg.type, msg.detection || '', msg)

    switch (msg.type) {
      case 'output':
        tab.terminal?.write(msg.data || '')
        tab.recentTerminalOutput += msg.data || ''
        if (tab.recentTerminalOutput.length > 10000) {
          tab.recentTerminalOutput = tab.recentTerminalOutput.slice(-8000)
        }
        break

      case 'connected':
        tab.connectionStatus = 'connected'
        tab.statusMessage = ''
        tab.errorMessage = ''
        tab.terminal?.writeln(`\x1b[32m[${msg.content || '已连接'}]\x1b[0m`)
        
        // 【新增】连接成功，立即创建会话（开始计时）
        await createChatSession(tab);

        // 同步终端尺寸
        nextTick(() => {
          if (tab.fitAddon && tab.ws && tab.ws.readyState === WebSocket.OPEN) {
            try {
              tab.fitAddon.fit()
              const dims = tab.fitAddon.proposeDimensions()
              if (dims) {
                tab.ws.send(JSON.stringify({
                  type: 'resize', cols: dims.cols, rows: dims.rows
                }))
              }
            } catch { /* ignore */ }
          }
        })
        break

      case 'status':
        tab.statusMessage = msg.content || ''
        tab.terminal?.writeln(`\x1b[90m[${msg.content || ''}]\x1b[0m`)
        break

      case 'pong':
        if (msg.timestamp) tab.wsLatency = Math.max(0, Date.now() - msg.timestamp)
        break

      case 'interactive_detected':
        tab.interactiveState = msg.interactive_type || null
        tab.interactiveHint = msg.hint || { message: '', actions: [] }
        break

      case 'command_finished':
        // 无条件收口，避免卡等待
        stopTabWaiting(tab)
        tab.interactiveState = null
        tab.interactiveHint = { message: '', actions: [] }

        // 通知后端停监视（幂等）
        if (tab.ws && tab.ws.readyState === WebSocket.OPEN) {
          tab.ws.send(JSON.stringify({ type: 'stop_watch' }))
        }

        await onTabCommandFinished(tab, msg.output || '')
        break

      case 'connection_lost':
        tab.connectionStatus = 'disconnected'
        tab.errorMessage = msg.content || '连接丢失'
        tab.terminal?.writeln(`\r\n\x1b[31m[${msg.content || '连接丢失'}]\x1b[0m`)
        stopTabWaiting(tab)
        // 新增：连接丢失也算作结束
        await endChatSession(tab)
        if (msg.reconnectable) {
          tab.terminal?.writeln('\x1b[33m[可点击"重连"按钮恢复连接]\x1b[0m')
        }
        break

      case 'status_report':
        if (!msg.ssh_alive && tab.connectionStatus === 'connected') {
          tab.connectionStatus = 'disconnected'
          tab.errorMessage = 'SSH连接已失效'
          tab.terminal?.writeln('\r\n\x1b[31m[SSH连接已失效]\x1b[0m')
          stopTabWaiting(tab)
        }
        break

      case 'error':
        tab.errorMessage = msg.content || '未知错误'
        tab.terminal?.writeln(`\r\n\x1b[31m[错误: ${tab.errorMessage}]\x1b[0m`)
        if (tab.connectionStatus === 'connecting') tab.connectionStatus = 'disconnected'
        break

      case 'disconnected':
        tab.connectionStatus = 'disconnected'
        tab.terminal?.writeln('\r\n\x1b[31m[SSH会话结束]\x1b[0m')
        stopTabWaiting(tab)
        // 新增：结束会话记录时长
        await endChatSession(tab)
        break
    }
  } catch {
    // 非 JSON 直接作为终端输出
    tab.terminal?.write(event.data)
  }
}

// ==================== 心跳 ====================
const tabLatencyTimers = new Map<string, ReturnType<typeof setInterval>>()

const startTabLatencyCheck = (tab: TerminalTab) => {
  const oldTimer = tabLatencyTimers.get(tab.id)
  if (oldTimer) clearInterval(oldTimer)

  const timer = setInterval(() => {
    if (tab.ws && tab.ws.readyState === WebSocket.OPEN) {
      tab.ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }))
    } else {
      clearInterval(timer)
      tabLatencyTimers.delete(tab.id)
    }
  }, 5000)

  tabLatencyTimers.set(tab.id, timer)
}

// ==================== 命令等待 ====================
const startTabWaiting = (tabParam: TerminalTab) => {
  // 同样重新获取响应式对象
  const tab = tabs.value.find(t => t.id === tabParam.id) || tabParam;
  
  tab.isWaitingCommandFinish = true;
  tab.waitingStartTime = Date.now();
  
  if (tab.waitingTimer) clearInterval(tab.waitingTimer);
  
  tab.waitingTimer = setInterval(() => {
    // 强制触发 Vue 更新
    tab.waitingStartTime = tab.waitingStartTime; // 触发响应式更新
  }, 1000);
}

const stopTabWaiting = (tabParam: TerminalTab) => {
  // 同样重新获取响应式对象
  const tab = tabs.value.find(t => t.id === tabParam.id) || tabParam;
  
  tab.isWaitingCommandFinish = false;
  tab.waitingStartTime = 0;
  if (tab.waitingTimer) {
    clearInterval(tab.waitingTimer);
    tab.waitingTimer = null;
  }
  tab.interactiveState = null;
  tab.interactiveHint = { message: '', actions: [] };
}

const forceStopWaiting = (tabParam: TerminalTab) => {
  // 同样重新获取响应式对象
  const tab = tabs.value.find(t => t.id === tabParam.id) || tabParam;
  
  if (tab.ws && tab.ws.readyState === WebSocket.OPEN) {
    tab.ws.send(JSON.stringify({ type: 'stop_watch' }));
  }
  stopTabWaiting(tab);
  tab.lastAICommand = '';
  ElMessage.info('已强制结束等待');
  tab.terminal?.writeln('\x1b[90m[已强制结束命令等待]\x1b[0m');
}

// ==================== 交互式操作 ====================
const sendInteractiveAction = (tab: TerminalTab, data: string) => {
  if (tab.ws && tab.ws.readyState === WebSocket.OPEN) {
    tab.ws.send(JSON.stringify({ type: 'data', data }))
  }
}

// ==================== 发送命令 ====================
const sendTabCommand = (tab: TerminalTab, cmd: string) => {
  if (tab.ws && tab.ws.readyState === WebSocket.OPEN) {
    tab.ws.send(JSON.stringify({ type: 'data', data: cmd + '\r' }))
  }
}

// ==================== AI 相关 ====================
const preprocessCommand = (cmd: string): string => {
  for (const [pattern, replacement] of Object.entries(PAGEBOUND_COMMANDS)) {
    if (cmd.trim().startsWith(pattern)) return replacement
  }
  return cmd
}

const isCommand = (input: string): boolean => {
  // 检查是否包含中文字符，如果包含，更可能是自然语言
  if (/[\u4e00-\u9fa5]/.test(input)) {
    return false
  }
  
  // 检查是否符合命令格式
  const isExplicitCommand = /^[a-zA-Z0-9_\-\.\/]+(\s+[a-zA-Z0-9_\-\.\/]+)*$/.test(input.trim())
  
  // 检查常见命令前缀
  const cmdPrefixes = ['ls', 'cd', 'cat', 'grep', 'find', 'sudo', 'apt', 'yum',
    'docker', 'systemctl', 'service', 'ps', 'kill', 'top', 'df', 'du',
    'mkdir', 'rm', 'cp', 'mv', 'chmod', 'chown', 'wget', 'curl',
    'tar', 'unzip', 'ssh', 'scp', 'ping', 'ifconfig', 'ip', 'netstat',
    'ss', 'iptables', 'ufw', 'vim', 'nano', 'echo', 'export', 'source',
    'npm', 'node', 'python', 'pip', 'git', 'make', 'gcc']
  const firstWord = input.trim().split(/\s+/)[0].toLowerCase()
  
  // 综合判断：命令格式匹配、路径前缀或常见命令前缀
  return isExplicitCommand || input.trim().startsWith('/') || input.trim().startsWith('./') || cmdPrefixes.includes(firstWord)
}

// 辅助函数：解析 JWT Token 获取用户信息
const getUsernameFromStorage = () => {
  // 1. 优先尝试直接获取
  let username = sessionStorage.getItem('username') || sessionStorage.getItem('user_name');
  if (username) return username;

  // 2. 尝试从 user 对象中获取 (很多前端框架习惯存一个 json 对象)
  try {
    const userStr = sessionStorage.getItem('user') || sessionStorage.getItem('userInfo');
    if (userStr) {
      const userObj = JSON.parse(userStr);
      if (userObj.username) return userObj.username;
      if (userObj.name) return userObj.name;
    }
  } catch (e) { /* ignore */ }

  // 3. 【最稳妥】解析 Access Token (JWT)
  try {
    const token = sessionStorage.getItem('access_token') || sessionStorage.getItem('token');
    if (token) {
      // JWT 格式为 header.payload.signature，我们需要 payload (第2部分)
      const payloadPart = token.split('.')[1];
      if (payloadPart) {
        // Base64 解码
        const base64 = payloadPart.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(window.atob(base64).split('').map(function(c) {
            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        }).join(''));
        
        const payload = JSON.parse(jsonPayload);
        // 根据 terminal.py 的逻辑，username 存在 'sub' 字段中
        if (payload.sub) return payload.sub;
        if (payload.username) return payload.username;
      }
    }
  } catch (e) {
    console.warn('解析 Token 获取用户名失败', e);
  }

  return 'Unknown User';
}

const createChatSession = async (tab: TerminalTab) => {
  try {
    // 1. 获取当前登录用户名 (使用增强的获取逻辑)
    const username = getUsernameFromStorage();
    
    // 2. 生成标题: 用户名 - 终端名
    const sessionTitle = `${username} - ${tab.name}`;
    
    // 3. 获取服务器IP
    const serverIp = tab.connection.host;
    
    // 4. 调用创建接口
    const resp = await http.post('/api/chat-history/sessions', {
      connection_id: tab.connectionId,
      title: sessionTitle,
      host: serverIp,
      username: username,
      status: 'active'
    });

    const data = resp?.data || resp;
    tab.currentSessionId = data?.id || null;
    
    console.log(`会话已创建: ${sessionTitle}, ID: ${tab.currentSessionId}`);
  } catch (e: any) {
    // 忽略 404 等错误，避免控制台刷屏
    if (e?.response?.status !== 404) {
      console.warn('创建会话失败:', e);
    }
    tab.currentSessionId = null;
  }
}

// 新增：结束会话函数（计算时长）
const endChatSession = async (tab: TerminalTab) => {
  if (!tab.currentSessionId) return;
  
  const sessionId = tab.currentSessionId;
  // 立即清空 ID 防止重复调用
  tab.currentSessionId = null;

  try {
    // 调用更新接口，设置状态为 completed
    // 后端会根据当前时间自动计算时长
    await http.put(`/api/chat-history/sessions/${sessionId}`, {
      status: 'completed'
    });
    console.log(`会话已结束 (ID: ${sessionId})`);
  } catch (e) {
    console.warn('结束会话失败:', e);
  }
}

/**
 * 保存聊天消息到后端
 * 修复：增加全局 try-catch，确保绝对不会抛出异常阻断主流程
 */
const saveChatMessage = async (tab: TerminalTab, messageData: any) => {
  try {
    if (!tab.currentSessionId) return
    const token = sessionStorage.getItem('access_token') || sessionStorage.getItem('token')
    // 尝试发送请求，如果 404 会进入 catch
    await http.post(`/api/chat-history/sessions/${tab.currentSessionId}/messages`, messageData, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
  } catch (error) {
    // 关键点：这里只打印警告，绝对不要 throw error
    console.warn('非关键错误：保存聊天记录失败 (接口可能未就绪)，不影响 AI 运行。', error)
  }
};

const buildSystemPrompt = (tab: TerminalTab): string => {
  const conn = tab.connection
  return `你是一个专业的Linux服务器运维AI助手。

服务器: ${conn.host} 用户: ${conn.username}

最近输出:
\`\`\`
${tab.recentTerminalOutput.slice(-3000)}
\`\`\`

回复格式（严格JSON）：
{"explanation":"中文解释","command":"shell命令","needs_more_info":false}

规则：每次只返回一条命令，不用sleep，不串联命令，避免交互式模式。任务完成时command为空字符串。`
}

/**
 * 解码Unicode转义字符
 */
const decodeUnicode = (str: string): string => {
  try {
    return JSON.parse(`"${str}"`);
  } catch {
    return str;
  }
};

/**
 * 处理特殊格式的AI响应
 */
const parseSpecialAIResponse = (content: string): string => {
  try {
    const contentMatches = content.match(/\{"content":"[^"]*"\}/g);
    if (contentMatches) {
      return contentMatches.map(match => {
        try {
          const obj = JSON.parse(match);
          return obj.content || '';
        } catch {
          return '';
        }
      }).join('');
    }
  } catch (e) {
    console.error('解析特殊格式失败:', e);
  }
  return content;
};

const parseAIResponse = (text: string): { explanation: string; command: string } => {
  // 先尝试直接 JSON 解析
  try {
    const json = JSON.parse(text.trim())
    return {
      explanation: decodeUnicode(json.explanation || json.message || ''),
      command: decodeUnicode(json.command || json.cmd || '')
    }
  } catch {
    // 尝试提取 JSON 块
  }

  // 尝试从文本中提取 JSON
  const jsonMatch = text.match(/\{[\s\S]*?\}/)
  if (jsonMatch) {
    try {
      const json = JSON.parse(jsonMatch[0])
      return {
        explanation: decodeUnicode(json.explanation || json.message || ''),
        command: decodeUnicode(json.command || json.cmd || '')
      }
    } catch {
      // fall through
    }
  }

  // 尝试提取 ```代码块``` 中的命令
  const codeMatch = text.match(/```(?:bash|sh|shell)?\s*\n?([\s\S]*?)\n?```/)
  if (codeMatch) {
    return {
      explanation: decodeUnicode(text.replace(codeMatch[0], '').trim()),
      command: decodeUnicode(codeMatch[1].trim())
    }
  }

  // 纯文本回复
  return { explanation: decodeUnicode(text.trim()), command: '' }
}

const processWithAI = async (tab: TerminalTab, input: string) => {
  tab.isProcessingAI = true
  tab.terminal?.writeln('\r\n\x1b[90m[AI处理中...]\x1b[0m')

  try {
    const messages = [
      { role: 'system', content: buildSystemPrompt(tab) },
      ...tab.conversationHistory.slice(-20)  // 限制历史长度
    ]

    const resp = await http.post('/api/chat/completions', {
      messages,
      model: 'default'
    })

    // 兼容拦截器解包：resp 可能是 response.data 或完整 response
    const data = resp?.data || resp
    const aiText = data?.choices?.[0]?.message?.content || ''

    if (!aiText) {
      tab.terminal?.writeln('\r\n\x1b[31m[AI返回为空]\x1b[0m')
      return
    }

    const parsed = parseAIResponse(aiText)

    if (parsed.explanation) {
      tab.terminal?.writeln(`\r\n\x1b[32m🤖 ${parsed.explanation}\x1b[0m`)
    }

    tab.conversationHistory.push({ role: 'assistant', content: aiText })

    // 保存消息（容错）
    saveChatMessage(tab, {
      role: 'assistant',
      content: parsed.explanation,
      ai_explanation: parsed.explanation,
      ai_suggested_command: parsed.command || undefined,
      message_type: parsed.command ? 'command_suggest' : 'text'
    })

    if (parsed.command) {
      const processedCmd = preprocessCommand(parsed.command)
      tab.aiSuggestedCommand = processedCmd
      tab.lastAICommand = processedCmd
      tab.showCommandConfirm = true
      tab.terminal?.writeln(`\r\n\x1b[33m┌─ AI建议命令 ────────────────────┐\x1b[0m`)
      tab.terminal?.writeln(`\x1b[33m│ \x1b[97m${processedCmd}\x1b[33m\x1b[0m`)
      tab.terminal?.writeln(`\x1b[33m└─────────────────────────────────┘\x1b[0m`)
    } else {
      tab.terminal?.writeln('\r\n\x1b[90m[AI分析完成，无需执行命令]\x1b[0m')
    }
  } catch (e: any) {
    const errMsg = e?.response?.data?.detail || e?.message || '未知错误'
    tab.terminal?.writeln(`\r\n\x1b[31m[AI错误: ${errMsg}]\x1b[0m`)

    // 如果是 404，提示用户
    if (e?.response?.status === 404) {
      tab.terminal?.writeln('\x1b[31m[Chat API未配置，请检查后端 /api/chat/completions 路由]\x1b[0m')
    }
  } finally {
    tab.isProcessingAI = false
  }
}

/**
 * 命令执行完成回调 - 终极修复版
 * 解决 UI 卡在 "等待命令执行完成" 的问题
 */
const onTabCommandFinished = async (tabParam: TerminalTab, output: string) => {
  // 1. 【核心修复】必须从响应式数组源头重新获取 tab 对象
  // WebSocket 回调传进来的 tabParam 可能是非响应式的旧引用
  const tab = tabs.value.find(t => t.id === tabParam.id);
  
  // 如果找不到（极端情况），回退使用传入的参数，但大概率 UI 不会更新
  const targetTab = tab || tabParam;

  console.log(`[Tab ${targetTab.id}] 收到命令完成信号，开始处理状态流转`);

  // 2. 【强制清理】第一件事：立即关闭等待状态和计时器
  // 无论后续逻辑如何，必须先让界面解锁
  targetTab.isWaitingCommandFinish = false;
  
  if (targetTab.waitingTimer) {
    clearInterval(targetTab.waitingTimer);
    targetTab.waitingTimer = null;
  }

  // 3. 更新输出缓冲区
  targetTab.recentTerminalOutput = output || targetTab.recentTerminalOutput;

  const cmd = targetTab.lastAICommand;

  // 4. 【异步保存】不使用 await，防止接口问题阻塞流程
  if (cmd) {
    saveChatMessage(targetTab, {
      role: 'output',
      content: output.slice(-4000),
      command: cmd,
      command_output: output.slice(-4000),
      command_status: 'executed',
      message_type: 'output'
    }).catch(e => console.warn('历史保存失败(忽略)', e));
  }

  // 5. 【核心逻辑修改】
  // 只有 (有命令) && (是Agent模式) && (不是手动输入的命令) 才继续 AI 分析
  if (cmd && targetTab.agentMode && !targetTab.isManualCommand) {
    // 状态切换：确保 等待=false, AI处理=true
    targetTab.isWaitingCommandFinish = false; // 双重保险
    targetTab.isProcessingAI = true;

    const resultMessage = `命令 \`${cmd}\` 已执行完成，输出如下：\n\`\`\`\n${output.slice(-2000)}\n\`\`\`\n请根据执行结果判断下一步操作。`;
    
    // 添加到前端历史
    targetTab.conversationHistory.push({ role: 'user', content: resultMessage });

    console.log('状态已切换，正在请求 AI 分析结果...');
    
    // 调用 AI (内部有 try-finally 确保 isProcessingAI 会关闭)
    await processWithAI(targetTab, resultMessage);
    
    // 清理命令记录
    targetTab.lastAICommand = '';
  } else {
    // 手动命令，或者 Shell 模式，到此为止
    targetTab.terminal?.writeln('\r\n\x1b[90m[执行完成]\x1b[0m\r\n');
    targetTab.lastAICommand = '';
    // 重置标记，以防万一
    targetTab.isManualCommand = false;
  }
};

// ==================== 确认/拒绝命令 ====================
const confirmCommand = (tab: TerminalTab) => {
  const cmd = (tab.aiSuggestedCommand || '').trim()
  tab.showCommandConfirm = false
  tab.aiSuggestedCommand = ''
  if (!cmd) return

  tab.lastAICommand = cmd
  // 【关键新增】这是 AI 建议的命令，执行完需要回传给 AI 继续分析
  tab.isManualCommand = false;

  startTabWaiting(tab) // 先进入等待态

  if (tab.ws && tab.ws.readyState === WebSocket.OPEN) {
    tab.ws.send(JSON.stringify({ type: 'watch_command' })) // 再开监视
    tab.ws.send(JSON.stringify({ type: 'data', data: cmd + '\r' })) // 最后发命令
  } else {
    stopTabWaiting(tab)
    tab.terminal?.writeln('\r\n\x1b[31m[连接未就绪，命令未发送]\x1b[0m')
  }
}

const rejectCommand = (tab: TerminalTab) => {
  tab.showCommandConfirm = false
  tab.aiSuggestedCommand = ''
  tab.lastAICommand = ''
  tab.terminal?.writeln('\x1b[90m[已拒绝执行命令]\x1b[0m')
}

/**
 * 处理用户输入提交
 * 修复：直接命令也必须先开启 watch_command，否则后端不会返回完成信号
 */
const handleUserSubmit = async (tab: TerminalTab) => {
  const input = tab.userInputText.trim()
  if (!input) return
  tab.userInputText = ''

  // 1. Shell 模式：普通发送，不监视
  if (!tab.agentMode) {
    sendTabCommand(tab, input)
    return
  }

  // 2. Agent 模式：所有操作都要记录
  tab.terminal?.writeln(`\r\n\x1b[36m❯ ${input}\x1b[0m`)
  tab.conversationHistory.push({ role: 'user', content: input })

  // 容错保存
  saveChatMessage(tab, {
    role: 'user',
    content: input,
    message_type: isCommand(input) ? 'command' : 'text'
  }).catch(() => {})

  // 3. 【核心修复】直接命令分支
  if (isCommand(input)) {
    const processedCmd = preprocessCommand(input)
    tab.terminal?.writeln(`\x1b[90m[直接执行命令: ${processedCmd}]\x1b[0m`)
    
    // 记录这次是直接输入的命令
    tab.lastAICommand = processedCmd
    // 【关键新增】标记这是手动命令，执行完不要叫 AI 分析
    tab.isManualCommand = true;
    
    // 开启等待 UI
    startTabWaiting(tab)

    // 发送组合拳：开启监视 -> 发送命令
    if (tab.ws && tab.ws.readyState === WebSocket.OPEN) {
      // 关键！告诉后端我要监视这个命令
      tab.ws.send(JSON.stringify({ type: 'watch_command' }))
      // 发送实际命令
      tab.ws.send(JSON.stringify({ type: 'data', data: processedCmd + '\r' }))
    } else {
      stopTabWaiting(tab)
      tab.terminal?.writeln('\x1b[31m[连接已断开]\x1b[0m')
    }
    return
  }

  // 4. 自然语言分支：调用AI
  if (!tab.currentSessionId) {
    await createChatSession(tab)
  }
  await processWithAI(tab, input)
}

// ==================== 窗口resize ====================
const handleResize = () => {
  const tab = activeTab.value
  if (tab?.fitAddon && tab.terminal) {
    try {
      tab.fitAddon.fit()
      if (tab.ws && tab.ws.readyState === WebSocket.OPEN) {
        const dims = tab.fitAddon.proposeDimensions()
        if (dims) {
          tab.ws.send(JSON.stringify({ type: 'resize', cols: dims.cols, rows: dims.rows }))
        }
      }
    } catch { /* ignore */ }
  }
}

// ==================== 生命周期 ====================
onMounted(async () => {
  await loadConnections()
  window.addEventListener('resize', handleResize)
  document.addEventListener('click', handleDocumentClick)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  document.removeEventListener('click', handleDocumentClick)

  for (const [, timer] of tabLatencyTimers) {
    clearInterval(timer)
  }
  tabLatencyTimers.clear()

  for (const tab of tabs.value) {
    cleanupTab(tab)
  }
})

// keep-alive 激活时重新 fit
onActivated(() => {
  nextTick(() => {
    const tab = activeTab.value
    if (tab?.fitAddon && tab.terminal) {
      try { tab.fitAddon.fit() } catch { /* ignore */ }
    }
  })
})

onDeactivated(() => {
  // keep-alive 停用时不清理连接
})

// 监听Agent模式切换
watch(() => activeTab.value?.agentMode, (newVal) => {
  const tab = activeTab.value
  if (tab && newVal && !tab.currentSessionId && tab.connectionStatus === 'connected') {
    createChatSession(tab)
  }
})
</script>

<style scoped>
.workspace-container {
  display: flex;
  height: 100%;
  overflow: hidden;
  background: #0d1117;
}

/* ========== 侧边栏 ========== */
.sidebar {
  width: 260px;
  min-width: 260px;
  background: #161b22;
  border-right: 1px solid #30363d;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: width 0.3s ease, min-width 0.3s ease;
}

.sidebar.collapsed {
  width: 60px;
  min-width: 60px;
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid #30363d;
  min-height: 60px;
  box-sizing: border-box;
}

.sidebar.collapsed .sidebar-header {
  min-height: 60px;
}

.sidebar-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sidebar-header h3 {
  margin: 0;
  color: #e6edf3;
  font-size: 16px;
  transition: opacity 0.3s ease;
}

.sidebar.collapsed .sidebar-header h3 {
  opacity: 0;
  width: 0;
  overflow: hidden;
}

.sidebar.collapsed .sidebar-header .el-button:not(.sidebar-toggle) {
  opacity: 0;
  width: 0;
  overflow: hidden;
  padding: 0;
  margin: 0;
  border: none;
}

.sidebar.collapsed .sidebar-header {
  justify-content: center;
}

.sidebar-toggle {
  color: #8b949e;
  transition: all 0.2s ease;
  padding: 8px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sidebar-toggle:hover {
  color: #e6edf3;
  background: #21262d;
}

.sidebar-toggle.collapsed {
  transform: rotate(180deg);
}

.sidebar.collapsed .sidebar-toggle {
  padding: 12px !important;
  font-size: 18px !important;
  width: 40px !important;
  height: 40px !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
}

.sidebar.collapsed .sidebar-toggle .el-icon svg {
  width: 20px !important;
  height: 20px !important;
  fill: currentColor !important;
}

/* 确保侧边栏头部在收缩前后高度一致 */
.sidebar-header {
  height: 60px !important;
  min-height: 60px !important;
  display: flex !important;
  align-items: center !important;
  box-sizing: border-box !important;
}

.sidebar.collapsed .sidebar-header {
  height: 60px !important;
  min-height: 60px !important;
  justify-content: center !important;
  align-items: center !important;
}

.connections-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.conn-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
  margin-bottom: 4px;
  position: relative;
}

.conn-item:hover {
  background: #21262d;
}

.conn-item.active {
  background: #1f6feb22;
  border: 1px solid #1f6feb44;
}

.conn-info {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
}

.conn-icon {
  color: #8b949e;
  font-size: 24px;
  margin-right: 10px;
  flex-shrink: 0;
}

.conn-details {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.conn-name {
  color: #e6edf3;
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conn-host {
  color: #8b949e;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conn-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.conn-item:hover .conn-actions {
  opacity: 1;
}

.action-icon {
  color: #8b949e;
  cursor: pointer;
  font-size: 14px;
  padding: 2px;
  border-radius: 3px;
  transition: all 0.2s;
}

.action-icon:hover {
  color: #58a6ff;
  background: #ffffff11;
}

.action-icon.add-icon:hover {
  color: #3fb950;
}

.action-icon.delete-icon:hover {
  color: #f85149;
}

.conn-status {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
}

.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #8b949e;
}

.status-dot.status-connected, .tab-status-dot.status-connected {
  background: #3fb950;
  box-shadow: 0 0 6px #3fb95066;
}

.status-dot.status-connecting, .tab-status-dot.status-connecting {
  background: #d29922;
  animation: pulse 1s infinite;
}

.status-dot.status-disconnected, .tab-status-dot.status-disconnected {
  background: #f85149;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* ========== 主内容区 ========== */
.terminal-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 标签栏 */
.terminal-tabs {
  display: flex;
  align-items: center;
  background: #161b22;
  border-bottom: 1px solid #30363d;
  padding: 0 8px;
  height: 38px;
  overflow-x: auto;
  position: relative;
  flex-shrink: 0;
}

.terminal-tabs::-webkit-scrollbar {
  height: 2px;
}

.tab-item {
  display: flex;
  align-items: center;
  padding: 6px 12px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  color: #8b949e;
  font-size: 13px;
  white-space: nowrap;
  transition: all 0.2s;
  gap: 6px;
}

.tab-item:hover {
  color: #e6edf3;
  background: #21262d;
}

.tab-item.active {
  color: #e6edf3;
  border-bottom-color: #1f6feb;
}

.tab-status-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #8b949e;
  flex-shrink: 0;
}

.tab-index {
  color: #6e7681;
  font-size: 11px;
}

.tab-close {
  font-size: 12px;
  opacity: 0;
  transition: opacity 0.2s;
  cursor: pointer;
  border-radius: 2px;
  padding: 1px;
}

.tab-item:hover .tab-close {
  opacity: 0.7;
}

.tab-close:hover {
  opacity: 1 !important;
  background: #ffffff22;
}

.tab-add {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  cursor: pointer;
  color: #8b949e;
  border-radius: 4px;
  transition: all 0.2s;
  flex-shrink: 0;
}

.tab-add:hover {
  color: #e6edf3;
  background: #21262d;
}

.new-tab-menu {
  position: absolute;
  top: 100%;
  right: 8px;
  background: #21262d;
  border: 1px solid #30363d;
  border-radius: 6px;
  padding: 4px;
  z-index: 100;
  min-width: 220px;
  max-height: 300px;
  overflow-y: auto;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  border-radius: 4px;
  color: #e6edf3;
  font-size: 13px;
  transition: background 0.2s;
}

.menu-item:hover {
  background: #30363d;
}

/* 欢迎页 */
.welcome-panel {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.welcome-content {
  text-align: center;
  color: #8b949e;
}

.welcome-icon {
  font-size: 64px;
  color: #30363d;
  margin-bottom: 16px;
}

.welcome-content h2 {
  color: #e6edf3;
  margin: 8px 0;
}

.welcome-content p {
  margin-bottom: 24px;
}

/* 终端面板 */
.terminal-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.terminal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background: #161b22;
  border-bottom: 1px solid #30363d;
  flex-shrink: 0;
}

.terminal-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.server-name {
  color: #e6edf3;
  font-weight: 600;
}

.terminal-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* 状态提示条 */
.status-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  font-size: 13px;
  flex-shrink: 0;
}

.status-banner.connecting {
  background: #d2992211;
  color: #d29922;
  border-bottom: 1px solid #d2992233;
}

.status-banner.error {
  background: #f8514911;
  color: #f85149;
  border-bottom: 1px solid #f8514933;
}

.terminal-container {
  flex: 1;
  padding: 4px;
  background: #1e1e1e;
  overflow: hidden;
  min-height: 200px;
}

.waiting-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  background: #1c2128;
  border-top: 1px solid #30363d;
  color: #d29922;
  font-size: 13px;
  flex-shrink: 0;
}

.rotating {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  100% { transform: rotate(360deg); }
}

.waiting-time {
  color: #8b949e;
  font-size: 12px;
}

.interactive-hint {
  padding: 8px 16px;
  background: #1c2128;
  border-top: 1px solid #30363d;
  flex-shrink: 0;
}

.hint-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.command-confirm {
  padding: 10px 16px;
  background: #2d2d30;
  border-top: 1px solid #ffc107;
  flex-shrink: 0;
  z-index: 1000;
  position: relative;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.confirm-header {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #d29922;
  margin-bottom: 8px;
}

.confirm-command {
  background: #0d1117;
  padding: 8px 12px;
  border-radius: 4px;
  margin-bottom: 8px;
}

.confirm-command code {
  color: #7ee787;
  font-family: Consolas, Monaco, monospace;
}

.confirm-actions {
  display: flex;
  gap: 8px;
}

.input-bar {
  padding: 8px 16px;
  background: #161b22;
  border-top: 1px solid #30363d;
  flex-shrink: 0;
}

::-webkit-scrollbar {
  width: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: #30363d;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: #484f58;
}
</style>