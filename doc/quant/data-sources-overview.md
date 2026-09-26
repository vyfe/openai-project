# 量化子系统数据源总览（v1 · 2026-09-23 新增同花顺官方源）

> 目的：把当前在用 / 可选用的所有行情数据源汇总到一份文档，给后续接入、对比、迁移提供
> 单一事实来源。后续每接入 / 弃用一个数据源，本文件必须同步更新。

---

## 0. TL;DR

- **2026-09-23 起新增 `ths`（同花顺官方）作为 auto 链首选**（priority 0），原 baostock 后移
  到 priority 1。`ths` 走 `https://fuyao.aicubes.cn/api/a-share/prices/historical`，需
  `X-api-key` 头，**仅支持日线**，单次请求 1 个 thscode。
- 现存 6 个 provider：`baostock / tencent / sina / yahoo`（active）+ `eastmoney / akshare`
  （**已弃用**：外网访问超时，仅保留显式调用兼容）。
- 字段完整度排序：**baostock (9) > ths (6 实字段 + pct/preclose 反算) = tencent (6+反算)
  > sina (5)**。Yahoo 字段最少（5 + adjclose）。
- 本节末尾给出「字段映射矩阵」和「接入示例」。

---

## 1. 数据源对照表

| 名称 | 类型 | Base URL | 鉴权 | 速率限制 | 主要能力 | 备注 |
|---|---|---|---|---|---|---|
| **ths**（新增） | 商业 API | `https://fuyao.aicubes.cn` | `X-api-key` | 动态（HTTP 429 / `code=4001`） | 日线 K（q/h/raw），行情快照，指数 K，财报，复权因子 | **首选**，须配置 api_key 最新文档地址：https://fuyao.aicubes.cn/llms-full.txt |
| **baostock** | 开源 SDK | `login()` + http | 无 | 宽松 | 日线 / 5/15/30/60min K，前/后/不复权 | 主力 backup，字段最全（含 turnover_rate） |
| **tencent** | 公开 HTTP | `web.ifzq.gtimg.cn` | 无 | 偶尔限流 | 日线 K，前/后/不复权；字段精简（6 字段） | 涨跌幅 / preclose 需相邻 close 反算 |
| **sina** | 公开 HTTP | `money.finance.sina.com.cn` | 无 | 偶尔限流 | 日线 K（仅 raw），当日 1/5/15/30/60min | 兜底，字段最少 |
| **yahoo** | 公开 HTTP | `query1.finance.yahoo.com` | 无 | 易限流 | 日 K / adjclose，**指数 + ETF 完整** | 兜底，对沪深指数覆盖好 |
| ~~eastmoney~~ | 公开 HTTP | `push2his.eastmoney.com` | 无 | **外网访问默认超时** | 日线 / 分钟 K | **已弃用**，显式调用发 `DeprecationWarning` |
| ~~akshare~~ | 开源 SDK | 多端点聚合 | 无 | **外网访问默认超时** | 全市场（含资金流 / 龙虎榜） | **已弃用**，显式调用发 `DeprecationWarning` |

### Auto Chain 当前排序（2026-09-23 后）

```python
_AUTO_CHAIN = [
    (0, ThsAshareProvider),          # 首选：同花顺官方，需 api_key
    (1, BaostockAshareProvider),     # 主力 backup：字段最全
    (2, TencentAshareProvider),      # 主力 backup：OHLCV + 涨跌幅反算
    (3, SinaAshareProvider),         # 主力 backup：仅 OHLCV
    (4, YfinanceAshareProvider),     # 兜底：指数 / ETF 全覆盖
]
```

`_AUTO_MINUTE_CHAIN` **不变**（ths 不支持分钟线）：

```python
_AUTO_MINUTE_CHAIN = [
    (0, BaostockAshareProvider),
    (1, EastmoneyAshareProvider),    # 分钟线 + 复权字段齐全（已弃用但分钟线暂未替换）
    (2, SinaAshareProvider),
]
```

---

## 2. 同花顺（ths）接入指南

### 2.1 获取 API Key

1. 登录 <https://fuyao.aicubes.cn/>（同花顺账号）。
2. 进入「API Key 管理」页：<https://fuyao.aicubes.cn/admin>
3. 点击 **创建 API Key**，填别名（如 `ai-quant-prod`），提交。
4. 弹窗中的完整 API Key **只展示一次**，立即保存到密码管理器或本地的 `.env`。

