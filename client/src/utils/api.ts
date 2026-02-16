import axios from 'axios'
import { ElMessage } from 'element-plus'

// 创建axios实例
const api = axios.create({
  baseURL: '',  // 使用相对路径，通过vite代理
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器 - 自动添加token
api.interceptors.request.use(
  (config) => {
    const token = sessionStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器 - 统一错误处理
api.interceptors.response.use(
  (response) => {
    return response
  },
  (error) => {
    const { response } = error
    
    if (response) {
      switch (response.status) {
        case 401:
          // 未授权，清除token并跳转到登录页
          sessionStorage.removeItem('access_token')
          sessionStorage.removeItem('user_id')
          sessionStorage.removeItem('user_role')
          sessionStorage.removeItem('user_name')
          ElMessage.error('登录已过期，请重新登录')
          window.location.href = '/login'
          break
        case 403:
          ElMessage.error('没有权限执行此操作')
          break
        case 404:
          ElMessage.error('请求的资源不存在')
          break
        case 500:
          ElMessage.error('服务器内部错误')
          break
        default:
          // 尝试获取后端返回的详细错误信息
          const detail = response.data?.detail || response.data?.message || '请求失败'
          ElMessage.error(detail)
      }
    } else {
      ElMessage.error('网络错误，请检查网络连接')
    }
    
    return Promise.reject(error)
  }
)

// 封装常用HTTP方法
export const http = {
  get: <T = any>(url: string, params?: any, config?: any) => api.get<T>(url, { params, ...config }),
  post: <T = any>(url: string, data?: any, config?: any) => api.post<T>(url, data, config),
  put: <T = any>(url: string, data?: any, config?: any) => api.put<T>(url, data, config),
  delete: <T = any>(url: string, config?: any) => api.delete<T>(url, config),
  patch: <T = any>(url: string, data?: any, config?: any) => api.patch<T>(url, data, config)
}

// 导出axios实例供特殊需求使用
export default api
