/**
 * 量化工作台纯函数（无副作用，可独立测试）。
 */

/** 把小数（0.1234）格式化为百分比字符串 "12.34%"。null/NaN/空 返回 "--"。 */
export function formatRate(value: any): string {
  if (value === null || value === undefined || value === '') return '--'
  const num = Number(value)
  if (!Number.isFinite(num)) return '--'
  return `${(num * 100).toFixed(2)}%`
}

/** 把数字格式化为指定小数位字符串。null/NaN 返回 "--"。 */
export function formatNumber(value: any, digits = 2): string {
  if (value === null || value === undefined || value === '') return '--'
  const num = Number(value)
  if (!Number.isFinite(num)) return '--'
  return num.toFixed(digits)
}

/** 策略状态映射到 Element Plus tag type。 */
export const strategyStatusTag = (status: string): 'success' | 'info' =>
  status === 'active' ? 'success' : 'info'

/**
 * 把 symbol 选项（{symbol, name, ...}）渲染成"展示名称，但传代码参数"的下拉 label。
 * - 优先用中文/英文 name
 * - 没有 name 时回退到 symbol（保证下拉永远可读）
 * - name 与 symbol 重复时去重（例如 name="002837 英维克" 不会变成 "英维克 · 002837 英维克"）
 */
export const symbolLabel = (item: { symbol?: string; code?: string; name?: string } | null | undefined): string => {
  if (!item) return ''
  const code = String(item.symbol || item.code || '').trim()
  const name = String(item.name || '').trim()
  if (!name) return code
  if (name === code) return code
  if (name.includes(code)) return name
  return `${name}（${code}）`
}

/**
 * 给定一个 symbol 字符串 + name 查表函数，返回"名称（代码）"展示串。
 * 适用于后端 API 只返回 symbol 但前端 symbolOptions 缓存里有 name 的场景
 * （如 signals/operations/position/memory/backtest trades 等只携带 code 的列表）。
 * 没有 name 时回退到 symbol 本身（保证表格列永远可读，不会空白）。
 */
export const displaySymbolWithName = (
  symbol: string,
  nameLookup: (symbol: string) => string | undefined,
): string => {
  const code = String(symbol || '').trim()
  if (!code) return ''
  const name = String(nameLookup(code) || '').trim()
  if (!name) return code
  if (name === code) return code
  if (name.includes(code)) return name
  return `${name}（${code}）`
}

/**
 * 根据 scheduleForm.taskType 构造对应的 payload。
 * 注意：依赖 scheduleForm 的 reactive 字段；调用方需传入。
 */
export const buildSchedulePayload = (scheduleForm: any): any => {
  if (scheduleForm.taskType === 'data_sync') {
    const frequencies: string[] = Array.isArray(scheduleForm.dataFrequencies) && scheduleForm.dataFrequencies.length > 0
      ? scheduleForm.dataFrequencies
      : ['1d']
    const payload: Record<string, unknown> = {
      symbols: scheduleForm.dataSymbols,
      provider: scheduleForm.dataProvider,
      adjust_flag: scheduleForm.dataAdjustFlag,
      frequencies,
      lookback_trade_days: scheduleForm.dataLookbackTradeDays,
      lease_seconds: scheduleForm.dataLeaseSeconds,
      note: scheduleForm.dataNote
    }
    // 仅在勾选 5m 时下发分时回溯分钟数；后端 schedule_execution_service._resolve_minute_lookback_minutes
    // 会以 minute_lookback_minutes 优先，旧别名 lookback_minutes 兼容。
    if (frequencies.includes('5m') && scheduleForm.dataMinuteLookbackMinutes) {
      payload.minute_lookback_minutes = scheduleForm.dataMinuteLookbackMinutes
    }
    return payload
  }
  if (scheduleForm.taskType === 'memory_digest') {
    return {
      symbols: scheduleForm.memorySymbols,
      lookback_days: scheduleForm.memoryLookbackDays,
      limit: scheduleForm.memoryLimit
    }
  }
  if (scheduleForm.taskType === 'industry_collect') {
    return {
      board_ids: scheduleForm.industryBoardIds,
      targets: scheduleForm.industryTargets
    }
  }
  if (scheduleForm.taskType === 'industry_report') {
    return {
      board_ids: scheduleForm.industryBoardIds,
      channel_ids: scheduleForm.industryChannelIds
    }
  }
  return {
    strategy_ids: scheduleForm.analysisStrategyIds,
    channel_ids: scheduleForm.analysisChannelIds,
    save_all_signals: scheduleForm.analysisSaveAllSignals
  }
}
