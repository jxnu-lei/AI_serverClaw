<template>
  <div class="main-layout">
    <!-- 侧边栏 -->
    <el-aside width="200px" class="sidebar">
      <div class="logo">
        <h2>AI Terminal</h2>
      </div>
      
      <el-menu
        :default-active="activeMenu"
        class="sidebar-menu"
        router
        unique-opened
        background-color="#001529"
        text-color="#fff"
        active-text-color="#409EFF"
      >
        <el-menu-item index="/">
          <template #icon>
            <el-icon><HomeFilled /></el-icon>
          </template>
          <span>工作台</span>
        </el-menu-item>
        
        <el-sub-menu index="connections">
          <template #title>
            <el-icon><Link /></el-icon>
            <span>连接管理</span>
          </template>
          <el-menu-item index="/connections">
            <span>服务器连接</span>
          </el-menu-item>
        </el-sub-menu>
        
        <el-sub-menu index="system">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>系统设置</span>
          </template>
          <el-menu-item index="/settings">
            <span>个人设置</span>
          </el-menu-item>
          <el-menu-item index="/ai-assistant">
            <span>AI 助手</span>
          </el-menu-item>
          <el-menu-item index="/chat-history" v-if="isAdmin">
            <span>对话历史</span>
          </el-menu-item>
          <el-menu-item index="/users" v-if="isAdmin">
            <span>用户管理</span>
          </el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-aside>
    
    <!-- 主内容区 -->
    <el-container class="main-content">
      <!-- 顶部导航栏 -->
      <el-header class="top-header">
        <div class="header-left">
          <el-button link @click="toggleCollapse" class="menu-toggle">
            <el-icon><Menu /></el-icon>
          </el-button>
        </div>
        
        <div class="header-right">
          <el-dropdown>
            <span class="user-info">
              <el-avatar :size="32">{{ userInitial }}</el-avatar>
              <span class="user-name">{{ userName }}</span>
              <el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="navigateToProfile">个人资料</el-dropdown-item>
                <el-dropdown-item @click="navigateToSettings">设置</el-dropdown-item>
                <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      
      <!-- 内容区域 -->
      <el-main>
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { HomeFilled, Link, Setting, Menu, ArrowDown } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const isCollapse = ref(false)

const activeMenu = computed(() => {
  return route.path
})

const userName = computed(() => {
  return localStorage.getItem('user_name') || '用户'
})

const userInitial = computed(() => {
  return userName.value.charAt(0).toUpperCase()
})

const isAdmin = computed(() => {
  return localStorage.getItem('user_role') === 'admin'
})

const toggleCollapse = () => {
  isCollapse.value = !isCollapse.value
}

const handleLogout = () => {
  localStorage.clear()
  ElMessage.success('已退出登录')
  router.push('/login')
}

const navigateToProfile = () => {
  router.push('/profile')
}

const navigateToSettings = () => {
  router.push('/settings')
}

onMounted(() => {
  // 检查登录状态
  const token = localStorage.getItem('access_token')
  if (!token) {
    router.push('/login')
  }
})
</script>

<style scoped lang="scss">
.main-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
  
  .sidebar {
    background-color: #001529;
    min-width: 200px;
    max-width: 200px;
    
    .logo {
      padding: 20px;
      background-color: #001529;
      
      h2 {
        color: #fff;
        font-size: 18px;
        margin: 0;
        text-align: center;
      }
    }
    
    .sidebar-menu {
      border-right: none;
      margin-top: 20px;
    }
  }
  
  .main-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    
    .top-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      background-color: #fff;
      border-bottom: 1px solid #e4e7ed;
      padding: 0 20px;
      height: 60px;
      
      .menu-toggle {
        color: #303133;
        font-size: 20px;
      }
      
      .user-info {
        display: flex;
        align-items: center;
        gap: 10px;
        cursor: pointer;
        
        .user-name {
          font-size: 14px;
          color: #303133;
        }
      }
    }
    
    .el-main {
      flex: 1;
      padding: 20px;
      overflow-y: auto;
      background-color: #f5f7fa;
    }
  }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>