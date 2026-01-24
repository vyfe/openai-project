<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <h1>智能对话系统</h1>
        <p>登录您的账户</p>
      </div>
      
      <el-form
        ref="loginFormRef"
        :model="loginForm"
        :rules="loginRules"
        class="login-form"
        @submit.prevent="handleLogin"
      >
        <el-form-item prop="username">
          <el-input
            v-model="loginForm.username"
            placeholder="请输入用户名"
            :prefix-icon="User"
            size="large"
          />
        </el-form-item>
        
        <el-form-item prop="password">
          <el-input
            v-model="loginForm.password"
            type="password"
            placeholder="请输入密码"
            :prefix-icon="Lock"
            size="large"
            show-password
          />
        </el-form-item>
        
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            class="login-button"
            @click="handleLogin"
          >
            登录
          </el-button>
        </el-form-item>
      </el-form>
    </div>
    
    <div class="login-footer">
      <p>体验智能对话，让AI为您服务</p>
      <p class="github-link-login">
        <a href="https://github.com/vyfe/openai-project" target="_blank" rel="noopener noreferrer">
          <el-icon><Link /></el-icon> 开源项目 GitHub
        </a>
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

        if (response && response.success) {
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
        } else if (error.response?.data?.msg) {
          errorMessage = error.response.data.msg
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
.login-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  background: linear-gradient(135deg, #d4e8d4 0%, #e8f5e8 50%, #f0f8e8 100%);
  position: relative;
  overflow: hidden;
}

.login-container::before {
  content: '';
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle, rgba(144, 238, 144, 0.1) 0%, transparent 70%);
  animation: float 6s ease-in-out infinite;
}

@keyframes float {
  0%, 100% { transform: translateY(0px) rotate(0deg); }
  50% { transform: translateY(-20px) rotate(180deg); }
}

.login-card {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-radius: 20px;
  padding: 40px;
  box-shadow: 0 20px 40px rgba(144, 238, 144, 0.2);
  border: 1px solid rgba(144, 238, 144, 0.3);
  width: 400px;
  max-width: 90%;
  position: relative;
  z-index: 1;
}

.login-header {
  text-align: center;
  margin-bottom: 30px;
}

.login-header h1 {
  color: #5a8a5a;
  font-size: 28px;
  font-weight: 600;
  margin-bottom: 8px;
}

.login-header p {
  color: #7a9c7a;
  font-size: 16px;
  margin: 0;
}

.login-form {
  margin-top: 20px;
}

.login-form .el-form-item {
  margin-bottom: 20px;
}

.login-form .el-input {
  background: rgba(232, 245, 232, 0.3);
  border-radius: 10px;
}

.login-form .el-input__wrapper {
  background: transparent;
  border: 1px solid #c0e0c0;
  box-shadow: none;
}

.login-form .el-input__wrapper:hover {
  border-color: #90ee90;
}

.login-form .el-input__wrapper:focus-within {
  border-color: #7dd87d;
  box-shadow: 0 0 0 2px rgba(144, 238, 144, 0.2);
}

.login-button {
  width: 100%;
  background: linear-gradient(135deg, #9acd32 0%, #7dd87d 100%);
  border: none;
  border-radius: 10px;
  font-size: 16px;
  font-weight: 500;
  height: 48px;
  transition: all 0.3s ease;
}

.login-button:hover {
  background: linear-gradient(135deg, #8fbc8f 0%, #6cc06c 100%);
  transform: translateY(-2px);
  box-shadow: 0 10px 20px rgba(144, 238, 144, 0.3);
}

.login-button:active {
  transform: translateY(0);
}

.login-footer {
  margin-top: 30px;
  text-align: center;
}

.login-footer p {
  color: #7a9c7a;
  font-size: 14px;
  margin: 0;
}

.login-footer .github-link-login {
  margin-top: 10px;
}

.login-footer .github-link-login a {
  color: #7a9c7a;
  text-decoration: none;
  font-size: 13px;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.login-footer .github-link-login a:hover {
  color: #5a8a5a;
  text-decoration: underline;
}
</style>