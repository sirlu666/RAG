import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5173,
    proxy: {
      // 后端在 8000，前端统一写 /api/xxx，避免 CORS 与环境变量分叉
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        // SSE 必须关闭代理缓冲，否则"流式"会变成一次性返回
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq) => {
            proxyReq.setHeader('Accept-Encoding', 'identity')
          })
        },
      },
    },
  },
})
