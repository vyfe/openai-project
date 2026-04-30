# 轻量级 AI 量化能力设计与开发评估

## 1. 背景与目标

当前项目的前后端重构已经基本完成，整体架构以 Flask 后端和 Vue 3 前端为主，已具备：

- 用户鉴权
- 模型管理
- 系统提示词管理
- 通知公告
- 对话能力
- 后台管理页

在此基础上，计划新增一个“轻量级 AI 量化”能力，核心诉求包括：

- 定时获取市场数据
- 自学习能力
- 记忆能力
- 交易日每日 2~3 次报告发送到指定 IM
- 实际操作登记
- 评估与回测

本文目标不是给出泛泛的功能清单，而是基于现有代码架构，输出一版可落地的工程评估，明确：

- 这个能力应该如何嵌入现有项目
- MVP 必须接受哪些工程约束
- AI 在其中扮演什么角色，边界在哪里
- 自学习和回测如何避免自我污染
- 哪些设计适合现在做，哪些应明确后置

## 2. 结论摘要

这个能力适合做成一个挂载在现有项目中的独立子系统，而不是另起一个完全分离的新平台。

推荐形态：

- 现有 Flask 服务继续承担配置管理、查询接口、人工触发和管理台能力
- 新增量化模块，负责数据采集、策略执行、报告生成、回测评估
- 新增独立 worker 进程，负责定时任务、抓数、跑策略、发报告
- 前端新增独立量化工作台页面，不建议把量化能力塞进聊天页面

简化后的职责边界：

- Web 服务负责“看”和“配”
- Worker 负责“跑”和“发”
- 规则策略负责“真实信号”
- LLM 负责“解释、总结、复盘、经验归纳”

但以上结论只有在以下 MVP 约束成立时才可行：

- 只允许单个量化 worker 实例运行
- 调度器不做多副本高可用
- 数据频率以日频和低频盘中任务为主
- 自动下单不进入 MVP
- AI 不直接生成数值信号和交易指令

## 3. 现有架构适配性评估

结合当前仓库结构，现有系统具备较好的承载基础，但需要增加明确的运行时边界。

### 3.1 后端适配性

当前后端已经具备：

- `routes + service + repository + model` 的模块化结构
- 基于 Peewee 的本地数据库持久化
- 基于 `bootstrap_service` 的启动初始化逻辑
- 现有定时任务雏形
- 现有通知管理与后台管理能力

这意味着量化能力可以沿用现有分层继续扩展：

- 新增路由：量化配置、执行记录、回测结果、人工操作登记
- 新增 service：数据采集、策略分析、报告推送、记忆与学习
- 新增 repository/model：策略、运行记录、报告、持仓与回测相关表

### 3.2 前端适配性

当前前端已具备：

- 独立路由和登录鉴权
- 聊天页与管理页的页面结构
- 管理台组件化模式
- 统一 API service 封装方式

因此量化能力适合新增一个 `/quant` 页面作为独立工作台，承载：

- 仪表盘
- 策略管理
- 报告历史
- 操作登记
- 回测评估

### 3.3 当前架构的不足

以下能力在现状中并不存在，需要在设计阶段先补约束，再谈功能：

- 独立 worker 的运行拓扑
- Web 与 Worker 的代码复用边界
- 多进程写入下的数据一致性约束
- 调度持久化与幂等处理
- AI 结构化输入与输出协议
- 自学习样本生成和隔离机制

### 3.4 不建议直接复用的部分

以下做法不建议：

- 不建议把量化能力直接塞进 `chat` 页面
- 不建议继续只用 `threading.Timer` 承担越来越多的定时任务
- 不建议将报告文本直接等同于“可执行交易决策”
- 不建议一开始就做自动交易
- 不建议一开始就上重量级研究平台

## 4. 推荐总体架构

建议将量化能力拆为 6 个核心层次，而不是简单理解为“加几个接口”。

### 4.1 数据采集层

负责定时获取：

- 行情数据
- 指数数据
- ETF 数据
- 资金面数据
- 行业板块数据
- 新闻、公告、情绪类补充数据

推荐策略：

- 第一阶段优先日频或低频数据，不要一开始做高频
- 第一阶段优先 A 股、ETF、指数等较聚焦的标的范围

推荐数据源：

