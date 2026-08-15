import { createI18n } from 'vue-i18n'
import messages from './locales'

/**
 * 国际化入口。i18n 语言包按域拆到 src/locales/{zh,en}/{chat,admin,login,validation}.ts。
 * 新增 key 时：
 *   - 同步在两个语言目录下都补齐（哪怕只翻译中文）
 *   - 域归属尽量贴近现有命名空间，避免新增 'misc'
 */
const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: 'zh',
  fallbackLocale: 'en',
  messages
})

export default i18n
