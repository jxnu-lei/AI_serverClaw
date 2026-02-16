import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiHost = env.VITE_API_HOST || 'http://127.0.0.1:8000'
  const wsHost = apiHost.replace('http', 'ws')

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      }
    },
    server: {
      port: 5173,
      proxy: {
        // WebSocket 代理 —— 必须放在 /api 前面，优先匹配
        '/api/ws': {
          target: wsHost,
          ws: true,
          changeOrigin: true,
        },
        // 普通 API 代理
        '/api': {
          target: apiHost,
          changeOrigin: true,
        }
      }
    }
  }
})
