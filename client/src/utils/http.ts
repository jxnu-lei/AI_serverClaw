import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({
  baseURL: '',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器：自动添加 token
http.interceptors.request.use(
  (config) => {
    const token = sessionStorage.getItem('token') || sessionStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器：统一错误处理
http.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    if (error.response) {
      const status = error.response.status
      const detail = error.response.data?.detail

      switch (status) {
        case 401:
          // token 过期或无效
          sessionStorage.removeItem('token')
          sessionStorage.removeItem('access_token')
          sessionStorage.removeItem('user_id')
          sessionStorage.removeItem('user_role')
          sessionStorage.removeItem('user_name')
          ElMessage.error('登录已过期，请重新登录')
          // 如果有 router 可以跳转登录页
          setTimeout(() => {
            window.location.href = '/login'
          }, 1500)
          break
        case 403:
          ElMessage.error('没有权限执行此操作')
          break
        case 404:
          // 不自动提示，让调用方处理
          break
        case 422:
          ElMessage.error(detail || '请求参数错误')
          break
        case 500:
          ElMessage.error('服务器内部错误')
          break
        default:
          // 不自动提示，让调用方处理
          break
      }
    } else if (error.code === 'ECONNABORTED') {
      ElMessage.error('请求超时，请检查网络')
    } else if (!error.response) {
      ElMessage.error('网络连接失败')
    }

    return Promise.reject(error)
  }
)

export default http