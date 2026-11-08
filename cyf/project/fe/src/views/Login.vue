<template>
  <div class="login-page min-h-screen flex flex-col" :class="{ 'login-dark': isDarkTheme }">
    <!-- 顶栏：品牌 + 语言 / 主题 -->
    <header class="login-topbar">
      <div class="login-brand">
        <span class="login-brand__mark" aria-hidden="true">
          <el-icon><ChatDotRound /></el-icon>
        </span>
        <span class="login-brand__title">{{ t('login.title') }}</span>
      </div>
      <div class="login-topbar__actions">
        <el-button
          class="login-topbar__action"
          :icon="SwitchFilled"
          :aria-label="currentLang === 'zh' ? t('chat.languageEnglish') : t('chat.languageChinese')"
          @click="toggleLanguage"
        >
          <span class="login-topbar__action-text">
            {{ currentLang === 'zh' ? t('chat.languageEnglish') : t('chat.languageChinese') }}
          </span>
        </el-button>
        <el-button
          class="login-topbar__action"
          :icon="isDarkTheme ? Sunny : Moon"
          :aria-label="isDarkTheme ? t('chat.lightTheme') : t('chat.darkTheme')"
          @click="toggleTheme"
        >
          <span class="login-topbar__action-text">
            {{ isDarkTheme ? t('chat.lightTheme') : t('chat.darkTheme') }}
          </span>
        </el-button>
      </div>
    </header>

    <main class="login-shell">
      <!-- 功能选择 -->
      <section class="login-features" aria-labelledby="login-feature-title">
        <h1 id="login-feature-title" class="login-features__title">
          {{ t('login.selectFunction') }}
        </h1>
        <p class="login-features__subtitle">{{ t('login.pageTitle') }}</p>

        <div class="login-feature-group" role="radiogroup" aria-labelledby="login-feature-title">
          <label
            v-for="app in LOGIN_APP_KEYS"
            :key="app"
            class="login-feature-card"
            :class="{ 'is-selected': selectedApp === app }"
          >
            <input
              v-model="selectedApp"
              @change="explicitSelection = true"
              class="login-feature-card__input"
              type="radio"
              name="login-app"
              :value="app"
            />
            <span class="login-feature-card__body">
              <span class="login-feature-card__head">
                <el-icon class="login-feature-card__icon"><component :is="APP_META[app].icon" /></el-icon>
                <span class="login-feature-card__name">{{ t(APP_META[app].labelKey) }}</span>
                <span
                  class="login-feature-card__tag"
                  :class="APP_META[app].requiresGrant ? 'is-grant' : 'is-included'"
                >
                  {{ APP_META[app].requiresGrant ? t('login.featureTagGrant') : t('login.featureTagIncluded') }}
                </span>
              </span>
              <span class="login-feature-card__desc">{{ t(APP_META[app].descriptionKey) }}</span>
            </span>
            <el-icon v-if="selectedApp === app" class="login-feature-card__check"><Select /></el-icon>
          </label>
        </div>

        <button type="button" class="login-admin-entry" @click="selectAdminEntry">
          <el-icon><Setting /></el-icon>
          <span>{{ t('login.adminEntry') }}</span>
        </button>
      </section>

      <!-- 表单 -->
      <section class="login-panel">
        <div class="login-card">
          <!-- 已登录：当前账号 -->
          <el-alert v-if="syncFailed" :title="t('login.roleSyncFailed')" type="error" :closable="false" show-icon>
            <el-button :loading="syncing" @click="refreshAuthorization">{{ t('login.retryAuthorization') }}</el-button>
          </el-alert>
          <div v-if="isLoggedIn" class="login-account">
            <span class="login-account__label">{{ t('login.currentAccount') }}</span>
            <span class="login-account__name">{{ authStore.user }}</span>
            <div class="login-account__roles">
              <el-tag v-for="role in authStore.roles" :key="role" size="small" type="info">
                {{ t(`apps.${role === 'admin' ? 'admin' : role}`) }}
              </el-tag>
            </div>
            <div class="login-account__actions">
              <el-button size="small" text @click="switchAccount">{{ t('login.switchAccount') }}</el-button>
              <el-button size="small" text @click="logout">{{ t('login.logout') }}</el-button>
            </div>
          </div>

          <!-- 权限引导 -->
          <div v-if="showGrantGuide" class="login-grant" role="status">
            <h2 class="login-grant__title">{{ grantTitle }}</h2>
            <p class="login-grant__desc">{{ t('login.notEnabledDesc') }}</p>
            <div v-if="availableEntries.length" class="login-grant__entries">
              <span class="login-grant__entries-label">{{ t('login.availableEntries') }}</span>
              <el-button
                v-for="entry in availableEntries"
                :key="entry"
                size="small"
                @click="explicitSelection = true; selectedApp = entry; enterApp(entry)"
              >
                {{ t(APP_META[entry].labelKey) }}
              </el-button>
            </div>
            <div class="login-grant__contact">
              <el-button size="small" type="primary" plain @click="copyContact">
                {{ t('login.contactAdmin') }}
              </el-button>
              <span class="login-grant__contact-text">{{ contactInfo }}</span>
            </div>
          </div>

          <!-- 登录表单 -->
          <div v-if="!isLoggedIn && mode === 'login'" class="login-form-host">
          <el-form
            ref="loginFormRef"
            :model="loginForm"
            :rules="loginRules"
            class="login-form"
            label-position="top"
            @submit.prevent="handleLogin"
          >
            <el-form-item :label="t('validation.username')" prop="username" class="login-form__item">
              <el-input
                ref="usernameInputRef"
                v-model="loginForm.username"
                :placeholder="t('login.usernamePlaceholder')"
                :prefix-icon="User"
                size="large"
                autocomplete="username"
                :disabled="submitting"
              />
            </el-form-item>

            <el-form-item :label="t('validation.password')" prop="password" class="login-form__item">
              <el-input
                v-model="loginForm.password"
                type="password"
                :placeholder="t('login.passwordPlaceholder')"
                :prefix-icon="Lock"
                size="large"
                show-password
                autocomplete="current-password"
                :disabled="submitting"
              />
            </el-form-item>

            <el-form-item class="login-form__item login-form__submit">
              <el-button
                type="primary"
                size="large"
                class="login-primary-btn"
                :loading="submitting"
                :disabled="submitting"
                native-type="submit"
              >
                {{ isLoggedIn ? t('login.enterApp', { app: selectedAppLabel }) : t('login.loginAndEnter', { app: selectedAppLabel }) }}
              </el-button>
            </el-form-item>
          </el-form>
          </div>

          <!-- 注册表单 -->
          <div v-if="!isLoggedIn && mode === 'register'" class="login-form-host">
          <el-form
            ref="registerFormRef"
            :model="registerForm"
            :rules="registerRules"
            class="login-form"
            label-position="top"
            @submit.prevent="handleRegister"
          >
            <p class="login-notice">{{ t('login.registerNotice') }}</p>

            <el-form-item :label="t('validation.username')" prop="username" class="login-form__item">
              <el-input
                v-model="registerForm.username"
                :placeholder="t('login.usernamePlaceholder')"
                :prefix-icon="User"
                size="large"
                autocomplete="username"
                :disabled="registering"
              />
            </el-form-item>

            <el-form-item :label="t('validation.password')" prop="password" class="login-form__item">
              <el-input
                v-model="registerForm.password"
                type="password"
                :placeholder="t('login.passwordPlaceholder')"
                :prefix-icon="Lock"
                size="large"
                show-password
                autocomplete="new-password"
                :disabled="registering"
              />
            </el-form-item>

            <el-form-item :label="t('validation.confirmPassword')" prop="confirmPassword" class="login-form__item">
              <el-input
                v-model="registerForm.confirmPassword"
                type="password"
                :placeholder="t('validation.confirmPassword')"
                :prefix-icon="Lock"
                size="large"
                show-password
                autocomplete="new-password"
                :disabled="registering"
              />
            </el-form-item>

            <!-- 高级设置：API Key -->
            <div class="login-advanced">
              <button
                type="button"
                class="login-advanced__toggle"
                :aria-expanded="advancedOpen"
                @click="advancedOpen = !advancedOpen"
              >
                <el-icon><Setting /></el-icon>
                <span>{{ t('login.advancedSettings') }}</span>
                <el-icon class="login-advanced__caret" :class="{ 'is-open': advancedOpen }"><ArrowDown /></el-icon>
              </button>
              <el-form-item v-show="advancedOpen" label="" prop="apiKey" class="login-form__item">
                <el-input
                  v-model="registerForm.apiKey"
                  type="password"
                  :placeholder="t('login.apiKeyPlaceholder')"
                  :prefix-icon="Lock"
                  size="large"
                  show-password
                  autocomplete="new-password"
                  :disabled="registering"
                />
                <p class="login-form__hint">{{ t('login.apiKeyHint') }}</p>
              </el-form-item>
            </div>

            <!-- 只读初始权限 -->
            <div class="login-permissions">
              <span class="login-permissions__title">{{ t('login.registerPermissionsTitle') }}</span>
              <ul class="login-permissions__list">
                <li class="login-permissions__item is-on">{{ t('login.permissionChat') }}</li>
                <li class="login-permissions__item">{{ t('login.permissionQuant') }}</li>
                <li class="login-permissions__item">{{ t('login.permissionSound') }}</li>
              </ul>
            </div>

            <el-form-item class="login-form__item login-form__submit">
              <el-button
                type="primary"
                size="large"
                class="login-primary-btn"
                :loading="registering"
                :disabled="registering"
                native-type="submit"
              >
                {{ t('login.registerButton') }}
              </el-button>
            </el-form-item>
          </el-form>
          </div>

          <!-- 已登录时的进入按钮 -->
          <div v-if="isLoggedIn" class="login-form__submit login-form__submit--standalone">
            <el-button
              type="primary"
              size="large"
              class="login-primary-btn"
              :disabled="!canEnterSelected"
              @click="enterApp(selectedApp)"
            >
              {{ t('login.enterApp', { app: selectedAppLabel }) }}
            </el-button>
          </div>

          <!-- 模式切换 -->
          <div class="login-switch">
            <el-button
              v-if="mode === 'login'"
              type="info"
              plain
              size="small"
              :icon="CirclePlus"
              :disabled="isLoggedIn"
              @click="switchToRegister"
            >
              {{ t('login.goToRegister') }}
            </el-button>
            <el-button
              v-else
              type="info"
              plain
              size="small"
              :disabled="isLoggedIn"
              @click="switchToLogin"
            >
              {{ t('login.goToLogin') }}
            </el-button>
          </div>
        </div>
      </section>
    </main>

    <footer class="login-footer">
      <p class="login-footer__line">
        <a
          href="https://github.com/vyfe/openai-project"
          target="_blank"
          rel="noopener noreferrer"
          class="login-footer__link"
        >
          <el-icon><Link /></el-icon> {{ t('login.githubLink') }}
        </a>
      </p>
      <p class="login-footer__line">
        <el-button link class="login-footer__copy" @click="copyContact">
          <el-icon><CopyDocument /></el-icon>
          <span>{{ copied ? t('login.copied') : t('login.copyContact') }}</span>
        </el-button>
        <span class="login-footer__contact">{{ contactInfo }}</span>
      </p>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import {
  ArrowDown,
  ChatDotRound,
  CirclePlus,
  CopyDocument,
  Link,
  Lock,
  Moon,
  Select,
  Setting,
  Sunny,
  SwitchFilled,
  User
} from '@element-plus/icons-vue'
import { APP_META, LOGIN_APP_KEYS, type AppKey } from '@/auth/apps'
import { resolveDestination } from '@/auth/destination'
import { syncCurrentRoles } from '@/auth/sync'
import { hasRole, type AppRole } from '@/auth/permissions'
import { useAuthStore } from '@/stores/auth'
import { authAPI } from '@/services/api'
import { useThemeManager } from '@/composables/useThemeManager'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { isDarkTheme, initThemeManager, setThemeManually } = useThemeManager()

