/**
 * 登录目的地解析。
 *
 * 规则（对齐开发任务书 §3.4）：
 * 1. 深链使用 `/login?redirect=<站内路由>`，功能选择使用 `app=chat|quant|sound|admin`；
 * 2. 显式功能选择会更新并取代先前深链目的地；
 * 3. 未显式选择时，优先恢复合法深链，其次使用该账号上次仍有权访问的功能，
 *    均不存在时按聊天、量化、声音、管理的顺序选首个可用入口；
 * 4. 拒绝外部 URL、协议相对地址、编码后的外部跳转及未知路径；
 * 5. 账号切换时清理上一账号的目的地偏好，退出登录清理全部状态。
 */
import { APP_META, APP_ORDER, isAppKey, type AppKey } from './apps'
import { hasRole, type AppRole } from './permissions'

/** 已知站内路径；由路由表在创建后登记。 */
const knownPaths = new Map<string, AppRole | undefined>()

export const registerKnownPaths = (paths: (string | { path: string; requiredRole?: AppRole })[]) => {
  paths.forEach((entry) => {
    const path = typeof entry === 'string' ? entry : entry.path
    if (path !== '/' && path !== '/login') knownPaths.set(path, typeof entry === 'string' ? undefined : entry.requiredRole)
  })
}

export const clearKnownPaths = () => {
  knownPaths.clear()
}

/** 归一化路径：去掉查询串与末尾斜杠。 */
const normalizePath = (path: string): string => {
  const withoutQuery = path.split('?')[0].split('#')[0]
  if (withoutQuery.length > 1 && withoutQuery.endsWith('/')) {
    return withoutQuery.slice(0, -1)
  }
  return withoutQuery
}

/**
 * 校验是否为可解析的站内路径。
 * 外部 URL、协议相对地址、编码后的外部跳转、未知路径一律拒绝。
 */
export const resolveInternalPath = (rawPath: string | null | undefined): string | null => {
  if (!rawPath || typeof rawPath !== 'string') return null
  const trimmed = rawPath.trim()
  if (!trimmed.startsWith('/')) return null
  if (trimmed.startsWith('//')) return null
  if (trimmed.includes('\\')) return null
  // 拒绝含 `..` 段的路径，避免绕过已知路径前缀匹配
  if (trimmed.split('/').some((segment) => segment === '..')) return null

  let decoded = trimmed
  try {
    decoded = decodeURIComponent(trimmed)
  } catch {
    return null
  }
  if (!decoded.startsWith('/') || decoded.startsWith('//') || decoded.includes('\\')) return null
  // 编码后再解出协议头的情况（%2F%2Fevil.com）已被上面的 startsWith('//') 拦掉
  if (/^\/[a-zA-Z][a-zA-Z0-9+.-]*:/.test(decoded)) return null

  const normalized = normalizePath(decoded)
  if (normalized.split('/').some((segment) => segment === '..' || segment === '.')) return null
  if (!knownPaths.has(normalized)) return null
  // 路径匹配使用解码值，查询参数和 hash 保持原样。
  return normalized + trimmed.slice(trimmed.search(/[?#]/) < 0 ? trimmed.length : trimmed.search(/[?#]/))

}

export type DestinationInput = {
  /** URL 上的 redirect 参数 */
  redirect?: string | null
  /** URL 上的 app 参数 */
  app?: string | null
}

export type ResolvedDestination = {
  /** 最终目标路由 */
  route: string
  /** 目标对应的功能入口 */
  app: AppKey
  /** 是否来自合法的深链 */
  fromDeepLink: boolean
  /** 目标入口所需角色 */
  requiredRole: AppRole
}

/**
 * 解析目的地。
 *
 * @param input URL 参数
 * @param roles 当前账号角色
 * @param lastApp 该账号上次使用的入口（同一账号内持久化）
 */
export const resolveDestination = (
  input: DestinationInput,
  roles: AppRole[],
  lastApp?: AppKey | null
): ResolvedDestination => {
  const roleOf = (app: AppKey): AppRole => (app === 'admin' ? 'admin' : (app as AppRole))

  // 1) 显式功能选择优先，并覆盖此前的深链目的地
  if (isAppKey(input.app)) {
    const app = input.app
    return {
      route: defaultRouteFor(app),
      app,
      fromDeepLink: false,
      requiredRole: roleOf(app)
    }
  }

  // 2) 合法深链
  const deepLink = resolveInternalPath(input.redirect)
  if (deepLink) {
    const app = appForPath(deepLink)
    return {
      route: deepLink,
      app,
      fromDeepLink: true,
      requiredRole: knownPaths.get(normalizePath(deepLink)) ?? roleOf(app)
    }
  }

  // 3) 该账号上次仍有权访问的功能
  if (lastApp && hasRole(roles, roleOf(lastApp))) {
    return {
      route: defaultRouteFor(lastApp),
      app: lastApp,
      fromDeepLink: false,
      requiredRole: roleOf(lastApp)
    }
  }

  // 4) 首个可用入口
  const fallback = APP_ORDER.find((app) => hasRole(roles, roleOf(app))) ?? 'chat'
  return {
    route: defaultRouteFor(fallback),
    app: fallback,
    fromDeepLink: false,
    requiredRole: roleOf(fallback)
  }
}

/** 按路径推断所属功能入口。 */
export const appForPath = (path: string): AppKey => {
  const normalized = normalizePath(path)
  if (normalized.startsWith('/quant')) return 'quant'
  if (normalized.startsWith('/studio')) return 'sound'
  if (normalized.startsWith('/admin')) return 'admin'
  return 'chat'
}

/** 入口的默认路由。 */
export const defaultRouteFor = (app: AppKey): string => APP_META[app].route
