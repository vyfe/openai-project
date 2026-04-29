export const normalizeModelList = (input: unknown): string[] => {
  const normalizeArray = (arr: unknown[]): string[] => {
    const cleaned = arr
      .map((item) => (typeof item === 'string' ? item.trim() : String(item || '').trim()))
      .filter((item) => !!item)
    return Array.from(new Set(cleaned))
  }

  if (Array.isArray(input)) {
    return normalizeArray(input)
  }

  if (typeof input === 'string') {
    const raw = input.trim()
    if (!raw) return []

    // 优先按 JSON 数组解析；解析失败则按单一模型字符串处理，不做逗号 split
    try {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) {
        return normalizeArray(parsed)
      }
      if (typeof parsed === 'string' && parsed.trim()) {
        return [parsed.trim()]
      }
    } catch {
      // 兼容历史“单字符串模型”场景
      return [raw]
    }
  }

  return []
}
