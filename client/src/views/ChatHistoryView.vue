<template>
  <div class="chat-history-container">
    <div class="page-header">
      <h1>对话历史</h1>
      <div class="header-actions">
        <el-input
          v-model="searchText"
          placeholder="搜索会话..."
          clearable
          style="width: 250px;"
          @input="debouncedSearch"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
      </div>
    </div>

    <!-- 会话列表 -->
    <el-table :data="sessions" v-loading="loading" style="width: 100%;" @row-click="viewSession">
      <el-table-column prop="title" label="会话标题" min-width="200">
        <template #default="{ row }">
          <div class="session-title">
            <el-icon><ChatDotRound /></el-icon>
            <span>{{ row.title || '未命名会话' }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="host" label="服务器" width="180" />
      <el-table-column prop="message_count" label="消息数" width="80" align="center" />
      <el-table-column prop="command_count" label="命令数" width="80" align="center" />

      <el-table-column prop="duration" label="时长" width="100">
        <template #default="{ row }">
          {{ formatDuration(row.duration) }}
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="时间" width="180">
        <template #default="{ row }">
          {{ formatTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click.stop="viewSession(row)">查看</el-button>
          <el-popconfirm title="确定删除？" @confirm="deleteSession(row.id)">
            <template #reference>
              <el-button size="small" type="danger" @click.stop>删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div class="pagination-wrapper">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadSessions"
      />
    </div>

    <!-- 会话详情对话框 -->
    <el-dialog v-model="showDetail" :title="detailSession?.title || '会话详情'" width="800px" top="5vh">
      <div class="session-detail" v-if="detailSession">
        <div class="detail-meta">
          <el-descriptions :column="3" border size="small">
            <el-descriptions-item label="服务器">{{ detailSession.host }}</el-descriptions-item>
            <el-descriptions-item label="用户">{{ detailSession.username }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="detailSession.status === 'active' ? 'success' : 'info'" size="small">
                {{ detailSession.status === 'active' ? '进行中' : '已完成' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="消息数">{{ detailSession.message_count }}</el-descriptions-item>
            <el-descriptions-item label="命令数">{{ detailSession.command_count }}</el-descriptions-item>
            <el-descriptions-item label="时长">{{ formatDuration(detailSession.duration) }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <!-- 消息时间线 -->
        <div class="messages-timeline">
          <div 
            v-for="msg in detailSession.messages" 
            :key="msg.id"
            :class="['message-item', `message-${msg.role}`, `type-${msg.message_type}`]"
          >
            <!-- 用户消息 -->
            <div v-if="msg.role === 'user'" class="msg-bubble user-bubble">
              <div class="msg-header">
                <el-icon><User /></el-icon>
                <span>用户</span>
                <span class="msg-time">{{ formatTime(msg.timestamp) }}</span>
              </div>
              <div class="msg-content">{{ msg.content }}</div>
            </div>

            <!-- AI回复 -->
            <div v-else-if="msg.role === 'assistant'" class="msg-bubble ai-bubble">
              <div class="msg-header">
                <el-icon><MagicStick /></el-icon>
                <span>AI助手</span>
                <span class="msg-time">{{ formatTime(msg.timestamp) }}</span>
              </div>
              <div class="msg-content" v-if="msg.ai_explanation">
                {{ msg.ai_explanation }}
              </div>
              <div class="msg-command-suggest" v-if="msg.ai_suggested_command">
                <span class="suggest-label">建议命令：</span>
                <code>{{ msg.ai_suggested_command }}</code>
              </div>
            </div>

            <!-- 命令执行/拒绝/修改 -->
            <div v-else-if="msg.role === 'command'" class="msg-bubble command-bubble">
              <div class="msg-header">
                <el-icon><Monitor /></el-icon>
                <span>命令</span>
                <el-tag 
                  :type="msg.command_status === 'executed' ? 'success' : 
                         msg.command_status === 'rejected' ? 'danger' : 'warning'" 
                  size="small"
                >
                  {{ msg.command_status === 'executed' ? '已执行' : 
                     msg.command_status === 'rejected' ? '已拒绝' : '已修改' }}
                </el-tag>
                <span class="msg-time">{{ formatTime(msg.timestamp) }}</span>
              </div>
              <div class="msg-command">
                <code>{{ msg.command }}</code>
              </div>
            </div>

            <!-- 命令输出 -->
            <div v-else-if="msg.role === 'output'" class="msg-bubble output-bubble">
              <div class="msg-header">
                <el-icon><Document /></el-icon>
                <span>输出</span>
                <span class="msg-time">{{ formatTime(msg.timestamp) }}</span>
              </div>
              <pre class="msg-output">{{ truncateOutput(msg.command_output || msg.content) }}</pre>
            </div>

            <!-- 系统/错误消息 -->
            <div v-else class="msg-bubble system-bubble">
              <div class="msg-content">{{ msg.content }}</div>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, ChatDotRound, User, MagicStick, Monitor, Document } from '@element-plus/icons-vue'
import { http } from '@/utils/api'

const sessions = ref<any[]>([])
const loading = ref(false)
const searchText = ref('')
const currentPage = ref(1)
const pageSize = 20
const total = ref(0)

const showDetail = ref(false)
const detailSession = ref<any>(null)

let searchDebounce: ReturnType<typeof setTimeout> | null = null

const loadSessions = async (newPage?: number) => {
  // 如果传入了新页码，更新currentPage
  if (newPage) {
    currentPage.value = newPage
  }
  
  loading.value = true
  try {
    const params: any = { page: currentPage.value, page_size: pageSize }
    if (searchText.value) params.search = searchText.value
    
    const res = await http.get('/api/chat-history/sessions', params)
    const data = res.data || res
    sessions.value = data.items || []
    total.value = data.total || 0
  } catch {
    ElMessage.error('加载历史记录失败')
  } finally {
    loading.value = false
  }
}

const debouncedSearch = () => {
  if (searchDebounce) clearTimeout(searchDebounce)
  searchDebounce = setTimeout(() => {
    currentPage.value = 1
    loadSessions()
  }, 300)
}

const viewSession = async (row: any) => {
  try {
    const res = await http.get(`/api/chat-history/sessions/${row.id}`)
    detailSession.value = res.data || res
    showDetail.value = true
  } catch {
    ElMessage.error('加载会话详情失败')
  }
}

const deleteSession = async (id: string) => {
  try {
    await http.delete(`/api/chat-history/sessions/${id}`)
    ElMessage.success('删除成功')
    loadSessions()
  } catch {
    ElMessage.error('删除失败')
  }
}

const formatDuration = (seconds: number | null): string => {
  if (!seconds) return '-'
  if (seconds < 60) return `${seconds}秒`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}分${seconds % 60}秒`
  return `${Math.floor(seconds / 3600)}时${Math.floor((seconds % 3600) / 60)}分`
}

const formatTime = (time: string | null): string => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

const truncateOutput = (output: string): string => {
  if (!output) return ''
  return output.length > 2000 ? output.slice(0, 2000) + '\n... (输出已截断)' : output
}

onMounted(() => loadSessions())
</script>

<style scoped>
.chat-history-container { padding: 20px; max-width: 1200px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h1 { margin: 0; }
.header-actions { display: flex; gap: 12px; }
.pagination-wrapper { margin-top: 30px; margin-bottom: 20px; display: flex; justify-content: center; }

/* 分页样式优化 */
:deep(.el-pagination) {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  background: #f8f9fa;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

:deep(.el-pagination__total) {
  font-size: 14px;
  color: #6c757d;
  font-weight: 500;
}

:deep(.el-pagination__sizes) {
  margin: 0;
}

:deep(.el-pagination__sizes .el-input .el-input__inner) {
  border-radius: 4px;
  border: 1px solid #dee2e6;
  transition: all 0.3s ease;
}

:deep(.el-pagination__sizes .el-input .el-input__inner:hover) {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2);
}

:deep(.el-pagination__prev),
:deep(.el-pagination__next) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 4px;
  border: 1px solid #dee2e6;
  background: #ffffff;
  color: #6c757d;
  cursor: pointer;
  transition: all 0.3s ease;
}

:deep(.el-pagination__prev:hover),
:deep(.el-pagination__next:hover) {
  border-color: #409eff;
  color: #409eff;
  background: #ecf5ff;
}

:deep(.el-pagination__prev.is-disabled),
:deep(.el-pagination__next.is-disabled) {
  border-color: #dee2e6;
  color: #c9ccd4;
  background: #f8f9fa;
  cursor: not-allowed;
}

:deep(.el-pagination__page-btn) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 4px;
  border: 1px solid #dee2e6;
  background: #ffffff;
  color: #6c757d;
  cursor: pointer;
  transition: all 0.3s ease;
  margin: 0 2px;
}

:deep(.el-pagination__page-btn:hover:not(.is-disabled)) {
  border-color: #409eff;
  color: #409eff;
  background: #ecf5ff;
}

:deep(.el-pagination__page-btn.is-current) {
  border-color: #409eff;
  color: #ffffff;
  background: #409eff;
  font-weight: 600;
  box-shadow: 0 2px 4px rgba(64, 158, 255, 0.3);
}

:deep(.el-pagination__jump) {
  font-size: 14px;
  color: #6c757d;
}

:deep(.el-pagination__jump .el-input .el-input__inner) {
  width: 60px;
  border-radius: 4px;
  border: 1px solid #dee2e6;
  transition: all 0.3s ease;
}

:deep(.el-pagination__jump .el-input .el-input__inner:hover) {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2);
}

/* 响应式设计 */
@media (max-width: 768px) {
  :deep(.el-pagination) {
    padding: 8px 12px;
    flex-wrap: wrap;
  }
  
  :deep(.el-pagination__total) {
    font-size: 13px;
  }
  
  :deep(.el-pagination__page-btn),
  :deep(.el-pagination__prev),
  :deep(.el-pagination__next) {
    width: 28px;
    height: 28px;
    font-size: 13px;
  }
}

@media (max-width: 480px) {
  :deep(.el-pagination) {
    gap: 4px;
  }
  
  :deep(.el-pagination__sizes),
  :deep(.el-pagination__jump) {
    display: none;
  }
}

.session-title { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.session-title:hover { color: #409eff; }

.session-detail { max-height: 70vh; overflow-y: auto; }
.detail-meta { margin-bottom: 20px; }

.messages-timeline { display: flex; flex-direction: column; gap: 12px; }

.msg-bubble { padding: 12px 16px; border-radius: 8px; }
.user-bubble { background: #e8f4fd; border-left: 3px solid #409eff; }
.ai-bubble { background: #f0f9eb; border-left: 3px solid #67c23a; }
.command-bubble { background: #fdf6ec; border-left: 3px solid #e6a23c; }
.output-bubble { background: #1e1e1e; border-left: 3px solid #666; color: #d4d4d4; }
.system-bubble { background: #f4f4f5; border-left: 3px solid #909399; color: #666; font-size: 13px; }

.msg-header { display: flex; align-items: center; gap: 6px; margin-bottom: 8px; font-size: 13px; color: #666; }
.msg-time { margin-left: auto; font-size: 12px; color: #999; }
.msg-content { font-size: 14px; line-height: 1.6; white-space: pre-wrap; }
.msg-command code { background: #f5f5f5; padding: 4px 8px; border-radius: 4px; font-family: Consolas, monospace; }
.msg-command-suggest { margin-top: 8px; }
.suggest-label { color: #e6a23c; font-size: 13px; }
.msg-output { margin: 0; font-family: Consolas, monospace; font-size: 13px; white-space: pre-wrap; word-break: break-all; max-height: 300px; overflow-y: auto; }

/* 操作栏按钮样式 */
.el-table__fixed-right .el-button {
  margin-right: 8px;
}

.el-table__fixed-right .el-button:last-child {
  margin-right: 0;
}
</style>