const mode = ref<'login' | 'register'>('login')
const selectedApp = ref<AppKey>('chat')
const submitting = ref(false)
const registering = ref(false)
const advancedOpen = ref(false)
const copied = ref(false)
const isLoggedIn = computed(() => Boolean(authStore.user && authStore.refreshToken))
const explicitSelection = ref(false)
const syncing = ref(false)
const syncFailed = ref(false)
const loginFormRef = ref<FormInstance>()
const registerFormRef = ref<FormInstance>()
const usernameInputRef = ref()

const currentLang = ref(locale.value)

const loginForm = ref({ username: '', password: '' })
const registerForm = ref({ username: '', password: '', confirmPassword: '', apiKey: '' })

const contactInfo = computed(() => t('login.contactInfo'))

const selectedAppLabel = computed(() => t(APP_META[selectedApp.value].labelKey))

const requestedDestination = computed(() => {
  const base = resolveDestination({ app: explicitSelection.value ? selectedApp.value : typeof route.query.app === 'string' ? route.query.app : null, redirect: typeof route.query.redirect === 'string' ? route.query.redirect : null }, authStore.roles, authStore.lastApp)
  // 路由守卫把被拒页面所需角色带过来（如 /quant/scheduler 需要 admin）：
  // 该角色才是本次真正缺失的权限，不能用功能入口的角色覆盖。
  const required = route.query.required
  if (typeof required === 'string' && required) {
    return { ...base, requiredRole: required as AppRole }
  }
  return base
})
const canEnterSelected = computed(() => !syncing.value && !syncFailed.value && (!isLoggedIn.value || (authStore.rolesConfirmed && hasRole(authStore.roles, requestedDestination.value.requiredRole))))

