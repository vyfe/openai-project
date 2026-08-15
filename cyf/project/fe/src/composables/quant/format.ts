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
 * 根据 scheduleForm.taskType 构造对应的 payload。
 * 注意：依赖 scheduleForm 的 reactive 字段；调用方需传入。
 */
export const buildSchedulePayload = (scheduleForm: any): any => {
  if (scheduleForm.taskType === 'data_sync') {
    return {
      symbols: scheduleForm.dataSymbols,
      provider: scheduleForm.dataProvider,
      adjust_flag: scheduleForm.dataAdjustFlag,
      lookback_trade_days: scheduleForm.dataLookbackTradeDays,
      lease_seconds: scheduleForm.dataLeaseSeconds,
      note: scheduleForm.dataNote
    }
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
