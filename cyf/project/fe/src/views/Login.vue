<template>
  <div
    class="login-page login-page-v2 min-h-screen flex flex-col justify-center items-center bg-gradient-to-br from-amber-100 via-stone-100 to-emerald-50 relative overflow-hidden"
    :class="{ 'login-dark': isDarkTheme }"
  >
    <div class="login-shell relative z-10">
      <section class="login-hero" aria-hidden="true">
        <div class="hero-vector hero-vector-main" />
        <div class="hero-vector hero-vector-grid" />
        <div class="hero-vector hero-vector-wave" />
        <div class="hero-copy">
          <p class="hero-copy-label">{{ t('login.subtitle') }}</p>
          <h2 class="hero-copy-title">{{ t('login.description') }}</h2>
        </div>
      </section>

      <section class="login-panel">
        <div class="login-card bg-white/95 backdrop-blur-sm rounded-2xl p-10 shadow-xl border border-amber-200/30 w-96 max-w-[90%]">
          <div class="login-head text-center mb-8">
            <h1 class="login-title text-2xl font-bold text-amber-700 mb-2">{{ t('login.title') }}</h1>
            <p class="login-subtitle text-stone-500">{{ t('login.subtitle') }}</p>
          </div>

          <el-form
            ref="loginFormRef"
            :model="loginForm"
            :rules="loginRules"
            class="login-form mt-5"
            @submit.prevent="handleLogin"
          >
            <el-form-item prop="username" class="mb-5">
              <el-input
                v-model="loginForm.username"
                :placeholder="t('login.usernamePlaceholder')"
                :prefix-icon="User"
                size="large"
                class="rounded-lg"
                autocomplete="new-password"
              />
            </el-form-item>

            <el-form-item prop="password" class="mb-5">
              <el-input
                v-model="loginForm.password"
                type="password"
                :placeholder="t('login.passwordPlaceholder')"
                :prefix-icon="Lock"
                size="large"
                show-password
                class="rounded-lg"
                autocomplete="new-password"
              />
            </el-form-item>

            <el-form-item class="w-full">
              <el-button
                type="primary"
                size="large"
                :loading="loading"
                class="login-primary-btn w-full bg-gradient-to-r from-amber-600 to-emerald-600 border-none text-base font-medium h-12 transition-all duration-300 hover:from-amber-700 hover:to-emerald-700 hover:translate-y-[-2px] hover:shadow-lg"
                @click="handleLogin"
              >
                {{ t('login.submitButton') }}
              </el-button>
            </el-form-item>
          </el-form>

          <!-- 注册链接按钮 -->
          <div class="text-center mt-4">
            <el-button
              type="info"
              plain
              size="small"
              @click="showRegisterModal = true"
              :icon="CirclePlus"
              class="login-secondary-btn text-amber-700 hover:text-amber-700"
            >
              {{ t('login.goToRegister') }}
            </el-button>
          </div>

          <!-- 通知按钮 -->
          <div class="mt-4 flex justify-end">
            <div class="notification-button-wrapper">
            <el-button
              type="info"
              plain
              size="small"
              @click="openNotifications"
              :icon="Bell"
            >
              {{ t('login.viewNotifications') }}
            </el-button>
              <span v-if="hasNewNotifications" class="notification-dot" />
            </div>
          </div>
        </div>
      </section>
    </div>

    <div class="login-footer mt-8 text-center">
      <p class="mt-2.5 flex items-center justify-center gap-1">
        <a href="https://github.com/vyfe/openai-project" target="_blank" rel="noopener noreferrer" class="login-footer-link text-stone-500 text-sm font-medium flex items-center gap-1 hover:text-amber-700 hover:underline">
          <el-icon><Link /></el-icon> {{ t('login.githubLink') }}
        </a>
        <span class="login-footer-contact ml-3.5 text-stone-500 font-medium inline-flex items-center"> {{ t('login.contactInfo') }} </span>
      </p>
    </div>

    <!-- 通知模态框 -->
    <Teleport to="body">
      <div v-if="showNotificationModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
        <div class="relative">
          <NotificationPanel
            isModal
            :notifications="notifications"
            :loading="notificationsLoading"
            @close="closeNotifications"
          />
        </div>
      </div>
    </Teleport>

    <!-- 注册弹窗 -->
    <Teleport to="body">
      <div v-if="showRegisterModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
        <div :class="[
          'login-register-modal login-register-modal-v2',
          { 'login-dark-modal': isDarkTheme },
          'rounded-2xl shadow-xl border w-96 max-w-[90%] transition-all duration-300 transform',
          'bg-white/95 backdrop-blur-sm border-amber-200/30'
        ]">
          <!-- 弹窗头部 -->
          <div class="flex items-center justify-between p-5 border-b border-gray-200">
            <h2 class="text-lg font-bold flex items-center text-amber-700">
              <el-icon class="mr-2"><CirclePlus /></el-icon>
              {{ t('login.registerTitle') }}
            </h2>
            <button @click="showRegisterModal = false" class="text-gray-500 hover:text-gray-700 transition-colors">
              <el-icon size="20"><Close /></el-icon>
            </button>
          </div>

          <!-- 弹窗内容 -->
          <div class="p-5">
            <el-form
              ref="registerFormRef"
              :model="registerForm"
              :rules="registerRules"
              class="space-y-4"
            >
              <el-form-item prop="username">
                <el-input
                  v-model="registerForm.username"
                  :placeholder="t('login.usernamePlaceholder')"
                  :prefix-icon="User"
                  size="large"
                  class="rounded-lg"
                  autocomplete="new-password"
                />
              </el-form-item>

              <el-form-item prop="password">
                <el-input
                  v-model="registerForm.password"
                  type="password"
                  :placeholder="t('login.passwordPlaceholder')"
                  :prefix-icon="Lock"
                  size="large"
                  show-password
                  class="rounded-lg"
                  autocomplete="new-password"
                />
              </el-form-item>

              <el-form-item prop="confirmPassword">
                <el-input
                  v-model="registerForm.confirmPassword"
                  type="password"
                  :placeholder="t('validation.confirmPassword')"
                  :prefix-icon="Lock"
                  size="large"
                  show-password
                  class="rounded-lg"
                  autocomplete="new-password"
                />
              </el-form-item>

              <!-- API key 输入框 -->
              <el-form-item prop="apiKey">
                <el-input
                  v-model="registerForm.apiKey"
                  type="password"
                  :placeholder="t('login.apiKeyPlaceholder')"
                  :prefix-icon="Lock"
                  size="large"
                  show-password
                  class="rounded-lg"
                  autocomplete="new-password"
                />
                <template #label>
                  <span class="text-sm">{{ t('login.apiKey') }}</span>
                </template>
              </el-form-item>

              <!-- API key 提示信息 -->
              <div class="text-xs text-gray-500 mb-2 flex items-start gap-1">
                <el-icon><InfoFilled /></el-icon>
                <span>{{ t('login.apiKeyHint') }}</span>
              </div>

              <el-form-item class="mb-0">
                <el-button
                  type="primary"
                  size="large"
                  :loading="registerLoading"
                  class="w-full bg-gradient-to-r from-amber-600 to-emerald-600 border-none text-base font-medium h-12 transition-all duration-300 hover:from-amber-700 hover:to-emerald-700 hover:translate-y-[-2px] hover:shadow-lg"
                  @click="handleRegister"
                >
                  {{ t('login.registerButton') }}
                </el-button>
              </el-form-item>
            </el-form>

            <div class="mt-4 text-center text-sm text-gray-500">
              {{ t('login.goToLogin') }}
              <button
                @click="showRegisterModal = false"
                class="ml-1 text-amber-700 hover:text-amber-700 font-medium underline"
              >
                {{ t('login.submitButton') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, FormInstance, FormRules } from 'element-plus'
import { User, Lock, Link, Bell, CirclePlus, Close, InfoFilled } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { authAPI } from '@/services/api'
import NotificationPanel from '@/components/NotificationPanel.vue'
import { useNotifications } from '@/composables/useNotifications'
import { useThemeManager } from '@/composables/useThemeManager'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const { isDarkTheme, initThemeManager } = useThemeManager()
const loginFormRef = ref()
const loading = ref(false)
const showNotificationModal = ref(false)
const showRegisterModal = ref(false)
const registerFormRef = ref<FormInstance>()
const registerLoading = ref(false)

const loginForm = reactive({
  username: '',
  password: ''
})

const loginRules = {
  username: [
    { required: true, message: t('validation.usernameRequired'), trigger: 'blur' },
    { min: 1, message: t('validation.usernameNotEmpty'), trigger: 'blur' }
  ],
  password: [
    { required: true, message: t('validation.passwordRequired'), trigger: 'blur' },
    { min: 1, message: t('validation.passwordNotEmpty'), trigger: 'blur' }
  ]
}

const registerForm = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  apiKey: ''
})

