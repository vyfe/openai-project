import { zhAdmin } from './zh/admin'
import { enAdmin } from './en/admin'
import { zhApps } from './zh/apps'
import { enApps } from './en/apps'
import { zhChat } from './zh/chat'
import { enChat } from './en/chat'
import { zhLogin } from './zh/login'
import { enLogin } from './en/login'
import { zhValidation } from './zh/validation'
import { enValidation } from './en/validation'

const messages = {
  zh: {
    admin: zhAdmin,
    apps: zhApps,
    chat: zhChat,
    login: zhLogin,
    validation: zhValidation,
  },
  en: {
    admin: enAdmin,
    apps: enApps,
    chat: enChat,
    login: enLogin,
    validation: enValidation,
  }
}

export default messages
