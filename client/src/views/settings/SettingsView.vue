<template>
  <div class="settings-container">
    <div class="settings-header">
      <h1>系统设置</h1>
    </div>
    
    <el-tabs v-model="activeTab" class="settings-tabs">
      <!-- 个人设置 -->
      <el-tab-pane label="个人设置" name="personal">
        <el-card class="settings-card">
          <el-form :model="personalForm" :rules="personalRules" ref="personalFormRef" label-width="120px">
            <el-form-item label="用户名" prop="username">
              <el-input v-model="personalForm.username" placeholder="请输入用户名" />
            </el-form-item>
            
            <el-form-item label="邮箱" prop="email">
              <el-input v-model="personalForm.email" type="email" placeholder="请输入邮箱" />
            </el-form-item>
            
            <el-form-item label="修改密码">
              <el-button type="primary" @click="openChangePasswordDialog">修改密码</el-button>
            </el-form-item>
            
            <el-form-item>
              <el-button type="primary" @click="savePersonalSettings">保存设置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>
      
      <!-- AI设置 -->
      <el-tab-pane label="AI 设置" name="ai">
        <el-card class="settings-card">
          <div class="form-tip">
            <el-alert type="info" :closable="false">
              <template #title>
                <span>配置说明：上方表单用于配置模型参数，点击"添加到列表"将配置保存为新模型；</span>
                <br>
                <span>下方列表中点击"使用"激活的模型才是AI真实使用的模型。</span>
              </template>
            </el-alert>
          </div>
          
          <el-form :model="aiForm" :rules="aiRules" ref="aiFormRef" label-width="120px" style="margin-top: 16px;">
            <el-form-item label="AI 服务提供商" prop="provider">
              <el-select v-model="aiForm.provider" placeholder="请选择AI服务提供商" filterable @change="handleProviderChange">
                <el-option
                  v-for="p in providerOptions"
                  :key="p.value"
                  :label="p.label"
                  :value="p.value"
                />
              </el-select>
            </el-form-item>
            
            <el-form-item label="API Key" prop="api_key">
              <el-input v-model="aiForm.api_key" type="password" placeholder="请输入API Key" show-password />
            </el-form-item>
            
            <el-form-item label="模型" prop="model">
              <el-input v-model="aiForm.model" placeholder="请输入模型名称" />
            </el-form-item>
            
            <el-form-item label="API 基础URL" prop="base_url">
              <el-input v-model="aiForm.base_url" placeholder="可选，例如: https://api.deepseek.com/v1" />
              <div style="font-size: 12px; color: #909399; margin-top: 5px;">留空将使用提供商默认URL</div>
            </el-form-item>
            
            <el-form-item label="温度" prop="temperature">
              <el-slider v-model="aiForm.temperature" :min="0" :max="1" :step="0.1" />
              <span class="slider-value">{{ aiForm.temperature }}</span>
            </el-form-item>
            
            <el-form-item>
              <el-button type="primary" @click="addNewModel">添加到列表</el-button>
              <el-button type="warning" @click="saveCurrentModelConfig" :disabled="!currentModelId">
                保存到当前模型
              </el-button>
              <el-button type="success" @click="openAddProviderDialog" style="margin-left:12px">新增提供商</el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <div style="margin-top:16px">
          <h3>已保存模型（点击"使用"激活）</h3>
          <el-table :data="models" style="width: 100%">
            <el-table-column prop="name" label="名称" />
            <el-table-column prop="provider" label="提供商" />
            <el-table-column prop="model" label="模型" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag v-if="row.is_active" type="success" size="small">使用中</el-tag>
                <el-tag v-else type="info" size="small" effect="plain">未使用</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160">
              <template #default="{ row }">
                <el-button 
                  size="small" 
                  :type="row.is_active ? 'success' : 'primary'"
                  :disabled="row.is_active"
                  @click="applyModel(row)"
                >
                  {{ row.is_active ? '当前使用' : '使用' }}
                </el-button>
                <el-button size="small" type="danger" @click="deleteModel(row)">
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- 新增提供商对话框 - 使用 v-model 替代 :visible.sync -->
        <el-dialog title="新增 AI 服务提供商" v-model="addProviderDialogVisible" width="450px">
          <el-form label-width="100px">
            <el-form-item label="显示名称">
              <el-input v-model="newProviderName" placeholder="如：Anthropic Claude" />
            </el-form-item>
            <el-form-item label="代码">
              <el-input v-model="newProviderCode" placeholder="如：anthropic" />
              <div style="font-size: 12px; color: #909399; margin-top: 5px;">用于API调用的标识符</div>
            </el-form-item>
            <el-form-item label="默认模型">
              <el-input v-model="newProviderDefaultModel" placeholder="如：claude-3-opus" />
            </el-form-item>
            <el-form-item label="默认URL">
              <el-input v-model="newProviderDefaultUrl" placeholder="如：https://api.anthropic.com" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="addProviderDialogVisible = false">取消</el-button>
            <el-button type="primary" @click="confirmAddProvider">确定</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>
      
      <!-- 系统设置 -->
      <el-tab-pane label="系统设置" name="system">
        <el-card class="settings-card">
          <el-form :model="systemForm" :rules="systemRules" ref="systemFormRef" label-width="120px">
            <el-form-item label="主题" prop="theme">
              <el-select v-model="systemForm.theme" placeholder="请选择主题">
                <el-option label="默认主题" value="default" />
                <el-option label="暗色主题" value="dark" />
              </el-select>
            </el-form-item>
            
            <el-form-item label="语言" prop="language">
              <el-select v-model="systemForm.language" placeholder="请选择语言">
                <el-option label="简体中文" value="zh-CN" />
                <el-option label="English" value="en-US" />
              </el-select>
            </el-form-item>
            
            <el-form-item label="终端字体大小" prop="terminal_font_size">
              <el-input-number v-model="systemForm.terminal_font_size" :min="8" :max="24" :step="1" />
            </el-form-item>
            
            <el-form-item label="自动保存会话" prop="auto_save_session">
              <el-switch v-model="systemForm.auto_save_session" />
            </el-form-item>
            
            <el-form-item label="会话超时时间" prop="session_timeout">
              <el-input-number v-model="systemForm.session_timeout" :min="5" :max="120" :step="5" />
              <span class="unit">分钟</span>
            </el-form-item>
            
            <el-form-item>
              <el-button type="primary" @click="saveSystemSettings">保存设置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>
      
      <!-- 关于 -->
      <el-tab-pane label="关于" name="about">
        <el-card class="settings-card">
          <div class="about-content">
            <h2>AI Terminal</h2>
            <p class="version">版本：1.0.0</p>
            <el-divider />
            <p>AI Terminal 是一个智能服务器管理终端，集成了AI助手功能，帮助您更高效地管理服务器。</p>
            <p>主要功能：</p>
            <ul>
              <li>多服务器连接管理</li>
              <li>Web-based 终端界面</li>
              <li>AI 智能助手</li>
              <li>会话管理和日志记录</li>
              <li>安全的认证系统</li>
            </ul>
            <el-divider />
            <p class="copyright">© 2026 AI Terminal. All rights reserved.</p>
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { http } from '@/utils/api'