const { notifications, notificationsLoading, hasNewNotifications, fetchNotifications, markNotificationsRead } = useNotifications()

const openNotifications = () => {
  showNotificationModal.value = true
}

const closeNotifications = () => {
  showNotificationModal.value = false
  markNotificationsRead()
}

const registerRules: FormRules = {
  username: [
    { required: true, message: t('validation.usernameRequired'), trigger: 'blur' },
    { min: 3, max: 20, message: t('validation.usernameMinLength'), trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9_]+$/, message: t('validation.usernameFormat'), trigger: 'blur' }
  ],
  password: [
    { required: true, message: t('validation.passwordRequired'), trigger: 'blur' },
    { min: 6, message: t('validation.passwordMinLength'), trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: t('validation.confirmPasswordRequired'), trigger: 'blur' },
    {
      validator: (rule: any, value: any, callback: any) => {
        if (value !== registerForm.password) {
          callback(new Error(t('validation.passwordsNotMatch')))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ],
  apiKey: []
}

onMounted(() => {
  initThemeManager()
  fetchNotifications()
})

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
          // 登录成功，获取用户信息（包含角色）
          const userData = response.data || { username: loginForm.username, role: 'user' }
          authStore.login({
            username: userData.username || loginForm.username,
            role: userData.role || 'user',
            accessToken: userData.access_token,
            accessTokenExpiresAt: userData.access_token_expires_at,
            refreshToken: userData.refresh_token,
            refreshTokenExpiresAt: userData.refresh_token_expires_at
          })

          ElMessage.success(response.msg || t('login.successMessage'))
          router.push('/chat')
        } else {
          throw new Error(response.msg || t('login.failedMessage'))
        }
      } catch (error: any) {
        console.error('Login error:', error)
        let errorMessage = t('login.failedMessage')
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

const handleRegister = async () => {
  if (!registerFormRef.value) return

  await registerFormRef.value.validate(async (valid: boolean) => {
    if (valid) {
      registerLoading.value = true

      try {
        const response = await authAPI.register(
          registerForm.username,
          registerForm.password,
          registerForm.apiKey || undefined
        )

        if (response && typeof response === 'object' && response.success) {
          ElMessage.success(response.msg || t('login.registerSuccess'))

          // 注册成功后切换到登录模式并预填用户名
          showRegisterModal.value = false
          loginForm.username = registerForm.username
          loginForm.password = ''

          // 清空注册表单
          registerForm.username = ''
          registerForm.password = ''
          registerForm.confirmPassword = ''
          registerForm.apiKey = ''
        } else {
          throw new Error(response.msg || t('login.registerFailed'))
        }
      } catch (error: any) {
        console.error('Registration error:', error)
        let errorMessage = t('login.registerFailed')
        if (error.message) {
          errorMessage = error.message
        } else if (error?.response?.data?.msg) {
          errorMessage = error.response.data.msg
        } else if (typeof error === 'object' && error.msg) {
          errorMessage = error.msg
        }
        ElMessage.error(errorMessage)
      } finally {
        registerLoading.value = false
      }
    }
  })
}
</script>

<style scoped>
.login-page-v2 {
  background:
    radial-gradient(900px 520px at 20% 16%, color-mix(in srgb, var(--accent-1) 14%, transparent), transparent 72%),
    radial-gradient(860px 540px at 88% 84%, color-mix(in srgb, var(--accent-2) 10%, transparent), transparent 74%),
    linear-gradient(180deg, var(--bg-0), color-mix(in srgb, var(--bg-0) 90%, var(--bg-2)));
}

.login-shell {
  width: 100%;
  max-width: 1160px;
  padding: 34px 22px 8px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 460px);
  gap: 28px;
  align-items: center;
}

