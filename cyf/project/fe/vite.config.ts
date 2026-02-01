import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import tailwindcss from '@tailwindcss/vite'

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
  plugins: [vue(),tailwindcss(),],
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
          : 'http://chat-h.cc/:39996',
        changeOrigin: true,
      }
    }
  },
  build: {
    // 启用代码分割，生成更多文件块
    rollupOptions: {
      output: {
        // 手动代码分割策略
        manualChunks: {
          // Vue相关库打包在一起
          'vue-vendor': ['vue', 'vue-router', 'pinia'],
          // UI组件库
          'ui-vendor': ['element-plus', '@element-plus/icons-vue'],
          // 工具库
          'utils-vendor': ['axios', 'highlight.js', 'marked', 'html-to-image'],
          // 数学公式库
          'math-vendor': ['katex'],
          // 国际化
          'i18n-vendor': ['vue-i18n'],
          // Tailwind CSS
          'tailwind-vendor': ['tailwindcss']
        },
        // 优化chunk大小，生成更多小文件
        chunkFileNames: 'assets/[name]-[hash].js',
        entryFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash].[ext]'
      }
    },
    // 启用压缩和优化
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true, // 删除console.log
        drop_debugger: true, // 删除debugger
        pure_funcs: ['console.log', 'console.info', 'console.debug'] // 删除指定函数
      },
      mangle: {
        toplevel: true // 混淆顶层作用域变量名
      }
    },
    // 启用CSS代码分割
    cssCodeSplit: true,
    // 启用资源优化
    assetsInlineLimit: 4096, // 小于4KB的资源内联
    // 启用tree shaking
    treeShaking: true,
    // 生成source map（生产环境可关闭）
    sourcemap: false,
    // 目标浏览器
    target: 'es2015',
    // 报告压缩大小
    reportCompressedSize: true
  }
})