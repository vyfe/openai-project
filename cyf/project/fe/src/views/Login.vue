<template>
  <div class="min-h-screen flex flex-col justify-center items-center bg-gradient-to-br from-blue-100 via-sky-100 to-cyan-50 relative overflow-hidden">
    <!-- Background floating animation -->
    <div class="absolute -top-1/2 -left-1/2 w-[200%] h-[200%] bg-radial-gradient animate-float"></div>

    <div class="relative z-10 flex items-start gap-6">
      <div class="bg-white/95 backdrop-blur-sm rounded-2xl p-10 shadow-xl border border-blue-200/30 w-96 max-w-[90%]">
        <div class="text-center mb-8">
          <h1 class="text-2xl font-bold text-indigo-600 mb-2">智能对话系统</h1>
          <p class="text-blue-400">登录您的账户</p>
        </div>

        <el-form
          ref="loginFormRef"
          :model="loginForm"
          :rules="loginRules"
          class="mt-5"
          @submit.prevent="handleLogin"
        >
          <el-form-item prop="username" class="mb-5">
            <el-input
              v-model="loginForm.username"
              placeholder="请输入用户名"
              :prefix-icon="User"
              size="large"
              class="rounded-lg"
            />
          </el-form-item>

          <el-form-item prop="password" class="mb-5">
            <el-input
              v-model="loginForm.password"
              type="password"
              placeholder="请输入密码"
              :prefix-icon="Lock"
              size="large"
              show-password
              class="rounded-lg"
            />
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              size="large"
              :loading="loading"
              class="w-full bg-gradient-to-r from-blue-500 to-cyan-400 border-none text-base font-medium h-12 transition-all duration-300 hover:from-blue-600 hover:to-cyan-500 hover:translate-y-[-2px] hover:shadow-lg"
              @click="handleLogin"
            >
              登录
            </el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- 通知信息组件 -->
      <NotificationPanel />
    </div>

    <div class="mt-8 text-center">
      <p class="text-blue-400">体验智能对话，让AI为您服务</p>
      <p class="mt-2.5 flex items-center justify-center gap-1">
        <a href="https://github.com/vyfe/openai-project" target="_blank" rel="noopener noreferrer" class="text-blue-400 text-sm font-medium flex items-center gap-1 hover:text-indigo-600 hover:underline">
          <el-icon><Link /></el-icon> 开源项目 GitHub
        </a>
        <span class="ml-3.5 text-blue-400 font-medium inline-flex items-center"> vx:pata_data_studio </span>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, Link } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { authAPI } from '@/services/api'
import NotificationPanel from '@/components/NotificationPanel.vue'

const router = useRouter()
const authStore = useAuthStore()
const loginFormRef = ref()
const loading = ref(false)

const loginForm = reactive({
  username: '',
  password: '' // 在实际应用中，后端似乎不需要密码，只需用户名
})

const loginRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 1, message: '用户名不能为空', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 1, message: '密码不能为空', trigger: 'blur' }
  ]
}

const handleLogin = async () => {
  if (!loginFormRef.value) return

  await loginFormRef.value.validate(async (valid: boolean) => {
    if (valid) {
      loading.value = true

      try {
        // 使用新的登录接口进行身份验证
        const response = await authAPI.login(loginForm.username, loginForm.password)

        // 现在我们可以确保response是一个对象，包含success和msg属性
        if (response && typeof response === 'object' && response.success) {
          // 登录成功
          authStore.login({
            username: loginForm.username,
            password: loginForm.password
          })

          ElMessage.success(response.msg || '登录成功！')
          router.push('/chat')
        } else {
          throw new Error(response.msg || '登录失败')
        }
      } catch (error: any) {
        console.error('Login error:', error)
        let errorMessage = '登录失败，请检查用户名和密码'
        if (error.message) {
          errorMessage = error.message
        } else if (error?.response?.data?.msg) {
          errorMessage = error.response.data.msg
        } else if (typeof error === 'object' && error.msg) {
          errorMessage = error.msg
        }
        ElMessage.error(errorMessage)
      } finally {
        loading.value = false
      }
    }
  })
}
</script>

<style scoped>
@keyframes float {
  0%, 100% { transform: translateY(0px) rotate(0deg); }
  50% { transform: translateY(-20px) rotate(180deg); }
}

.animate-float {
  animation: float 6s ease-in-out infinite;
}

.bg-radial-gradient {
  background: radial-gradient(circle, rgba(144, 200, 248, 0.1) 0%, transparent 70%);
}

/* 深色主题样式 */
@media (prefers-color-scheme: dark) {
  .min-h-screen {
    background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 50%, #1a1a1a 100%) !important;
  }

  .bg-radial-gradient {
    background: radial-gradient(circle, rgba(85, 85, 85, 0.1) 0%, transparent 70%) !important;
  }

  .bg-white\/95 {
    background: rgba(34, 34, 34, 0.95) !important;
    color: white !important;
  }

  .border-blue-200\/30 {
    border: 1px solid rgba(85, 85, 85, 0.3) !important;
  }

  .text-indigo-600 {
    color: #e0e0e0 !important;
  }

  .text-blue-400 {
    color: #9a9a9a !important;
  }

  .hover\:text-indigo-600:hover {
    color: #e0e0e0 !important;
  }

  .el-input__wrapper {
    background: rgba(50, 50, 50, 0.9) !important;
    border: 1px solid #555 !important;
    color: white !important;
  }

  .el-input__inner {
    background: rgba(50, 50, 50, 0.9) !important;
    color: white !important;
  }

  .el-input__inner::placeholder {
    color: #aaa !important;
  }

  .el-input__suffix {
    color: #aaa !important;
  }

  .el-button {
    --el-button-bg-color: #409eff !important;
    --el-button-border-color: #409eff !important;
    --el-button-text-color: #ffffff !important;
    --el-button-hover-text-color: #ffffff !important;
    --el-button-hover-bg-color: #66b1ff !important;
    --el-button-hover-border-color: #66b1ff !important;
  }

  .border {
    border: 1px solid #555 !important;
  }

  .bg-gradient-to-r.from-blue-500.to-cyan-400 {
    background: linear-gradient(135deg, #5a7bc1 0%, #7a9ccc 100%) !important;
    color: white !important;
  }

  .hover\:from-blue-600.hover\:to-cyan-500:hover {
    background: linear-gradient(135deg, #6a9a6a 0%, #8ab88a 100%) !important;
    box-shadow: 0 10px 20px rgba(122, 168, 122, 0.3) !important;
    transform: translateY(-2px) !important;
  }
}

.el-input__inner,
.el-textarea__inner {
  background-color: #e4e4e4;
  color: #4b4b4b;
}
</style>