import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 部署：Cloudflare Pages / Vercel，构建输出 dist/
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000', // 开发时代理到本地后端
    },
  },
})