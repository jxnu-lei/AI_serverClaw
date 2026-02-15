import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { ElMessage } from 'element-plus'

const routes: RouteRecordRaw[] = [
  // 公开页面
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/auth/LoginView.vue'),
    meta: { guest: true }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('../views/auth/RegisterView.vue'),
    meta: { guest: true }
  },

  // 需要登录
  {
    path: '/',
    component: () => import('../components/layout/MainLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'Home',
        component: () => import('../views/workspace/WorkspaceView.vue')
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('../views/settings/SettingsView.vue')
      },
      {
        path: 'connections',
        name: 'Connections',
        component: () => import('../views/workspace/WorkspaceView.vue')
      },
      {
        path: 'ai-assistant',
        name: 'AIAssistant',
        component: () => import('../views/ai-assistant/AIAssistantView.vue')
      },
      {
        path: 'chat-history',
        name: 'ChatHistory',
        component: () => import('../views/ChatHistoryView.vue'),
        meta: { requiresAdmin: true }
      },
      {
        path: 'users',
        name: 'UserManagement',
        component: () => import('../views/UserManagementView.vue'),
        meta: { requiresAdmin: true }
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('../views/settings/SettingsView.vue')
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, _from, next) => {
  const isAuthenticated = localStorage.getItem('access_token')
  const userRole = localStorage.getItem('user_role')

  if (to.meta.requiresAuth && !isAuthenticated) {
    return next({ name: 'Login', query: { redirect: to.fullPath } })
  }

  // 管理员页面权限检查
  if (to.meta.requiresAdmin && userRole !== 'admin') {
    ElMessage.error('只有管理员可以访问此页面')
    return next({ path: '/' })
  }

  next()
})

export default router