.login-hero {
  position: relative;
  min-height: 520px;
  border-radius: 24px;
  border: 1px solid color-mix(in srgb, var(--line-1) 76%, transparent);
  background: color-mix(in srgb, var(--overlay-1) 78%, transparent);
  overflow: hidden;
  padding: 36px 34px;
  display: flex;
  align-items: flex-end;
  box-shadow: 0 12px 36px rgba(15, 23, 42, 0.06);
}

.hero-vector {
  position: absolute;
  pointer-events: none;
}

.hero-vector-main {
  inset: -8% -16% auto auto;
  width: 68%;
  height: 68%;
  border-radius: 42% 58% 52% 48%;
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--accent-1) 36%, transparent),
    color-mix(in srgb, var(--accent-2) 14%, transparent)
  );
  filter: blur(2px);
  animation: hero-float 16s ease-in-out infinite;
}

.hero-vector-grid {
  left: 8%;
  top: 10%;
  width: 76%;
  height: 76%;
  background-image:
    linear-gradient(to right, color-mix(in srgb, var(--line-1) 66%, transparent) 1px, transparent 1px),
    linear-gradient(to bottom, color-mix(in srgb, var(--line-1) 66%, transparent) 1px, transparent 1px);
  background-size: 30px 30px;
  mask-image: radial-gradient(circle at 38% 48%, black 30%, transparent 82%);
  opacity: 0.24;
}

