<template>
  <div class="user-management-container">
    <div class="page-header">
      <h1>用户管理</h1>
      <el-button type="primary" @click="openCreateDialog">新增用户</el-button>
    </div>

    <el-card>
      <el-table :data="users" v-loading="loading" style="width: 100%">
        <el-table-column prop="username" label="用户名" width="150" />
        <el-table-column prop="email" label="邮箱" min-width="200" />
        <el-table-column prop="role" label="角色" width="100">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small">
              {{ row.role === 'admin' ? '管理员' : '普通用户' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
              {{ row.is_active ? '活跃' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="320" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEditDialog(row)">编辑</el-button>
            <el-button 
              size="small" 
              :type="row.is_active ? 'danger' : 'success'" 
              :disabled="row.username === 'admin'"
              @click="toggleUserStatus(row)"
            >
              {{ row.is_active ? '禁用' : '启用' }}
            </el-button>
            <el-button 
              size="small" 
              type="warning" 
              @click="resetPassword(row)"
            >
              重置密码
            </el-button>
            <el-button 
              v-if="row.username !== 'admin'" 
              size="small" 
              type="danger" 
              @click="deleteUser(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 编辑用户对话框 -->
    <el-dialog title="编辑用户" v-model="editDialogVisible" width="500px">
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="用户名">
          <el-input v-model="editForm.username" disabled />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="editForm.email" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="editForm.role" :disabled="!isAdmin">
            <el-option label="普通用户" value="user" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="editForm.is_active" active-text="启用" inactive-text="禁用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveUser">保存</el-button>
      </template>
    </el-dialog>

    <!-- 创建用户对话框 -->
    <el-dialog title="新增用户" v-model="createDialogVisible" width="500px">
      <el-form :model="createForm" :rules="createRules" ref="createFormRef" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="createForm.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="createForm.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="createForm.password" type="password" placeholder="请输入密码" show-password />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="createForm.role">
            <el-option label="普通用户" value="user" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="createUser">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { http } from '@/utils/api'

const users = ref<any[]>([])
const loading = ref(false)
const editDialogVisible = ref(false)
const createDialogVisible = ref(false)
const createFormRef = ref()
const editForm = reactive({
  id: '',
  username: '',
  email: '',
  role: 'user',
  is_active: true
})

const createForm = reactive({
  username: '',
  email: '',
  password: '',
  role: 'user'
})

const createRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度3-20个字符', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' }
  ]
}

// 检查当前用户是否是管理员
const isAdmin = computed(() => {
  return localStorage.getItem('user_role') === 'admin'
})

const loadUsers = async () => {
  loading.value = true
  try {
    const res = await http.get('/api/admin/users')
    users.value = res.data || res || []
  } catch (e: any) {
    console.error('加载用户列表失败:', e)
    ElMessage.error('加载用户列表失败')
  } finally {
    loading.value = false
  }
}

const openEditDialog = (row: any) => {
  editForm.id = row.id
  editForm.username = row.username
  editForm.email = row.email
  editForm.role = row.role
  editForm.is_active = row.is_active
  editDialogVisible.value = true
}

const saveUser = async () => {
  try {
    await http.put(`/api/admin/users/${editForm.id}`, {
      email: editForm.email,
      role: editForm.role,
      is_active: editForm.is_active
    })
    ElMessage.success('用户更新成功')
    editDialogVisible.value = false
    loadUsers()
  } catch (e: any) {
    console.error('更新用户失败:', e)
    ElMessage.error('更新用户失败')
  }
}

const toggleUserStatus = async (row: any) => {
  try {
    await http.put(`/api/admin/users/${row.id}`, {
      is_active: !row.is_active
    })
    ElMessage.success(row.is_active ? '用户已禁用' : '用户已启用')
    loadUsers()
  } catch (e: any) {
    console.error('更新用户状态失败:', e)
    ElMessage.error('更新用户状态失败')
  }
}

const deleteUser = async (row: any) => {
  try {
    await ElMessageBox.confirm(`确定要删除用户 "${row.username}" 吗？`, '确认删除', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await http.delete(`/api/admin/users/${row.id}`)
    ElMessage.success('用户删除成功')
    loadUsers()
  } catch (e: any) {
    if (e !== 'cancel') {
      console.error('删除用户失败:', e)
      ElMessage.error(e?.response?.data?.detail || '删除用户失败')
    }
  }
}

const resetPassword = async (row: any) => {
  try {
    await ElMessageBox.confirm(`确定要重置用户 "${row.username}" 的密码吗？`, '确认重置密码', {
      confirmButtonText: '重置',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await http.post(`/api/admin/users/${row.id}/reset-password`)
    ElMessage.success('密码已重置为 admin!123')
  } catch (e: any) {
    if (e !== 'cancel') {
      console.error('重置密码失败:', e)
      ElMessage.error(e?.response?.data?.detail || '重置密码失败')
    }
  }
}

const openCreateDialog = () => {
  createForm.username = ''
  createForm.email = ''
  createForm.password = ''
  createForm.role = 'user'
  createDialogVisible.value = true
}

const createUser = async () => {
  if (!createFormRef.value) return
  
  try {
    await createFormRef.value.validate()
    await http.post('/api/admin/users', {
      username: createForm.username,
      email: createForm.email,
      password: createForm.password,
      role: createForm.role
    })
    ElMessage.success('用户创建成功')
    createDialogVisible.value = false
    loadUsers()
  } catch (e: any) {
    console.error('创建用户失败:', e)
    // 显示更详细的错误信息
    const errorMsg = e?.response?.data?.detail || e?.message || '创建用户失败'
    ElMessage.error(errorMsg)
  }
}

const formatTime = (time: string | null): string => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

onMounted(() => {
  if (!isAdmin.value) {
    ElMessage.warning('只有管理员可以访问用户管理')
    return
  }
  loadUsers()
})
</script>

<style scoped>
.user-management-container {
  padding: 20px;
}
.page-header {
  margin-bottom: 20px;
}
.page-header h1 {
  margin: 0;
  font-size: 24px;
}
</style>
