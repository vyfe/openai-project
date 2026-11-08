import { describe, expect, it } from 'vitest'
import {
  BUSINESS_ROLE_ORDER,
  hasRole,
  isAdminRoles,
  normalizeRoles,
  toCompatRole,
  type AppRole
} from '@/auth/permissions'

describe('角色规范化', () => {
  it('按 chat / quant / sound 固定顺序返回', () => {
    expect(normalizeRoles(['sound', 'quant', 'chat'])).toEqual(['chat', 'quant', 'sound'])
  })

  it('含 admin 时归一为 ["admin"]', () => {
    expect(normalizeRoles(['admin', 'chat'])).toEqual(['admin'])
  })

  it('去重', () => {
    expect(normalizeRoles(['chat', 'chat', 'quant'])).toEqual(['chat', 'quant'])
  })

  it('丢弃未知角色', () => {
    expect(normalizeRoles(['chat', 'wizard'])).toEqual(['chat'])
  })

  it('非数组输入返回空数组', () => {
    expect(normalizeRoles('chat')).toEqual([])
    expect(normalizeRoles(null)).toEqual([])
  })

  it('空数组返回空数组', () => {
    expect(normalizeRoles([])).toEqual([])
  })

  it('业务角色顺序常量与后端一致', () => {
    expect(BUSINESS_ROLE_ORDER).toEqual(['chat', 'quant', 'sound'])
  })
})

describe('有效权限判定', () => {
  it('普通账号只具备自己的角色', () => {
    expect(hasRole(['chat'], 'chat')).toBe(true)
    expect(hasRole(['chat'], 'quant')).toBe(false)
  })

  it('管理员具备全部业务模块', () => {
    const admin: AppRole[] = ['admin']
    expect(hasRole(admin, 'chat')).toBe(true)
    expect(hasRole(admin, 'quant')).toBe(true)
    expect(hasRole(admin, 'sound')).toBe(true)
  })

  it('业务角色不能推导出管理员', () => {
    expect(hasRole(['chat', 'quant', 'sound'], 'admin')).toBe(false)
    expect(isAdminRoles(['chat', 'quant', 'sound'])).toBe(false)
  })

  it('兼容 role 投影', () => {
    expect(toCompatRole(['chat', 'quant'])).toBe('user')
    expect(toCompatRole(['admin'])).toBe('admin')
    expect(toCompatRole([])).toBe('user')
  })
})
