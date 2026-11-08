/**
 * 功能入口元数据：角色到入口的映射、标签键、图标与默认路由。
 *
 * 顶栏模块切换、登录页功能卡片、路由 `requiredRole` 元信息共用这一份配置，
 * 避免各处各自维护一份「角色 → 入口」映射。
 */
import type { Component } from 'vue'
import { ChatDotRound, DataBoard, Headset, Setting } from '@element-plus/icons-vue'
import type { AppRole } from './permissions'

export type AppKey = 'chat' | 'quant' | 'sound' | 'admin'

export interface AppMeta {
  key: AppKey
  /** 对应角色；管理员入口对应 admin */
  role: AppRole
  /** i18n 标签键 */
  labelKey: string
  /** i18n 描述键（登录页功能卡） */
  descriptionKey: string
  /** 是否需要管理员授权 */
  requiresGrant: boolean
  /** 默认路由 */
  route: string
  icon: Component
}

export const APP_META: Record<AppKey, AppMeta> = {
  chat: {
    key: 'chat',
    role: 'chat',
    labelKey: 'apps.chat',
    descriptionKey: 'apps.chatDescription',
    requiresGrant: false,
    route: '/chat',
    icon: ChatDotRound
  },
  quant: {
    key: 'quant',
    role: 'quant',
    labelKey: 'apps.quant',
    descriptionKey: 'apps.quantDescription',
    requiresGrant: true,
    route: '/quant/overview',
    icon: DataBoard
  },
  sound: {
    key: 'sound',
    role: 'sound',
    labelKey: 'apps.sound',
    descriptionKey: 'apps.soundDescription',
    requiresGrant: true,
    route: '/studio/voice',
    icon: Headset
  },
  admin: {
    key: 'admin',
    role: 'admin',
    labelKey: 'apps.admin',
    descriptionKey: 'apps.adminDescription',
    requiresGrant: true,
    route: '/admin',
    icon: Setting
  }
}

/** 功能选择顺序：聊天 → 量化 → 声音 → 管理 */
export const APP_ORDER: AppKey[] = ['chat', 'quant', 'sound', 'admin']

/** 登录页展示的三个业务功能（不含管理员入口） */
export const LOGIN_APP_KEYS: AppKey[] = ['chat', 'quant', 'sound']

export const isAppKey = (value: unknown): value is AppKey =>
  typeof value === 'string' && (APP_ORDER as string[]).includes(value)

export const appMeta = (key: AppKey): AppMeta => APP_META[key]

/** 角色对应的入口；管理员入口不通过业务角色映射。 */
export const appForRole = (role: AppRole): AppKey | null => {
  if (role === 'admin') return 'admin'
  const found = APP_ORDER.find((key) => APP_META[key].role === role)
  return found ?? null
}