- `AkShare`：接入门槛低，适合轻量原型
- `Tushare Pro`：更标准，但存在积分和额度约束

交易日识别可用：

- `pandas_market_calendars`
- `exchange_calendars`

### 4.2 策略与分析层

这一层不要完全依赖 LLM 直接生成交易信号，而应采用“规则策略主导、AI 辅助解释”的思路。

职责划分建议：

- 规则模块负责真实可验证的选股、打分、择时、风控逻辑
- LLM 负责对规则输出进行自然语言解释、报告总结、风险提示、盘中盘后复盘

初期可支持的策略类型：

- 趋势跟随
- 均线/突破类
- 波动率过滤
- 成交量异动
- 板块轮动打分
- 简单多因子打分

### 4.3 AI 上下文与产物契约层

这是本方案的关键工程层，不能只写“调用 LLM 生成报告”。

必须定义两个结构化对象：

- `AnalysisBundle`：传给 LLM 的结构化输入
- `ReportDraft`：LLM 返回的受约束输出

其中：

- 数值信号、价格、涨跌幅、仓位、排名等字段必须在 `AnalysisBundle` 中由程序计算完成
- LLM 只允许对这些字段进行解释、排序说明、风险描述、归纳总结
- 报告中的数值字段禁止由 LLM 自由生成，必须通过模板插值或结构化字段回填

### 4.4 记忆与自学习层

“自学习”不应理解为在线训练模型，而应理解为：

- 保存每次信号及其后续表现
- 记录人工是否采纳建议
- 汇总策略失效场景
- 周期性生成参数建议与复盘摘要

“记忆”应拆成两类：

- 结构化记忆：策略配置、信号记录、人工操作、发送记录、回测结果
- 非结构化记忆：复盘结论、失败原因、人工备注、异常事件描述

### 4.5 调度执行层

量化场景下调度是基础能力，建议从当前简单定时器升级。

推荐方案：

- 开发阶段或轻量部署：`APScheduler`
- 正式运行：独立 `quant_worker.py` 进程运行 scheduler

调度层应支持：

- 按交易日执行
- 每日固定多个时间点执行
- 补偿执行
- 失败重试
- 任务状态记录
- 手工重跑
- 任务幂等校验

### 4.6 展示与管理层

建议新增量化工作台，不依附聊天页。

推荐页面结构：

- 仪表盘：今日任务、最新信号、最近报告、风险提示
- 策略中心：策略配置、标的池、启停状态、调度时间
- 操作登记：人工买卖记录、执行理由、执行后结果
- 回测评估：收益、回撤、胜率、夏普、净值曲线、版本对比

## 5. 进程拓扑与一致性约束

这一节是 MVP 是否可落地的关键。

### 5.1 MVP 运行拓扑

MVP 明确采用双进程拓扑：

- `web`：现有 Flask 服务，只提供 API 和前端访问
- `worker`：单独的量化 worker，只负责定时调度和任务执行

MVP 明确约束：

- 只允许一个 worker 实例运行
- Web 不参与任何定时量化任务执行
- 所有定时任务只从 worker 触发

这是为了避免：

- 多实例重复执行
- 多进程调度冲突
- Flask 多 worker 下任务误触发

### 5.2 Web 与 Worker 的代码共享方式

MVP 阶段不建议过早拆包成独立 `quant_core` 仓库或发布包。

建议做法：

- 继续单仓
- `worker` 直接导入现有 `service / repository / model / conf`
- 量化逻辑集中在 `service/quant/` 和 `model/repositories/quant_repository.py`

这样可以降低前期搬迁成本。

但需要额外约束：

- 量化模块不能反向依赖 Flask request context
- 量化 service 应只依赖配置、数据库和通用工具，不依赖路由层
- 需要预留未来抽成 `quant_core` 的边界

建议未来满足以下条件时再拆包：

- worker 和 web 生命周期明显分离
- 回测或研究逻辑体量显著增加
- 需要独立测试、单独部署或外部复用

### 5.3 SQLite 的可行性边界

MVP 使用 SQLite 不是因为它理想，而是因为它能在有限复杂度下快速起步。

但必须写清楚它的边界：

- 允许 Web 和 Worker 双进程并存
- 不允许高频多线程并发写
- 不适合作为分钟级高频行情主存储
- 不适合多个 worker 并发回测写入