.hero-vector-wave {
  inset: auto 0 0;
  height: 42%;
  background:
    radial-gradient(120% 100% at 32% 82%, color-mix(in srgb, var(--accent-2) 22%, transparent), transparent 68%),
    radial-gradient(100% 90% at 66% 86%, color-mix(in srgb, var(--accent-1) 14%, transparent), transparent 68%);
  transform-origin: center;
  animation: hero-wave 20s ease-in-out infinite;
}

.hero-copy {
  position: relative;
  z-index: 2;
  max-width: 540px;
}

.hero-copy-label {
  margin: 0 0 12px;
  font-size: 14px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-2);
}

.hero-copy-title {
  margin: 0;
  font-size: clamp(34px, 4.2vw, 54px);
  line-height: 1.15;
  letter-spacing: -0.02em;
  color: var(--text-1);
  word-break: break-word;
  overflow-wrap: break-word;
}

.login-panel {
  display: flex;
  justify-content: center;
}

.login-card {
  width: min(460px, 100%);
  margin: 0 auto;
  background: var(--overlay-1) !important;
  border: 1px solid var(--line-1) !important;
  border-radius: 20px !important;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08) !important;
  padding: 28px 22px !important;
}

.login-head {
  margin-bottom: 22px;
}

.login-title {
  margin-bottom: 6px !important;
  color: var(--text-1) !important;
  font-size: 26px;
  font-weight: 650;
  letter-spacing: 0;
}

.login-subtitle {
  color: var(--text-2) !important;
  font-size: 14px;
}

.login-form :deep(.el-input__wrapper) {
  border-radius: 12px;
  border: 1px solid var(--line-1);
  box-shadow: none !important;
  background: var(--bg-1);
}

.login-form :deep(.el-input__inner) {
  color: var(--text-1);
}

.login-form :deep(.el-input__inner::placeholder) {
  color: var(--text-2);
}

.login-primary-btn {
  border: 1px solid var(--line-1) !important;
  background: var(--bg-1) !important;
  color: var(--text-1) !important;
  height: 44px !important;
  border-radius: 12px !important;
  box-shadow: none !important;
  transform: none !important;
}

.login-primary-btn:hover {
  background: var(--bg-2) !important;
  box-shadow: none !important;
}

.login-secondary-btn {
  border: 1px solid var(--line-1) !important;
  border-radius: 999px !important;
  color: var(--text-2) !important;
  background: var(--bg-1) !important;
}

.login-secondary-btn:hover {
  color: var(--text-1) !important;
  background: var(--bg-2) !important;
}

.login-footer {
  margin-top: 14px !important;
}

.login-footer-desc,
.login-footer-link,
.login-footer-contact {
  color: var(--text-2) !important;
}

.login-footer-link:hover {
  color: var(--text-1) !important;
}

@keyframes hero-float {
  0%, 100% {
    transform: translate3d(0, 0, 0) scale(1);
    border-radius: 42% 58% 52% 48%;
  }
  50% {
    transform: translate3d(-12px, 10px, 0) scale(1.04);
    border-radius: 56% 44% 48% 52%;
  }
}

@keyframes hero-wave {
  0%, 100% {
    transform: translateX(0) scaleY(1);
  }
  50% {
    transform: translateX(2%) scaleY(1.06);
  }
}

body.dark-theme .login-page-v2 {
  background:
    radial-gradient(900px 520px at 20% 16%, var(--accent-1-soft), transparent 72%),
    radial-gradient(860px 540px at 88% 84%, color-mix(in srgb, var(--accent-2) 18%, transparent), transparent 74%),
    linear-gradient(180deg, var(--bg-0), color-mix(in srgb, var(--bg-0) 90%, var(--bg-2)));
}

body.dark-theme .login-hero,
.login-page.login-dark .login-hero {
  background: color-mix(in srgb, var(--overlay-1) 84%, transparent);
}

body.dark-theme .login-card,
.login-page.login-dark .login-card {
  background: var(--overlay-1) !important;
  border-color: var(--line-1) !important;
}

body.dark-theme .login-title,
body.dark-theme .login-subtitle,
body.dark-theme .login-footer-desc,
body.dark-theme .login-footer-link,
body.dark-theme .login-footer-contact {
  color: var(--text-1) !important;
}

@media (max-width: 768px) {
  .login-shell {
    display: flex;
    justify-content: center;
    padding: 12px 10px 6px;
  }

  .login-hero {
    display: none;
  }

  .login-card {
    width: min(460px, 94vw);
    padding: 20px 16px !important;
    border-radius: 16px !important;
  }

  .login-title {
    font-size: 22px;
  }

  .login-subtitle {
    font-size: 13px;
  }
}
</style>