const availableEntries = computed<AppKey[]>(() =>
  isLoggedIn.value ? authStore.availableApps.filter((app) => app !== 'admin' || authStore.isAdmin()) : []
)

/** 未开通引导：已登录但目标功能未授权。 */
const showGrantGuide = computed(() => isLoggedIn.value && authStore.rolesConfirmed && !hasRole(authStore.roles, requestedDestination.value.requiredRole))

const grantTitle = computed(() => {
  const required = explicitSelection.value ? APP_META[selectedApp.value].role : route.query.required ?? requestedDestination.value.requiredRole
  if (required === 'admin') return t('login.requiresAdminTitle')
  return t('login.notEnabledTitle')
})

const loginRules: FormRules = {
  username: [
    { required: true, message: t('validation.usernameRequired'), trigger: 'blur' },
    { min: 1, message: t('validation.usernameNotEmpty'), trigger: 'blur' }
  ],
  password: [
    { required: true, message: t('validation.passwordRequired'), trigger: 'blur' },
    { min: 1, message: t('validation.passwordNotEmpty'), trigger: 'blur' }
  ]
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
      validator: (_rule: any, value: any, callback: any) => {
        if (value !== registerForm.value.password) {
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

/** 从 URL 参数解析初始目的地。 */
const applyQueryDestination = () => {
  const queryApp = route.query.app
  const queryRedirect = route.query.redirect
  const resolved = resolveDestination(
    {
      app: typeof queryApp === 'string' ? queryApp : null,
      redirect: typeof queryRedirect === 'string' ? queryRedirect : null
    },
    authStore.roles,
    authStore.lastApp
  )
  selectedApp.value = resolved.app
}

const selectAdminEntry = () => {
  explicitSelection.value = true
  selectedApp.value = 'admin'
  mode.value = 'login'
  nextTick(() => usernameInputRef.value?.focus?.())
}

const switchToRegister = () => {
  mode.value = 'register'
}

const switchToLogin = () => {
  mode.value = 'login'
  loginForm.value.password = ''
}

const switchAccount = () => {
  authStore.logout()
  mode.value = 'login'
  loginForm.value.password = ''
}

const logout = async () => {
  authStore.logout()
  ElMessage.success(t('chat.logoutSuccess'))
}

const copyContact = async () => {
  try {
    await navigator.clipboard.writeText(contactInfo.value)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch (error) {
    console.error('复制联系方式失败:', error)
  }
}

/** 进入目标功能；未授权时展示权限引导，不发起业务请求。 */
const enterApp = async (app: AppKey) => {
  if (!authStore.canAccessApp(app)) {
    selectedApp.value = app
    return
  }
  if (syncFailed.value || !authStore.rolesConfirmed) {
    if (!await refreshAuthorization()) return
  }
  const destination = app === selectedApp.value ? requestedDestination.value : resolveDestination({ app }, authStore.roles)
  if (!hasRole(authStore.roles, destination.requiredRole)) return
  const target = destination.route
  authStore.setLastApp(app)
  await router.push(target)
}

const handleLogin = async () => {
  if (submitting.value) return
  const form = loginFormRef.value
  if (!form) return

  const valid = await form.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const response: any = await authAPI.login(loginForm.value.username, loginForm.value.password)
    if (!response?.success) {
      throw new Error(response?.msg || t('login.failedMessage'))
    }
    authStore.login(response.data || {})
    authStore.setLastApp(selectedApp.value)

    if (!authStore.canAccessApp(selectedApp.value)) {
      // 认证成功但目标未开通：保留登录态，展示权限引导。
      ElMessage.warning(t('login.notEnabledTitle'))
      return
    }
    ElMessage.success(response.msg || t('login.successMessage'))
    await enterApp(selectedApp.value)
  } catch (error: any) {
    const message = error?.response?.data?.msg || error?.msg || error?.message || t('login.failedMessage')
    ElMessage.error(message)
    await nextTick()
    usernameInputRef.value?.focus?.()
  } finally {
    submitting.value = false
  }
}

const handleRegister = async () => {
  if (registering.value) return
  const form = registerFormRef.value
  if (!form) return

  const valid = await form.validate().catch(() => false)
  if (!valid) return

  registering.value = true
  try {
    const response: any = await authAPI.register(
      registerForm.value.username,
      registerForm.value.password,
      registerForm.value.apiKey || undefined
    )
    if (!response?.success) {
      throw new Error(response?.msg || t('login.registerFailed'))
    }
    ElMessage.success(response.msg || t('login.registerSuccess'))
    // 注册成功回到登录表单：预填用户名、清空密码、目标设为聊天。
    loginForm.value.username = registerForm.value.username
    loginForm.value.password = ''
    registerForm.value = { username: '', password: '', confirmPassword: '', apiKey: '' }
    advancedOpen.value = false
    mode.value = 'login'
    explicitSelection.value = true
    selectedApp.value = 'chat'
    await nextTick()
    usernameInputRef.value?.focus?.()
  } catch (error: any) {
    const message = error?.response?.data?.msg || error?.msg || error?.message || t('login.registerFailed')
    ElMessage.error(message)
  } finally {
    registering.value = false
  }
}

const toggleLanguage = () => {
  const nextLocale = currentLang.value === 'zh' ? 'en' : 'zh'
  locale.value = nextLocale
  currentLang.value = nextLocale
  localStorage.setItem('locale', nextLocale)
}

const toggleTheme = () => {
  setThemeManually(!isDarkTheme.value)
}

const refreshAuthorization = async () => {
  syncing.value = true
  syncFailed.value = false
  const snapshot = await syncCurrentRoles()
  syncFailed.value = !snapshot && isLoggedIn.value
  syncing.value = false
  return Boolean(snapshot)
}

watch(() => route.fullPath, () => {
  explicitSelection.value = false
  applyQueryDestination()
})

onMounted(async () => {
  initThemeManager()
  authStore.isAuthenticated()
  if (isLoggedIn.value) await refreshAuthorization()
  applyQueryDestination()
  const destination = requestedDestination.value
  if (isLoggedIn.value && authStore.rolesConfirmed && destination.fromDeepLink && hasRole(authStore.roles, destination.requiredRole)) {
    authStore.setLastApp(destination.app)
    await router.replace(destination.route)
  }
})

</script>

<style scoped>
.login-page {
  background:
    radial-gradient(900px 520px at 20% 16%, color-mix(in srgb, var(--accent-1) 14%, transparent), transparent 72%),
    radial-gradient(860px 540px at 88% 84%, color-mix(in srgb, var(--accent-2) 10%, transparent), transparent 74%),
    linear-gradient(180deg, var(--bg-0), color-mix(in srgb, var(--bg-0) 90%, var(--bg-2)));
  color: var(--text-1);
}

.login-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 18px clamp(16px, 4vw, 48px);
}

.login-brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.login-brand__mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 10px;
  color: var(--text-1);
  background: var(--overlay-1);
  border: 1px solid var(--line-1);
}

.login-brand__title {
  font-size: 20px;
  font-weight: 650;
  letter-spacing: 0.02em;
}

.login-topbar__actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.login-topbar__action {
  margin-left: 0;
}

.login-shell {
  width: 100%;
  max-width: 1160px;
  margin: 0 auto;
  padding: 12px clamp(16px, 4vw, 32px) 24px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(340px, 420px);
  gap: clamp(20px, 3vw, 40px);
  align-items: start;
}

.login-features__title {
  margin: 0 0 6px;
  font-size: clamp(20px, 2.4vw, 26px);
  font-weight: 650;
}

.login-features__subtitle {
  margin: 0 0 20px;
  font-size: 14px;
  color: var(--text-2);
}

.login-feature-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.login-feature-card {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px 18px;
  border-radius: 14px;
  border: 1px solid var(--line-1);
  background: var(--overlay-1);
  cursor: pointer;
  transition: border-color 0.18s ease, transform 0.18s ease, box-shadow 0.18s ease;
}

.login-feature-card:hover {
  transform: translateY(-1px);
}

.login-feature-card.is-selected {
  border-color: var(--accent-1);
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08);
}

