"""量化子系统 ORM 实体（按业务域拆分）。

- :mod:`quant.quant_entities_market` —— 行情/市场数据（symbol、KLine、行业板块、新闻等）
- :mod:`quant.quant_entities_strategy` —— 策略/回测/运营记录
- :mod:`quant.quant_entities_ops` —— 调度/报告/IM/记忆

本文件仅做 re-export，保留旧导入路径 `from quant.entities import ...`。
"""

from quant.quant_entities_market import (
    QuantBaseModel,
    QuantInstrument,
    QuantDailyBar,
    QuantMinuteBar,
    QuantImportBatch,
    QuantMarketSnapshot,
    QuantIndustryBoard,
    QuantIndustryWatchSymbol,
    QuantIndustryNewsItem,
    QuantResearchReportItem,
    QuantIndustryIndicatorSnapshot,
    QuantDailyIndicator,
)

from quant.quant_entities_strategy import (
    QuantStrategy,
    QuantStrategyRun,
    QuantStrategySignal,
    QuantOperationRecord,
    QuantBacktestRun,
)

from quant.quant_entities_ops import (
    QuantScheduleConfig,
    QuantScheduleRun,
    QuantPromptTemplate,
    QuantReportRecord,
    QuantImChannel,
    QuantReportDelivery,
    QuantImInboundEvent,
    QuantPositionJournal,
    QuantFeishuUserBinding,
    QuantClientTask,
)

QUANT_MODELS = [
    QuantBaseModel,
    QuantInstrument,
    QuantDailyBar,
    QuantMinuteBar,
    QuantImportBatch,
    QuantStrategy,
    QuantStrategyRun,
    QuantStrategySignal,
    QuantOperationRecord,
    QuantBacktestRun,
    QuantScheduleConfig,
    QuantScheduleRun,
    QuantPromptTemplate,
    QuantReportRecord,
    QuantDailyIndicator,
    QuantIndustryBoard,
    QuantIndustryWatchSymbol,
    QuantMarketSnapshot,
    QuantIndustryNewsItem,
    QuantResearchReportItem,
    QuantIndustryIndicatorSnapshot,
    QuantImChannel,
    QuantReportDelivery,
    QuantImInboundEvent,
    QuantPositionJournal,
    QuantFeishuUserBinding,
    QuantClientTask,
]