最现实的问题不是数据量上限，而是双进程写入锁竞争：

- 行情快照写入
- `strategy_run` 写入
- 报告发送记录写入
- 操作登记补录

因此 MVP 使用 SQLite 的前提是：

- 低频任务
- 单 worker
- 批量写入控制
- 必要时以文件缓存减少数据库写压

一旦出现以下任一情况，应迁移到 PostgreSQL：

- 报告任务和抓数任务并行度明显上升
- 分钟级快照持续入库
- 回测任务需要并发执行
- 出现频繁 `database is locked`

### 5.4 APScheduler 的使用边界

`APScheduler` 可以用于 MVP，但不能假设它天然解决一致性问题。

需要明确：

- `MemoryJobStore` 重启后任务定义丢失
- `SQLAlchemyJobStore` 会引入第二套 ORM 生态，不建议在 MVP 为它专门铺设
- 多实例部署时 APScheduler 不具备天然分布式抢锁能力

因此 MVP 建议：

- 调度配置以业务表为准，而不是完全依赖 APScheduler 持久化
- worker 启动时从业务表重建 job
- job 执行前做一次数据库层幂等检查

后续如果进入多实例阶段，迁移路径建议为：

- PostgreSQL
- 基于数据库锁或 Redis 锁的任务抢占
- 将调度从单机 APScheduler 演进为可协调执行模型

## 6. 推荐模块拆分

### 6.1 后端目录建议

建议在现有 `cyf/project/server` 下新增：

```text
routes/quant_routes.py
service/quant/
service/quant/data_service.py
service/quant/strategy_service.py
service/quant/report_service.py
service/quant/backtest_service.py
service/quant/memory_service.py
service/quant/scheduler_service.py
service/quant/contract_service.py
model/repositories/quant_repository.py
worker/quant_worker.py
```

职责建议：

- `quant_routes.py`：对外提供量化相关接口
- `data_service.py`：统一封装数据抓取与缓存
- `strategy_service.py`：规则打分、信号生成、风控检查
- `report_service.py`：报告组装与 IM 推送
- `backtest_service.py`：简化回测、指标统计
- `memory_service.py`：经验记录、案例检索、学习建议
- `scheduler_service.py`：调度注册与执行编排
- `contract_service.py`：结构化输入输出协议校验、prompt 版本解析
- `quant_worker.py`：独立运行的任务入口

### 6.2 前端目录建议

建议在现有 `cyf/project/fe/src` 下新增：

```text
views/Quant.vue
components/quant/QuantDashboard.vue
components/quant/StrategyTable.vue
components/quant/RunHistoryTable.vue
components/quant/PositionJournalTable.vue
components/quant/BacktestPanel.vue
services/quantApi.ts
```

## 7. AI 上下文与产物契约

这一节用于解决“AI 报告如何可复现、可约束、可回放”的问题。

### 7.1 `AnalysisBundle` 输入契约

建议定义统一结构化输入对象 `AnalysisBundle`，作为策略引擎到 LLM 的唯一中间层。

字段建议：

- `bundle_version`
- `strategy_id`
- `strategy_version`
- `prompt_version`
- `run_id`
- `run_type`
- `market`
- `timezone`
- `as_of`
- `benchmark`
- `symbols`
- `top_signals`
- `risk_flags`
- `portfolio_snapshot`
- `market_summary`
- `memory_snippets`
- `operator_notes`

必须额外规定：

- 所有时间字段使用统一时区和 ISO 8601 格式
- 所有价格、涨跌幅、换手率、收益率字段单位固定
- 百分比字段明确是 `0.1234` 还是 `12.34%`
- 缺失值必须统一约定为 `null`，不能混用空字符串和 `0`

### 7.2 `ReportDraft` 输出契约

LLM 返回的对象不应是任意 Markdown，而应是受限结构。

建议字段：

- `title`
- `summary`
- `market_view`
- `signal_highlights`
- `risk_warnings`
- `action_watchlist`
- `memory_references`
- `footer_notes`

最终发送给 IM 的 Markdown 由程序负责模板化拼装。

原则：

- LLM 负责写“解释文本”
- 程序负责插入“结构化数值”

### 7.3 Prompt 版本管理

