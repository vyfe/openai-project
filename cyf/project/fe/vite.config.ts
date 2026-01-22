import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  server: {
    port: 3000,
    proxy: {
      '/never_guess_my_usage': {
        target: process.env.NODE_ENV === 'development' || !process.env.NODE_ENV
          ? 'http://localhost:39997'
          : 'http://aichat.609088523.xyz:39996',
        changeOrigin: true,
      }
    }
  }
})