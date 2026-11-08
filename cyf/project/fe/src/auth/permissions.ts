/**
 * 共享角色类型与规范化工具。
 *
 * 与后端 `service/permission_service.py` 保持一致：
 * - `chat` / `quant` / `sound` 为业务角色，可自由组合；
 * - `admin` 为管理员，权限覆盖全部业务模块；
 * - 业务角色不能推导出管理员身份。
 */
export type BusinessRole = 'chat' | 'quant' | 'sound'
export type AppRole = BusinessRole | 'admin'

/** 普通账号角色的固定排序 */
export const BUSINESS_ROLE_ORDER: BusinessRole[] = ['chat', 'quant', 'sound']
/** 全部合法角色 */
export const ALL_ROLES: AppRole[] = ['chat', 'quant', 'sound', 'admin']

const ROLE_SET = new Set<string>(ALL_ROLES)

export const isBusinessRole = (role: string): role is BusinessRole =>
  BUSINESS_ROLE_ORDER.includes(role as BusinessRole)

export const isAppRole = (role: string): role is AppRole => ROLE_SET.has(role)

/** 把任意输入规范化为角色列表；未知值直接丢弃。 */
export const normalizeRoles = (raw: unknown): AppRole[] => {
  if (!Array.isArray(raw)) return []
  const collected: AppRole[] = []
  for (const item of raw) {
    if (typeof item !== 'string') continue
    const role = item.trim()
    if (!ROLE_SET.has(role) || collected.includes(role as AppRole)) continue
    collected.push(role as AppRole)
  }
  if (collected.includes('admin')) return ['admin']
  return BUSINESS_ROLE_ORDER.filter((role) => collected.includes(role))
}

/** 管理员判定 */
export const isAdminRoles = (roles: AppRole[]): boolean => roles.includes('admin')

/**
 * 角色是否具备某能力。
 * 管理员天然具备全部业务模块；业务角色不能推导出管理员。
 */
export const hasRole = (roles: AppRole[], role: AppRole): boolean => {
  if (!role) return false
  if (isAdminRoles(roles)) return true
  return roles.includes(role)
}

/** 兼容字段：把角色集合投影为旧单值 role */
export const toCompatRole = (roles: AppRole[]): string => (isAdminRoles(roles) ? 'admin' : 'user')

/** 账号快照（login / refresh / auth/me 共用） */
export type AccountSnapshot = {
  userId: number | null
  username: string
  roles: AppRole[]
  compatRole: string
}