`quant_strategy.llm_prompt` 直接存裸字符串不够。

建议引入：

- `prompt_template`
- `prompt_version`
- `prompt_change_note`
- `enabled`

并在 `strategy_run` 或关联表中记录本次运行实际使用的：

- `prompt_version`
- `bundle_version`
- `model_name`
- `model_params`

否则会出现：

- 同一策略前后报告口径不一致
- 复盘时无法知道报告基于哪版 prompt 生成
- 记忆与自学习缺少稳定基准

### 7.4 Token 预算与裁剪策略

当后续接入历史案例召回和人工备注时，context 很容易失控。

因此需要先定义裁剪顺序，而不是等超限再补。

建议优先级：

1. 当前市场摘要和核心信号
2. 风险标记
3. 最近一次人工备注
4. 最多 K 条历史案例
5. 非关键附加说明

建议对不同上下文来源设置单独预算：

- `market_summary_budget`
- `memory_budget`
- `operator_note_budget`

并将裁剪结果落入运行记录，保证可解释。

### 7.5 幻觉防护规则

应从协议层而不是“提醒模型小心”层面防幻觉。

必须明确：

- 价格、涨跌幅、排名、收益率、仓位、回撤等数值字段不得由 LLM 自由生成
- 若 `AnalysisBundle` 中无对应字段，报告中不得出现该类数值
- 报告中的建议性措辞不能替代真实信号字段
- 若模型输出不符合 schema，必须判定为失败并重试或降级

## 8. 建议的数据模型

为了快速形成闭环，建议至少设计以下核心表。

### 8.1 `quant_strategy`

字段建议：

- `id`
- `name`
- `strategy_type`
- `status`
- `symbols_json`
- `rule_config_json`
- `risk_config_json`
- `strategy_version`
- `active_prompt_version`
- `created_at`
- `updated_at`

### 8.2 `quant_prompt_template`

字段建议：

- `id`
- `strategy_id`
- `prompt_version`
- `prompt_template`
- `change_note`
- `enabled`
- `created_at`

### 8.3 `quant_schedule`

字段建议：

- `id`
- `strategy_id`
- `schedule_type`
- `cron_expr`
- `market_calendar`
- `enabled`
- `last_run_at`
- `next_run_at`

### 8.4 `market_snapshot`

不建议只做 `feature_json + raw_json` 双大字段。

建议最少将常用查询字段固化为列：

- `id`
- `symbol`
- `trade_date`
- `timeframe`
- `close_price`
- `pct_change`
- `volume`
- `turnover`
- `ma5`
- `ma10`
- `ma20`
- `volatility`
- `feature_json`
- `raw_json`
- `data_source`
- `data_source_version`
- `created_at`

这样可以支持：

- 横截面排序
- 条件筛选
- 风险扫描

而不是每次都全表反序列化 JSON。

### 8.5 `strategy_run`

字段建议：

- `id`
- `strategy_id`
- `strategy_version`
- `prompt_version`
- `bundle_version`
- `run_type`
- `status`
- `input_hash`
- `code_version`
- `data_source_version`
- `output_json`
- `error_message`
- `started_at`
- `finished_at`

关于 `input_hash` 必须补充约束：

- 不能包含毫秒级随机时间戳
- 应包含策略版本、输入数据版本、计划执行时点、运行类型
- 不应包含无关的格式化字段

否则会出现：

- 永远不命中幂等
- 或错误命中历史运行

### 8.6 `position_journal`

字段建议：

- `id`
- `strategy_id`
- `symbol`
- `side`
- `price`
- `quantity`
- `occurred_at`
- `source`
- `reason`
- `remark`

### 8.7 `report_delivery`

字段建议：

- `id`
- `run_id`
- `channel_type`
- `channel_target`
- `status`
- `request_payload`
- `response_payload`
- `sent_at`

### 8.8 `memory_note`

字段建议：

- `id`
- `strategy_id`
- `symbol`
- `note_type`
- `content`
- `tags`
- `score`
- `score_horizon`
- `source_run_id`
- `created_at`

这里 `score` 不能只作为模糊“经验分”，需要明确：

- 是收益标签
- 还是人工评分
- 还是策略置信回填

建议至少额外保存 `score_horizon`，例如：

- `T+1`
- `T+5`
- `holding_period`