.login-feature-card:focus-within {
  outline: 2px solid var(--accent-1);
  outline-offset: 2px;
}

.login-feature-card__input {
  position: absolute;
  opacity: 0;
  width: 1px;
  height: 1px;
  pointer-events: none;
}

.login-feature-card__body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.login-feature-card__head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.login-feature-card__icon {
  color: var(--text-2);
}

.login-feature-card.is-selected .login-feature-card__icon {
  color: var(--accent-1);
}

.login-feature-card__name {
  font-size: 16px;
  font-weight: 600;
}

.login-feature-card__tag {
  font-size: 12px;
  line-height: 1;
  padding: 4px 8px;
  border-radius: 999px;
  border: 1px solid var(--line-1);
  color: var(--text-2);
}

.login-feature-card__tag.is-included {
  color: var(--text-1);
}

.login-feature-card__desc {
  font-size: 13px;
  color: var(--text-2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.login-feature-card__check {
  margin-left: auto;
  color: var(--accent-1);
}

.login-admin-entry {
  margin-top: 16px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  padding: 4px 0;
  color: var(--text-2);
  font-size: 13px;
  cursor: pointer;
}

.login-admin-entry:hover {
  color: var(--text-1);
  text-decoration: underline;
}

.login-card {
  border-radius: 18px;
  border: 1px solid var(--line-1);
  background: var(--overlay-1);
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
  padding: 24px 22px;
}

.login-account {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-bottom: 16px;
  margin-bottom: 16px;
  border-bottom: 1px solid var(--line-1);
}

.login-account__label {
  font-size: 12px;
  color: var(--text-2);
}

.login-account__name {
  font-size: 18px;
  font-weight: 650;
}

.login-account__roles {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 2px;
}

.login-account__actions {
  display: flex;
  gap: 4px;
  margin-top: 4px;
}

.login-grant {
  padding: 14px 16px;
  margin-bottom: 16px;
  border-radius: 12px;
  border: 1px solid color-mix(in srgb, var(--accent-2) 42%, var(--line-1));
  background: color-mix(in srgb, var(--accent-2) 8%, transparent);
}

.login-grant__title {
  margin: 0 0 6px;
  font-size: 15px;
  font-weight: 650;
}

.login-grant__desc {
  margin: 0 0 10px;
  font-size: 13px;
  color: var(--text-2);
}

.login-grant__entries {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.login-grant__entries-label {
  font-size: 12px;
  color: var(--text-2);
}

.login-grant__contact {
  display: flex;
  align-items: center;
  gap: 8px;
}

.login-grant__contact-text {
  font-size: 13px;
  color: var(--text-2);
}

.login-form__item {
  margin-bottom: 16px;
}

.login-form__submit {
  margin-bottom: 8px;
}

.login-form__submit--standalone {
  margin-top: 4px;
}

.login-form__hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--text-2);
}

.login-notice {
  margin: 0 0 14px;
  font-size: 13px;
  color: var(--text-2);
}

.login-primary-btn {
  width: 100%;
  height: 46px;
  font-size: 15px;
  font-weight: 500;
  border-radius: 12px;
}

.login-advanced {
  margin-bottom: 14px;
}

.login-advanced__toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  padding: 4px 0;
  color: var(--text-2);
  font-size: 13px;
  cursor: pointer;
}

