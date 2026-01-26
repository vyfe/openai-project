import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// 为了处理 process 变量的类型问题
declare global {
  var process: {
    env: {
      NODE_ENV?: string;
      npm_package_version?: string;
    };
  };
}

// 在ES模块中获取当前目录路径
const __dirname = resolve('.');

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  define: {
    __APP_VERSION__: JSON.stringify(process.env.npm_package_version || Date.now().toString()),
    __BUILD_TIME__: JSON.stringify(new Date().toISOString())
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