> ⚠️ API Key 与同花顺账号绑定；在管理页可查看/吊销。**不要把 Key 写入提示词 / git 仓库**。

### 2.2 配置

`cyf/project/server/conf/conf.ini` 的 `[quant]` 段新增：

```ini
[quant]
# 同花顺金融数据 API Key（fuyao.aicubes.cn）
ths_api_key=你的_API_Key
```

也可通过环境变量 `THS_API_KEY` 临时覆盖（优先级：conf > env）。

### 2.3 已使用端点（v1）

| 能力 | HTTP 方法 / 路径 | 说明 |
|---|---|---|
| A 股日线 K | `GET /api/a-share/prices/historical` | 单 thscode，1d 周期，adjust=none/forward/backward；窗口 ≤ 10 年 |

> 后续可按需扩展：snapshot / corporate-actions / financials / index / ticker-search 等。

### 2.4 请求示例

```bash
curl 'https://fuyao.aicubes.cn/api/a-share/prices/historical?thscode=600519.SH&interval=1d&start=1716105600000&end=1747641600000&adjust=forward' \
  -H 'X-api-key: <your-api-key>'
```

### 2.5 响应字段（`data.item[]` 为 `PriceBarItem`）

| 字段 | 类型 | 说明 | provider 输出映射 |
|---|---|---|---|
| `date_ms` | long | K 线日期（毫秒，Asia/Shanghai 零点） | → `trade_date`（ISO 8601 `YYYY-MM-DD`） |
| `open_price` | number | 开盘价（CNY） | → `open_price` |
| `high_price` | number | 最高价（CNY） | → `high_price` |
| `low_price` | number | 最低价（CNY） | → `low_price` |
| `close_price` | number | 收盘价（CNY） | → `close_price` |
| `volume` | number | 成交量（股） | → `volume` |
| `turnover` | number | 成交额（CNY） | → `amount` |

**不提供但 provider 反算**：
- `preclose_price`：上一交易日 close（首日为 `None`）
- `pct_change`：`(close - preclose) / preclose * 100`
- `change`：上一交易日 close 与当前 close 的差

**明确为 None**：`turnover_rate`（ths 不返回换手率）

### 2.6 错误码

| code | 含义 | 处理策略 |
|---|---|---|
| `0` | 成功 | - |
| `1001` / `1002` / `1003` / `1004` | 参数错 | 不重试，立即失败（per-symbol 容错吞掉） |
| `2001` | 未认证 | 不重试；检查 api_key |
| `2003` | 权限不足 | 不重试；联系管理员开 capability |
| `3001` | 标的不存在 | 不重试；该 symbol 跳过 |
| `3002` | 数据未就绪 | 不重试 |
| `4001` | 限流 | **fail-fast 不重试**（加重压力），per-symbol 容错吞掉 |
| `5001` / `5002` / `5003` | 上游故障 | 退避重试 ≤ 3 次 |

HTTP 429 与 `code=4001` 等价：fail-fast 不重试。

### 2.7 已知约束

- **每日一次只能拉 1 个 thscode**：批量请求会失败。Provider 内部循环遍历 symbols。
- **窗口 ≤ 10 年**：`end - start` 超过 10 年返回 `code=1003`。
- **仅日线 1d**：不实现 `fetch_minute_bars`。原因：
  - `/api/a-share/prices/historical` 的 `interval` 参数**当前仅支持 `1d`**（官方文档明确）。
  - `/api/a-share/high-frequency/historical` 虽然支持 `interval=1m`，但**官方明确"暂未开放外部接入"**，且返回的是专有指标 `hf_direction` / `hf_participation`，**不提供 OHLCV**，无法做回测 / 实时打分。
  - 因此分钟线仍走原链 `baostock → eastmoney → sina`，ths provider 显式抛 `NotImplementedError`，不进 `_AUTO_MINUTE_CHAIN`。
- **不复权 / 前复权 / 后复权**：`adjust=none/forward/backward`，provider 透传。
- **thscode 标准化**：入参会被服务端 `trim().toUpperCase()`；provider 输出统一 `code.EXCHANGE`
  （如 `600519.SH`），与 baostock/tencent/sina/yahoo 一致。