### 8.9 `backtest_job`

字段建议：

- `id`
- `strategy_id`
- `strategy_version`
- `benchmark`
- `sample_range`
- `validation_range`
- `config_json`
- `result_summary_json`
- `artifact_path`
- `code_version`
- `data_source_version`
- `status`
- `created_at`
- `finished_at`

如果只做最小 MVP，可以先收缩为 5 张表：

- `quant_strategy`
- `quant_prompt_template`
- `strategy_run`
- `position_journal`
- `report_delivery`

## 9. IM 报告推送设计

目标是支持“交易日每日 2~3 次”报告推送到指定 IM。

建议优先支持 webhook 型机器人渠道：

- 飞书
- 企业微信
- 钉钉

原因：

- 接入简单
- 不需要复杂 OAuth
- 足够满足群通知和日报推送需求

推荐默认执行时点：

- 09:20 盘前观察
- 11:35 午间简报
- 15:10 收盘复盘

这些时间点不应写死，应该配置化。

推荐发送链路：

1. 调度器触发策略运行
2. 生成结构化分析结果
3. 组装 `AnalysisBundle`
4. LLM 返回 `ReportDraft`
5. 程序模板化渲染最终 Markdown
6. 调用 webhook 发送
7. 将发送结果落库
8. 失败时按策略重试

## 10. 回测与评估建议

第一阶段不建议直接上重量级研究平台，建议先做简化版回测。

### 10.1 第一阶段

基于 `pandas` 实现轻量事件驱动或日频回测：

- 收益率
- 最大回撤
- 胜率
- 盈亏比
- 换手率
- 基准对比

这足够支撑：

- 策略可行性初评
- 参数调整前后对比
- 例行复盘

### 10.2 第二阶段

如果规则策略逐渐稳定，可考虑引入：

- `backtrader`

如果未来演进为更重的研究平台，再考虑：

- `Qlib`

不建议一开始就引入 `Qlib`，原因是：

- 学习与集成成本较高
- 对当前项目体量偏重
- 可能导致开发重心从“做出闭环能力”偏移到“搭研究平台”

## 11. 自学习与样本隔离设计

建议将“自学习”拆为三个阶段理解，但必须增加样本时点和隔离约束。

### 11.1 阶段一：经验沉淀

- 保存每次信号、报告、人工操作和事后表现
- 标记成功和失败案例
- 汇总常见失效场景

### 11.2 阶段二：参数建议

- 定期分析过去样本窗口表现
- 对策略参数给出调整建议
- 由人工审核是否生效

### 11.3 阶段三：历史案例召回

- 对非结构化复盘内容生成 embedding
- 报告生成时召回相似历史案例
- 在报告中加入类似场景下的历史经验

### 11.4 评估时点契约

这是自学习设计里必须明确的一层。

需要定义：

- 信号产生时点
- 标签回填时点
- 标签计算口径
- 持有期口径

例如：

- T 日 09:20 盘前信号
- 使用 T 日收盘到 T+5 收盘收益作为标签
- 或使用固定持有期收益作为标签

必须避免：

- 用未来已经发生的结果回写当天报告逻辑
- 不同类型信号混用不同标签口径却未显式记录

### 11.5 参数建议的样本隔离

参数建议本身就存在数据泄露风险。

因此建议明确：

- 用于生成参数建议的样本窗口，不能直接作为验证窗口
- 至少采用“建议样本窗口”和“验证样本窗口”分离
- 参数生效后，效果评估必须看未参与建议生成的新样本

这本质上是简化版 walk-forward 思路。

### 11.6 embedding 召回的边界

相似案例召回只能作为解释增强，不能直接视为交易因果依据。

必须明确：

- 相似文本或相似形态不代表相似后续走势
- 召回结果仅用于补充经验、风险提醒和复盘参考
- 不应作为直接买卖触发条件

## 12. 推荐技术选型

### 12.1 后端基础依赖

建议新增依赖：

- `pandas`
- `numpy`
- `apscheduler`
- `akshare`
- `pandas_market_calendars` 或 `exchange_calendars`
- `tenacity`

可选依赖：

- `backtrader`
- `matplotlib` 或 `plotly`

### 12.2 AI 与记忆

如果后续做 embedding 记忆能力，可考虑：