const activeTab = ref('personal')

// 个人设置表单
const personalFormRef = ref()
const personalForm = reactive({
  username: '',
  email: ''
})

const personalRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度3-20个字符', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ]
}

// AI设置表单
const aiFormRef = ref()
const aiForm = reactive({
  provider: 'deepseek',
  api_key: '',
  model: 'deepseek-chat',
  base_url: '',
  temperature: 0.7
})

// 提供商列表（从后端获取）
const providers = ref<Array<{id: string, name: string, code: string, default_model?: string, default_url?: string, is_default: boolean}>>([])

const loadProviders = async () => {
  try {
    const resp = await http.get('/api/llm/providers')
    providers.value = resp.data || []
  } catch (e) {
    console.error('加载提供商列表失败:', e)
  }
}

const providerOptions = computed(() => {
  return providers.value.map(p => ({
    label: p.name,
    value: p.code,
    default_model: p.default_model,
    default_url: p.default_url
  }))
})

// 选择提供商时自动填充默认模型和URL
const handleProviderChange = (providerCode: string) => {
  const provider = providers.value.find(p => p.code === providerCode)
  if (provider) {
    if (provider.default_model && !aiForm.model) {
      aiForm.model = provider.default_model
    }
    if (provider.default_url && !aiForm.base_url) {
      aiForm.base_url = provider.default_url
    }
  }
}

// 新增提供商对话框
const addProviderDialogVisible = ref(false)
const newProviderName = ref('')
const newProviderCode = ref('')
const newProviderDefaultModel = ref('')
const newProviderDefaultUrl = ref('')

const openAddProviderDialog = () => {
  newProviderName.value = ''
  newProviderCode.value = ''
  newProviderDefaultModel.value = ''
  newProviderDefaultUrl.value = ''
  addProviderDialogVisible.value = true
}