---

## 3. 字段映射矩阵

13 项核心字段在 5 个 active provider 间的可填充性：

| 字段 | ths | baostock | tencent | sina | yahoo |
|---|:-:|:-:|:-:|:-:|:-:|
| `trade_date` | ✅ 原始 | ✅ 原始 | ✅ 原始 | ✅ 原始 | ✅ 原始 |
| `open_price` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `high_price` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `low_price` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `close_price` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `preclose_price` | 🔄 反算 | ✅ | 🔄 反算 | 🔄 反算 | 🔄 反算 |
| `volume` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `amount` (turnover) | ✅ | ✅ | ❌ | ❌ | ❌ |
| `turnover_rate` | ❌ | ✅ | ❌ | ❌ | ❌ |
| `pct_change` | 🔄 反算 | ✅ | 🔄 反算 | 🔄 反算 | 🔄 反算 |
| `change` | 🔄 反算 | 🔄 反算 | ❌ | ❌ | 🔄 反算 |
| `amplitude_pct` | ❌ | ❌ | ❌ | ❌ | ❌ |
| `currency` | ✅ CNY 显式 | ⚠️ 隐式 | ⚠️ 隐式 | ⚠️ 隐式 | ✅ CNY |

✅ = 原始返回；🔄 = provider 层从相邻 bar 反算；❌ = 不提供；⚠️ = 隐式约定

> 写入 `KLine` 表前，各 provider 都已对齐这套字段语义。`amplitude_pct` 当前所有源
> 都不提供，由前端/后端 indicator 层自行用 `(high - low) / preclose` 计算。

---

## 4. 接入新数据源的通用流程

1. **加 provider**：`cyf/project/server/quant_client/provider_<name>.py`，继承
   `BaseAshareProvider`，至少实现 `fetch_daily_bars`。
2. **注册到 factory**：`provider_factory.py` 加入 `PROVIDER_MAP`；决定是否进
   `_AUTO_CHAIN` / `_AUTO_MINUTE_CHAIN` 及其优先级。
3. **配置**：在 `conf.ini.tpl` + `conf/settings.py` 增加配置项；env var 兜底。
4. **per-symbol 容错**：参考 `quant-provider-per-symbol-resilience` 记忆，**单 symbol 失败
   不能影响其他 symbol**，异常被吞掉记 `logger.warning`。
5. **单元测试**：`tests/unit/test_provider_<name>.py`，覆盖：symbol 转换、字段映射、
   错误码、限流 fail-fast、per-symbol 容错、auto chain 集成。
6. **连通性探针**：`tools/check_quant_sources.py` 增加 `probe_<name>_*` 探测点。
7. **本地 demo**：在 `tools/` 或 README 中给出「填 Key 后即可跑」的小脚本。
8. **更新本文档** §1 对照表 + §3 字段映射矩阵。

---

## 5. 调试与排障

- **连通性总览**：`python tools/check_quant_sources.py --symbol 600519.SH`
  （输出每源的 ok / items / 耗时 / 样例）
- **ths 专项 demo**：`python tools/ths_demo.py`（需先填 `THS_API_KEY` 或 `quant.ths_api_key`）
- **per-symbol 失败日志**：`logger.warning("ths_symbol_failed symbol=%s err=%s", ...)`
  关键字搜 `ths_symbol_failed`。
- **限流触发**：HTTP 429 / `code=4001` → 立即停止对该 provider 的后续请求
  （per-symbol 容错吞掉，但建议人工降并发）。

---

## 6. 未来扩展点（按需）

- `ths.snapshot`：替代/补充 yahoo 的指数快照（ths 指数 / 板块 / 行业 `886042.TI` /
  `881101.TI` 都支持）。
- `ths.corporate_actions`：复权因子事件流，可由客户端自行推导复权价。
- `ths.financials`：利润表 / 资产负债表 / 现金流量表多期序列。
- `ths.ticker_search`：替代现有的搜索服务（现 `symbol_search_service` 走 akshare）。
- `ths.market_dumps`：全 A 股 10 年日 K Parquet 下载（适合一次拉全市场回测）。

每次启用新端点需：provider 新增 method → factory 暴露 → 配置项（如需）→ 单元测试 →
更新本文档对应小节。