- OpenAI embeddings
- 本地简单向量存储或先直接落库

第一阶段不强制引入复杂向量数据库。

## 13. 开发阶段建议

推荐按 4 期推进，但每一期必须有完成定义和放弃条件。

### 13.1 第一期：先做可运行闭环

范围：

- 策略配置
- 标的池管理
- 定时抓取行情
- 规则打分
- AI 报告生成
- IM webhook 推送
- 执行记录查询

完成定义建议：

- 连续 5 个交易日按计划发送报告
- 关键时点报告送达成功率不低于 99%
- 同一计划任务无重复执行
- 失败任务可重试且有状态可查
- 单 worker 模式下无明显 SQLite 锁冲突

放弃条件建议：

- 若持续出现 `database is locked` 且无法通过降并发缓解，则停止继续堆功能，优先迁移数据库
- 若 AI 报告内容无法稳定符合结构化契约，则先回退到纯模板报告

### 13.2 第二期：补操作登记与评估

范围：

- 人工买卖登记
- 建议与实际执行对照
- 基础回测
- 周报和月报

完成定义建议：

- 操作登记可追溯到对应 run
- 回测结果可按策略版本复现
- 周报和月报生成链路稳定

放弃条件建议：

- 若策略结果尚不稳定，暂停复杂报表和多维评估扩展，先固化信号质量

### 13.3 第三期：补记忆与自学习

范围：

- 历史案例沉淀
- embedding 检索
- 参数优化建议
- 失败模式归纳

完成定义建议：

- 至少支持受控的历史案例召回
- 参数建议能区分训练窗口和验证窗口
- 复盘中能追溯建议来源与样本口径

放弃条件建议：

- 若历史召回无法带来稳定信息增益，保留经验档案，不强推 embedding 在线化

### 13.4 第四期：再考虑半自动执行

范围：

- 接券商或交易接口
- 风控阈值
- 模拟盘/实盘切换
- 审批流

完成定义建议：

- 有完整风控开关
- 有审批或人工确认链路
- 有模拟盘稳定验证周期

放弃条件建议：

- 若前 3 期仍无法稳定证明信号质量和执行一致性，则不进入自动化下单阶段

明确建议自动下单放在最后阶段。

## 14. 主要风险与注意事项

### 14.1 数据源稳定性

免费数据源在字段、频率、稳定性上可能变化较快，需要：

- 数据缓存
- 失败重试
- 字段兼容
- 降级方案

### 14.2 调度重复执行

如果未来 Web 服务以多进程部署，不能把所有定时任务直接绑在 Flask 进程中，否则容易重复触发。

### 14.3 LLM 幻觉

AI 适合：

- 报告
- 总结
- 风险提示
- 复盘

不适合直接无约束地产生买卖信号或关键数值字段。

### 14.4 自学习污染和前视偏差

如果学习逻辑、标签回填和验证窗口不严格区分，会出现比普通回测更隐蔽的数据泄露。

### 14.5 SQLite 锁竞争

MVP 阶段 SQLite 只有在单 worker、低频写入和受控并发前提下才成立。

### 14.6 可复现性不足

如果不记录：

- 代码版本
- prompt 版本
- bundle 版本
- 数据源版本

则回测和报告都很难复现。

## 15. 最终建议

如果目标是尽快在现有系统上做出一个真正可用的量化能力，建议采用如下路线：

- 基于现有 Flask 项目扩展 `quant` 子系统
- 用独立单实例 worker + `APScheduler` 跑定时任务
- 先用 `AkShare + pandas` 做数据与规则策略
- 用结构化契约约束 LLM，只让其负责解释和复盘
- 用 webhook 接入飞书、企微、钉钉
- 用 SQLite 做 MVP，但把锁竞争和迁移条件写进设计
- 回测先做简化版
- 自动下单后置

这条路线的优点是：

- 对现有代码侵入较小
- 能较快形成端到端闭环
- 风险边界更清楚
- 后续迁移路径明确

## 16. 可作为下一步的输出物

在本设计评估基础上，后续可以继续补充：

- 数据库表结构草案
- Peewee 模型定义草案
- 后端 API 清单
- 前端页面原型
- 第一阶段任务拆解清单
- 部署与运行方案
- `AnalysisBundle` 与 `ReportDraft` 的 JSON schema

