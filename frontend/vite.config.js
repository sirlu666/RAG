import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const apiTarget = process.env.MATHRAG_API_TARGET || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: process.env.MATHRAG_LAN_HOST || '127.0.0.1',
    port: Number(process.env.MATHRAG_FRONTEND_PORT || 5173),
    strictPort: true,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: false,
      },
      '/docs': { target: apiTarget, changeOrigin: false },
      '/openapi.json': { target: apiTarget, changeOrigin: false },
    },
  },
})