.login-advanced__toggle:hover {
  color: var(--text-1);
}

.login-advanced__caret {
  transition: transform 0.18s ease;
}

.login-advanced__caret.is-open {
  transform: rotate(180deg);
}

.login-permissions {
  padding: 12px 14px;
  margin-bottom: 16px;
  border-radius: 12px;
  border: 1px solid var(--line-1);
  background: var(--bg-1);
}

.login-permissions__title {
  font-size: 12px;
  color: var(--text-2);
}

.login-permissions__list {
  margin: 8px 0 0;
  padding-left: 18px;
  font-size: 13px;
  color: var(--text-2);
}

.login-permissions__item.is-on {
  color: var(--text-1);
}

.login-switch {
  margin-top: 12px;
  text-align: center;
}

.login-footer {
  margin-top: auto;
  padding: 16px clamp(16px, 4vw, 48px) 28px;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px 24px;
}

.login-footer__line {
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.login-footer__link,
.login-footer__contact {
  font-size: 13px;
  color: var(--text-2);
}

.login-footer__link:hover {
  color: var(--text-1);
  text-decoration: underline;
}

.login-footer__copy {
  color: var(--text-2);
  font-size: 13px;
}

.login-footer__copy:hover {
  color: var(--text-1);
}

@media (max-width: 900px) {
  .login-shell {
    grid-template-columns: minmax(0, 1fr);
    max-width: 560px;
  }
}

@media (max-width: 480px) {
  .login-topbar {
    padding: 14px 14px 4px;
  }

  /* 窄屏收起按钮文案，只留图标，避免顶栏撑出水平滚动 */
  .login-topbar__action-text {
    display: none;
  }

  .login-shell {
    padding: 8px 12px 20px;
  }

  .login-card {
    padding: 18px 16px;
  }

  .login-feature-card {
    padding: 14px;
  }

  .login-feature-card__desc {
    white-space: normal;
  }
}
</style>
