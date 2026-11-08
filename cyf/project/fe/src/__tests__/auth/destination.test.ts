import { beforeEach, describe, expect, it } from 'vitest'
import {
  appForPath,
  defaultRouteFor,
  registerKnownPaths,
  resolveDestination,
  resolveInternalPath
} from '@/auth/destination'

beforeEach(() => {
  registerKnownPaths([
    '/login',
    '/chat',
    '/admin',
    '/studio',
    '/studio/voice',
    '/studio/music',
    '/quant',
    '/quant/overview',
    '/quant/data',
    '/quant/industry',
    '/quant/strategy',
    '/quant/runs',
    '/quant/operations',
    '/quant/backtest',
    '/quant/scheduler',
    '/quant/ai-memory',
    '/quant/im-positions'
  ])
})

describe('站内路径校验', () => {
  it('接受已知路径', () => {
    expect(resolveInternalPath('/quant/overview')).toBe('/quant/overview')
  })

  it('接受已知路径的子路径', () => {
    expect(resolveInternalPath('/quant/strategy')).toBe('/quant/strategy')
  })

  it('拒绝外部 URL', () => {
    expect(resolveInternalPath('https://evil.com/quant')).toBeNull()
    expect(resolveInternalPath('//evil.com/quant')).toBeNull()
  })

  it('拒绝编码后的外部跳转', () => {
    expect(resolveInternalPath('%2F%2Fevil.com/quant')).toBeNull()
    expect(resolveInternalPath('/%2F%2Fevil.com')).toBeNull()
  })

  it('拒绝未知路径', () => {
    expect(resolveInternalPath('/unknown/page')).toBeNull()
    expect(resolveInternalPath('/admin/../etc/passwd')).toBeNull()
  })

  it('拒绝空值', () => {
    expect(resolveInternalPath('')).toBeNull()
    expect(resolveInternalPath(null)).toBeNull()
  })
})

describe('目的地解析', () => {
  it('显式 app 优先于深链', () => {
    const resolved = resolveDestination({ app: 'quant', redirect: '/chat' }, ['chat', 'quant'])
    expect(resolved.app).toBe('quant')
    expect(resolved.route).toBe('/quant/overview')
    expect(resolved.fromDeepLink).toBe(false)
  })

  it('合法深链被保留', () => {
    const resolved = resolveDestination({ redirect: '/quant/strategy' }, ['chat', 'quant'])
    expect(resolved.app).toBe('quant')
    expect(resolved.route).toBe('/quant/strategy')
    expect(resolved.fromDeepLink).toBe(true)
  })

  it('非法深链退回默认选择', () => {
    const resolved = resolveDestination({ redirect: 'https://evil.com' }, ['chat'])
    expect(resolved.route).toBe('/chat')
    expect(resolved.fromDeepLink).toBe(false)
  })

  it('优先使用该账号上次仍有权访问的功能', () => {
    const resolved = resolveDestination({}, ['chat', 'quant'], 'quant')
    expect(resolved.app).toBe('quant')
    expect(resolved.route).toBe('/quant/overview')
  })

  it('上次功能已失权时按顺序选首个可用入口', () => {
    const resolved = resolveDestination({}, ['chat'], 'quant')
    expect(resolved.app).toBe('chat')
  })

  it('没有任何权限时兜底到聊天入口', () => {
    const resolved = resolveDestination({}, [], 'quant')
    expect(resolved.app).toBe('chat')
  })

  it('按聊天、量化、声音、管理的顺序选首个可用入口', () => {
    // 管理员具备全部业务模块，按固定顺序仍落在聊天入口。
    const resolved = resolveDestination({}, ['admin'])
    expect(resolved.app).toBe('chat')
    expect(resolved.route).toBe('/chat')
  })
})

describe('路径与入口映射', () => {
  it('按前缀推断入口', () => {
    expect(appForPath('/quant/overview')).toBe('quant')
    expect(appForPath('/studio/music')).toBe('sound')
    expect(appForPath('/admin')).toBe('admin')
    expect(appForPath('/chat')).toBe('chat')
  })

  it('入口默认路由', () => {
    expect(defaultRouteFor('chat')).toBe('/chat')
    expect(defaultRouteFor('quant')).toBe('/quant/overview')
    expect(defaultRouteFor('sound')).toBe('/studio/voice')
    expect(defaultRouteFor('admin')).toBe('/admin')
  })
})
