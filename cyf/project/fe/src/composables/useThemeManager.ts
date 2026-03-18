import { ref } from 'vue'

const THEME_KEY = 'isDarkTheme'
const MANUAL_OVERRIDE_KEY = 'themeManualOverride'
const NIGHT_START_HOUR = 19
const NIGHT_END_HOUR = 7

const isDarkTheme = ref(false)

let initialized = false
let autoCheckTimer: number | null = null

const isNightTime = () => {
  const currentHour = new Date().getHours()
  return currentHour >= NIGHT_START_HOUR || currentHour < NIGHT_END_HOUR
}

const hasUserManuallySetTheme = () => localStorage.getItem(MANUAL_OVERRIDE_KEY) === 'true'

const getStoredTheme = () => localStorage.getItem(THEME_KEY) === 'true'

const setManualOverride = (manual: boolean) => {
  localStorage.setItem(MANUAL_OVERRIDE_KEY, String(manual))
}

const setStoredTheme = (dark: boolean) => {
  localStorage.setItem(THEME_KEY, String(dark))
}

const applyThemeClasses = (dark: boolean) => {
  document.body.classList.toggle('dark-theme', dark)
  document.body.classList.toggle('dark', dark)
  document.documentElement.classList.toggle('dark', dark)
}

const syncThemeFromRules = () => {
  const nextDark = hasUserManuallySetTheme() ? getStoredTheme() : isNightTime()
  isDarkTheme.value = nextDark
  applyThemeClasses(nextDark)
  setStoredTheme(nextDark)
}

const autoSwitchTheme = () => {
  const autoDark = isNightTime()
  const isManual = hasUserManuallySetTheme()
  const currentStoredTheme = getStoredTheme()

  if (isManual) {
    if (currentStoredTheme === autoDark) {
      // 用户手动选择和自动规则已经一致，回到自动模式
      setManualOverride(false)
    } else {
      isDarkTheme.value = currentStoredTheme
      applyThemeClasses(currentStoredTheme)
      return
    }
  }

  isDarkTheme.value = autoDark
  applyThemeClasses(autoDark)
  setStoredTheme(autoDark)
}

const handleVisibilityChange = () => {
  if (!document.hidden) {
    autoSwitchTheme()
  }
}

const handleStorageChange = (event: StorageEvent) => {
  if (event.key === THEME_KEY || event.key === MANUAL_OVERRIDE_KEY) {
    syncThemeFromRules()
  }
}

const initThemeManager = () => {
  if (initialized) {
    syncThemeFromRules()
    return
  }

  initialized = true
  syncThemeFromRules()
  autoSwitchTheme()

  autoCheckTimer = window.setInterval(autoSwitchTheme, 60_000)
  document.addEventListener('visibilitychange', handleVisibilityChange)
  window.addEventListener('storage', handleStorageChange)
}

const setThemeManually = (dark: boolean) => {
  setManualOverride(true)
  setStoredTheme(dark)
  isDarkTheme.value = dark
  applyThemeClasses(dark)
}

export const useThemeManager = () => ({
  isDarkTheme,
  initThemeManager,
  syncThemeFromRules,
  setThemeManually,
  setManualOverride,
})