const confirmAddProvider = async () => {
  if (!newProviderName.value.trim()) {
    ElMessage.warning('请输入提供商名称')
    return
  }
  if (!newProviderCode.value.trim()) {
    ElMessage.warning('请输入提供商代码')
    return
  }
  
  try {
    await http.post('/api/llm/providers', null, {
      params: {
        name: newProviderName.value.trim(),
        code: newProviderCode.value.trim().toLowerCase().replace(/\s+/g, '-'),
        default_model: newProviderDefaultModel.value.trim() || undefined,
        default_url: newProviderDefaultUrl.value.trim() || undefined
      }
    })
    ElMessage.success('提供商添加成功')
    addProviderDialogVisible.value = false
    // 重新加载提供商列表
    await loadProviders()
    // 自动选中新添加的提供商
    aiForm.provider = newProviderCode.value.trim().toLowerCase().replace(/\s+/g, '-')
  } catch (e: any) {
    console.error('添加提供商失败:', e)
    ElMessage.error(e?.response?.data?.detail || '添加提供商失败')
  }
}

const aiRules = {
  provider: [
    { required: true, message: '请选择AI服务提供商', trigger: 'change' }
  ],
  api_key: [
    { required: true, message: '请输入API Key', trigger: 'blur' }
  ],
  model: [
    { required: true, message: '请输入模型名称', trigger: 'blur' }
  ]
}

const models = ref([])
const currentModelId = ref<string | null>(null)

const loadModels = async () => {
  try {
    const resp = await http.get('/api/llm/configs')
    models.value = resp.data || []
    
    // 查找当前激活的模型（is_active=true）
    const activeModel = models.value.find((m: any) => m.is_active === true)
    if (activeModel) {
      currentModelId.value = activeModel.id
    } else {
      currentModelId.value = null
    }
  } catch (e) {
    console.error('加载模型列表失败:', e)
  }
}

// 系统设置表单
const systemFormRef = ref()
const systemForm = reactive({
  theme: 'default',
  language: 'zh-CN',
  terminal_font_size: 14,
  auto_save_session: true,
  session_timeout: 30
})

const systemRules = {
  theme: [
    { required: true, message: '请选择主题', trigger: 'change' }
  ],
  language: [
    { required: true, message: '请选择语言', trigger: 'change' }
  ]
}

// 保存个人设置
const savePersonalSettings = async () => {
  if (!personalFormRef.value) return

  try {
    await personalFormRef.value.validate()
    const userId = localStorage.getItem('user_id')
    if (!userId) {
      ElMessage.error('请先登录')
      return
    }

    const payload = {
      username: personalForm.username,
      email: personalForm.email
    }

    const resp = await http.put(`/api/admin/users/${userId}`, payload)

    // 同步本地信息
    localStorage.setItem('user_name', resp.data.username)
    ElMessage.success('个人设置已保存')
  } catch (error: any) {
    console.error('保存个人设置失败:', error)
  }
}

// 添加新模型
// 添加新模型
const addNewModel = async () => {
  if (!aiFormRef.value) return
  
  try {
    await aiFormRef.value.validate()
    
    const name = `${aiForm.provider}-${aiForm.model}`
    await http.post('/api/llm/configs', {
      name: name,
      provider: aiForm.provider,
      model: aiForm.model,
      api_key: aiForm.api_key,
      base_url: aiForm.base_url,
      temperature: aiForm.temperature,
      is_active: true  // 新增后自动激活
    })
    ElMessage.success('模型已添加并激活')
    
    // 刷新模型列表
    await loadModels()
  } catch (error: any) {
    console.error('添加模型失败:', error)
    ElMessage.error(error?.response?.data?.detail || '添加模型失败')
  }
}

// 保存当前激活模型的配置
const saveCurrentModelConfig = async () => {
  if (!aiFormRef.value) return
  
  try {
    await aiFormRef.value.validate()
    
    if (!currentModelId.value) {
      ElMessage.warning('请先在下方选择一个模型或添加新模型')
      return
    }
    
    const payload = {
      provider: aiForm.provider,
      model: aiForm.model,
      api_key: aiForm.api_key,
      base_url: aiForm.base_url,
      temperature: aiForm.temperature
    }
    
    await http.put('/api/llm/config', payload)
    ElMessage.success('配置已保存到当前模型')
    
    // 刷新模型列表
    await loadModels()
  } catch (error: any) {
    console.error('保存配置失败:', error)
    ElMessage.error(error?.response?.data?.detail || '保存配置失败')
  }
}

