/**
 * i18n locale 结构与一致性测试。
 *
 * 锁住以下不变量（任一被破坏即报错）：
 * 1. messages 默认导出形如 `{ zh: {...}, en: {...} }`
 * 2. zh 与 en 的顶层命名空间集合完全一致
 * 3. zh 与 en 每个命名空间内的 leaf key 集合完全一致（防止翻译漏写）
 * 4. 已知 sample key 能正确解析（防止再出现"嵌套双层 chat.chat"这种 bug）
 * 5. 任何 zh/en leaf key 值都是非空字符串
 *
 * 历史背景：2026-08-15 重构 i18n 时，每个 locale 文件多包了一层
 * `chat:/admin:/login:/validation:` 包装，导致 messages 结构变成
 * `messages.zh.chat = { chat: {...} }`，前端 `t('chat.title')` 取不到值。
 * 本测试就是这条 bug 的回归防线。
 */

import { describe, it, expect } from 'vitest'
import messages from '@/locales'

// ─── helpers ───

/** 按点分割的路径解析（语义同 vue-i18n 的 t()） */
function resolve(obj: any, key: string): unknown {
  if (!obj) return undefined
  const parts = key.split('.')
  let cur: any = obj
  for (const p of parts) {
    if (cur && typeof cur === 'object' && p in cur) {
      cur = cur[p]
    } else {
      return undefined
    }
  }
  return cur
}

/** 递归收集对象里所有的"叶子 key 路径"（值为字符串或数字） */
function collectLeafKeys(obj: any, prefix = ''): string[] {
  if (obj === null || obj === undefined) return []
  if (typeof obj !== 'object') return [prefix].filter(Boolean)
  const keys: string[] = []
  for (const [k, v] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${k}` : k
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      keys.push(...collectLeafKeys(v, path))
    } else {
      keys.push(path)
    }
  }
  return keys
}

// ─── tests ───

describe('i18n messages 结构', () => {
  it('默认导出形如 { zh: {...}, en: {...} }', () => {
    expect(messages).toBeTypeOf('object')
    expect(Object.keys(messages).sort()).toEqual(['en', 'zh'])
  })

  it('zh 与 en 顶层命名空间完全一致', () => {
    const zhNs = Object.keys(messages.zh).sort()
    const enNs = Object.keys(messages.en).sort()
    expect(enNs).toEqual(zhNs)
    // 不能只有一个空白命名空间占位（防止把整个域塞到同一个 key 里）
    expect(zhNs.length).toBeGreaterThan(1)
  })
})

describe('i18n key 集合对齐（zh ↔ en）', () => {
  // 列举所有命名空间，逐个对比 zh/en 的 leaf key 集合
  const namespaces = Object.keys(messages.zh)

  for (const ns of namespaces) {
    it(`namespace "${ns}"：zh 与 en key 集合完全一致`, () => {
      const zhKeys = collectLeafKeys(messages.zh[ns]).sort()
      const enKeys = collectLeafKeys(messages.en[ns]).sort()
      expect(enKeys, `en 缺少 key: ${zhKeys.filter(k => !enKeys.includes(k)).join(', ')}`)
        .toEqual(zhKeys)
    })

    it(`namespace "${ns}"：zh 翻译值均为非空字符串`, () => {
      const keys = collectLeafKeys(messages.zh[ns])
      for (const key of keys) {
        const val = resolve(messages.zh[ns], key)
        expect(typeof val, `${ns}.${key} 应为字符串`).toBe('string')
        expect((val as string).length, `${ns}.${key} 不应为空字符串`).toBeGreaterThan(0)
      }
    })
  }
})

describe('i18n 关键 sample key 解析正确', () => {
  // 这些是项目里实际用到的 key —— 防止再出现"嵌套双层 chat.chat"这种 bug
  const cases: Array<[string, string]> = [
    ['chat.title', 'chat 域顶级 title'],
    ['chat.AI', 'AI 角色占位（拼接用）'],
    ['admin.title', 'admin 域顶级 title'],
    ['admin.modelManagement', 'admin 模型管理'],
    ['login.title', 'login 域 title'],
    ['login.submitButton', 'login 提交按钮'],
    ['validation.passwordMinLength', 'validation 密码长度提示'],
  ]

  for (const [key, desc] of cases) {
    it(`${key}（${desc}）：zh 与 en 均能解析`, () => {
      const zh = resolve(messages.zh, key)
      const en = resolve(messages.en, key)
      expect(zh, `${key} (zh)`).toBeTypeOf('string')
      expect((zh as string).length, `${key} (zh) 非空`).toBeGreaterThan(0)
      expect(en, `${key} (en)`).toBeTypeOf('string')
      expect((en as string).length, `${key} (en) 非空`).toBeGreaterThan(0)
    })
  }

  // 反向断言：嵌套错误的 key 必须返回 undefined，避免再次出现"chat.chat.title" 这种 bug
  it('嵌套错误的 key（如 chat.chat.title）必须返回 undefined', () => {
    expect(resolve(messages.zh, 'chat.chat.title')).toBeUndefined()
    expect(resolve(messages.en, 'chat.chat.title')).toBeUndefined()
    expect(resolve(messages.zh, 'admin.admin.title')).toBeUndefined()
    expect(resolve(messages.zh, 'login.login.submitButton')).toBeUndefined()
  })
})

describe('i18n 数值占位（边界）', () => {
  it('zh 与 en 中任何 leaf key 都不应是 undefined 或 null', () => {
    for (const lang of ['zh', 'en'] as const) {
      const allKeys = collectLeafKeys(messages[lang])
      for (const key of allKeys) {
        const val = resolve(messages[lang], key)
        expect(val, `${lang}.${key} 不应为 null/undefined`).toBeDefined()
        expect(val, `${lang}.${key} 不应为 null`).not.toBeNull()
      }
    }
  })
})