const applyModel = async (row: any) => {
  try {
    // 调用后端API激活选中的模型
    const resp = await http.put(`/api/llm/configs/${row.id}/activate`)
    const activated = resp.data
    
    // 用激活模型的数据更新表单
    aiForm.provider = activated.provider || row.provider
    aiForm.model = activated.model || row.model
    aiForm.api_key = activated.api_key || row.api_key || ''
    aiForm.base_url = activated.base_url || row.base_url || ''
    aiForm.temperature = activated.temperature ?? row.temperature ?? 0.7
    
    // 更新当前使用状态
    currentModelId.value = row.id
    
    // 刷新模型列表
    await loadModels()
    
    ElMessage.success(`已切换到模型: ${row.name || row.model}`)
  } catch (error: any) {
    console.error('切换模型失败:', error)
    ElMessage.error('切换模型失败')
  }
}

const deleteModel = async (row: any) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除模型 "${row.name || row.model}" 吗？`, 
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await http.delete(`/api/llm/configs/${row.id}`)
    ElMessage.success('模型已删除')
    
    // 如果删除的是当前使用的模型，重置状态
    if (currentModelId.value === row.id) {
      currentModelId.value = null
    }
    
    // 重新加载模型列表
    loadModels()
  } catch (e: any) {
    if (e !== 'cancel') {
      console.error('删除模型失败:', e)
      ElMessage.error('删除模型失败')
    }
  }
}

// 保存系统设置（目前前端持久化到 localStorage）
const saveSystemSettings = async () => {
  if (!systemFormRef.value) return

  try {
    await systemFormRef.value.validate()
    const payload = { ...systemForm }
    // 前端持久化（后端尚未提供系统设置接口）
    localStorage.setItem('system_settings', JSON.stringify(payload))
    ElMessage.success('系统设置已保存')
  } catch (error) {
    // 表单验证失败或其他错误
    ElMessage.error('系统设置保存失败')
  }
}

// 打开修改密码对话框
const openChangePasswordDialog = () => {
  // 后端当前未提供专门的修改密码接口，建议用户通过重置流程或在未来实现。
  ElMessageBox.alert('当前后端未提供在线修改密码接口；如果需要，请联系管理员或使用重置流程。', '修改密码', {
    confirmButtonText: '知道了',
    type: 'info'
  })
}

// 初始化设置
const initSettings = async () => {
  // 从 localStorage 读取基本用户信息
  personalForm.username = localStorage.getItem('user_name') || ''
  personalForm.email = ''

  // 加载前端已保存的系统设置（回退到默认）
  try {
    const sys = localStorage.getItem('system_settings')
    if (sys) {
      const parsed = JSON.parse(sys)
      Object.assign(systemForm, parsed)
    }
  } catch (e) {
    // ignore
  }

  // 尝试获取当前用户和已保存的 LLM 配置
  try {
    const res = await http.get('/api/auth/me')
    personalForm.username = res.data.username || personalForm.username
    personalForm.email = res.data.email || personalForm.email
    localStorage.setItem('user_name', res.data.username || localStorage.getItem('user_name') || '')
  } catch (e) {
    // 忽略获取用户失败
  }

  try {
    const resp = await http.get('/api/llm/config')
    const cfg = resp.data || {}
    aiForm.provider = cfg.provider || aiForm.provider
    aiForm.model = cfg.model || aiForm.model
    aiForm.api_key = cfg.api_key || aiForm.api_key
    aiForm.base_url = cfg.base_url || aiForm.base_url
    aiForm.temperature = cfg.temperature ?? aiForm.temperature
  } catch (e) {
    // 忽略获取失败（未配置）
    console.log('LLM配置未设置，使用默认值')
  }
}

// 初始化
onMounted(() => {
  loadProviders()
  initSettings()
  loadModels()
})
</script>

<style scoped lang="scss">
.settings-container {
  .settings-header {
    margin-bottom: 20px;
    
    h1 {
      font-size: 24px;
      color: #303133;
    }
  }
  
  .settings-tabs {
    .settings-card {
      margin-bottom: 20px;
    }
    
    .form-tip {
      margin-bottom: 0;
    }
    
    .slider-value {
      margin-left: 10px;
      font-size: 14px;
      color: #606266;
    }
    
    .unit {
      margin-left: 10px;
      font-size: 14px;
      color: #606266;
    }
    
    .about-content {
      text-align: center;
      
      h2 {
        font-size: 24px;
        color: #303133;
        margin-bottom: 10px;
      }
      
      .version {
        font-size: 16px;
        color: #606266;
        margin-bottom: 20px;
      }
      
      p {
        font-size: 14px;
        color: #606266;
        line-height: 1.6;
        margin-bottom: 10px;
      }
      
      ul {
        text-align: left;
        margin: 20px 0;
        padding-left: 20px;
        
        li {
          font-size: 14px;
          color: #606266;
          line-height: 1.6;
          margin-bottom: 5px;
        }
      }
      
      .copyright {
        margin-top: 30px;
        font-size: 12px;
        color: #909399;
      }
    }
  }
}
</style>