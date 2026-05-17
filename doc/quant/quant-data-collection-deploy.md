# 量化数据采集服务 - 管理员部署说明

## 1. 架构概述

```
┌─────────────────────────────────────────────────────┐
│  Flask Web (localhost:39997)                        │
│  ├─ 内存任务池 (task_dispatch_service)               │
│  ├─ quant.db (SQLite, 独立存放)                      │
│  └─ 对外 API: /never_guess_my_usage/quant/client/*  │
├─────────────────────────────────────────────────────┤
│  Scheduler Worker (quant_scheduler_worker.py)       │
│  └─ 按 cron 自动创建 data_sync 任务                  │
├─────────────────────────────────────────────────────┤
│  Data Client (quant_client/cli.py)                  │
│  ├─ 循环 claim 任务                                  │
│  ├─ 调用 Eastmoney → AKShare → Baostock 采集        │
│  └─ 回传 bundle 到服务端入库                          │
└─────────────────────────────────────────────────────┘
```

## 2. 服务端配置

### 2.1 conf.ini 量化段

在 `cyf/project/server/conf/conf.ini` 中配置：

```ini
[quant]
# 独立量化数据库。不要和 log.sqlite3_file 共用
sqlite3_file=./quant.db
# bundle 运行时目录
bundle_dir=./quant_bundles
# 股票记忆 Markdown 存储目录
memory_dir=./quant_memory
# 飞书自建应用（如需 IM 推送）
feishu_app_id=cli_xxx
feishu_app_secret=xxx
feishu_verification_token=xxx
feishu_encrypt_key=
```

### 2.2 启动 Web 服务

```bash
cd /Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/server
./local-run.sh
# 默认监听 http://localhost:39997
```

### 2.3 创建 admin 用户（首次部署）

任务创建需要 admin 权限。如果数据库中尚无 admin 用户：

```bash
cd cyf/project/server
python -c "
from model.entities import User
password_hash, salt = User.hash_password('你的admin密码')
User.create(username='admin', password_hash=password_hash, salt=salt, role='admin', is_active=True)
print('Admin created')
"
```

## 3. 调度 Worker 部署

调度 worker 负责按 cron 表达式自动创建数据同步任务。

### 3.1 创建调度配置

通过前端 Quant 工作台 → 调度中心，或直接调用 API：

```bash
# 登录获取 token
ADMIN_TOKEN=$(curl -s -X POST http://localhost:39997/never_guess_my_usage/login \
  -H "Content-Type: application/json" \
  -d '{"user":"admin","password":"你的密码"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")

# 创建 data_sync 调度（每天 15:20 执行）
curl -s -X POST http://localhost:39997/never_guess_my_usage/quant/scheduler/config/create \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{
    "name": "每日数据同步",
    "task_type": "data_sync",
    "cron_expr": "20 15 * * 1-5",
    "payload": {
      "symbols": ["600519", "000001.SZ", "000858.SZ", "601318.SH"],
      "provider": "auto",
      "lookback_trade_days": 1
    },
    "market_calendar": "A_SHARE",
    "retry_max": 1,
    "retry_delay_seconds": 180
  }'
```

**关键参数说明：**

| 参数 | 说明 |
|---|---|
| `task_type` | `data_sync`（数据同步）、`analysis_report`（分析报告）、`memory_digest`（记忆梳理）|
| `cron_expr` | 标准 cron 表达式，建议工作日执行 |
| `symbols` | A 股代码列表，支持 `600519` 或 `000001.SZ` 格式 |
| `provider` | `auto`（推荐，三源 fallback）、`eastmoney`、`akshare`、`baostock` |
| `lookback_trade_days` | 回溯交易日数（默认 20），用于确定抓取时间窗口 |
| `market_calendar` | 交易日历，当前仅支持 `A_SHARE` |

### 3.2 启动 Worker

```bash
cd cyf/project/server
python worker/quant_scheduler_worker.py
```

Worker 每 30 秒检查一次是否有到期调度需要执行。

## 4. 数据采集客户端部署

### 4.1 数据源选择

| Provider | 数据源 | 字段完整性 | 国内访问 | 海外访问 |
|---|---|---|---|---|
| `eastmoney` | 东方财富 Push API | 最全（含振幅、涨跌额、名称） | ✅ 快 | ❌ 受限 |
| `akshare` | 东方财富 + 新浪 | 完整 | ✅ | ❌ 间歇 |
| `baostock` | Baostock 独立服务 | 基本（无振幅/涨跌额/名称） | ✅ | ✅ 稳定 |
| `auto` | 三源 fallback | 按实际数据源 | ✅ | ✅（降级到 baostock） |

**推荐：生产环境（国内服务器）用 `auto`，海外调试用 `baostock`。**

### 4.2 客户端启动方式

#### 方式 A：循环脚本（推荐）

```bash
cd cyf/project/server
while true; do
  python -m quant_client.cli run-once \
    --server-url http://127.0.0.1:39997 \
    --client-id quant-prod-01 \
    --user test_user \
    --password test123
  sleep 15
done
```

#### 方式 B：手动认领 + 执行

```bash
# 仅认领（查看任务详情）
python -m quant_client.cli claim-task \
  --server-url http://127.0.0.1:39997 \
  --client-id quant-debug-01 \
  --user test_user \
  --password test123

# 手动抓取（不依赖任务池）
python -m quant_client.cli fetch-bars \
  --provider auto \
  --symbols 600519,000001.SZ \
  --start-date 2026-05-14 \
  --end-date 2026-05-16 \
  --adjust-flag qfq \
  --output /tmp/bundle.json.gz
```

### 4.3 重试机制

每个 provider 内部已实现 **3 次重试 + 失败 sleep 60s**：

- Eastmoney: 直连东方财富 Push API，每次超时 30s，3 次重试共 ~210s
- AKShare: 通过 akshare 库调用，每次超时取决于网络，3 次重试共 ~180s+
- Baostock: 独立登录 + 查询，每次超时较短，3 次重试共 ~180s+

`auto` provider 依次尝试 Eastmoney → AKShare → Baostock，任一个成功即返回。

## 5. 任务分配与查看

### 5.1 查看任务池

```bash
ADMIN_TOKEN=$(curl -s -X POST http://localhost:39997/never_guess_my_usage/login \
  -H "Content-Type: application/json" \
  -d '{"user":"admin","password":"你的密码"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")

curl -s http://localhost:39997/never_guess_my_usage/quant/client/tasks/list \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool
```

### 5.2 任务状态说明

| 状态 | 说明 |
|---|---|
| `pending` | 等待客户端认领 |
| `leased` | 已被客户端认领，租约 10 分钟，超时自动回收 |
| `success` | 执行成功，数据已入库 |
| `failed` | 执行失败，查看 `message` 字段获取错误详情 |

### 5.3 手动重置失败任务

```bash
curl -s -X POST http://localhost:39997/never_guess_my_usage/quant/client/tasks/reset \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"task_id": "具体任务ID"}'
```

重置后任务回到 `pending` 状态，等待下次客户端认领。

### 5.4 查看导入批次

```bash
curl -s http://localhost:39997/never_guess_my_usage/quant/data/import-batches?limit=20 \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool
```

### 5.5 查看最新数据日期

```bash
curl -s http://localhost:39997/never_guess_my_usage/quant/scheduler/meta \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('最新市场数据日期:', d['data'].get('latest_market_data_date'))
print('调度概览:', d['data'].get('overview'))
"
```

## 6. 数据去重机制

### 6.1 数据库层

| 表 | 唯一键 | 去重行为 |
|---|---|---|
| `quant_daily_bar` | `(symbol, trade_date, adjust_flag)` | `on_conflict_replace` — 重复导入时覆盖 |
| `quant_instrument` | `symbol` | `on_conflict_replace` — 重复时更新 name/source 等 |
| `quant_import_batch` | `batch_id` | 已存在则跳过，返回已有记录 |

### 6.2 注意事项

- 相同 symbol + 日期 + 复权类型的数据会被覆盖为最新导入的值
- 不会在任务创建阶段检查数据是否已存在（MVP 阶段设计），因此可能产生无实际数据变更的重复采集
- 生产环境建议通过调度 cron 的 `lookback_trade_days` 参数限制采集范围

## 7. 采集字段说明

### 7.1 日线数据 (quant_daily_bar)

| 字段 | 说明 | 东财 | AKShare | Baostock |
|---|---|---|---|---|
| `symbol` | 标准化代码 `600519.SH` | ✅ | ✅ | ✅ |
| `trade_date` | 交易日 | ✅ | ✅ | ✅ |
| `open_price` | 开盘价 | ✅ | ✅ | ✅ |
| `high_price` | 最高价 | ✅ | ✅ | ✅ |
| `low_price` | 最低价 | ✅ | ✅ | ✅ |
| `close_price` | 收盘价 | ✅ | ✅ | ✅ |
| `preclose_price` | 前收盘价 | ✅ | ✅ | ✅ |
| `volume` | 成交量（股） | ✅ | ✅ | ✅ |
| `amount` | 成交额（元） | ✅ | ✅ | ✅ |
| `turnover_rate` | 换手率（%） | ✅ | ✅ | ✅ |
| `pct_change` | 涨跌幅（%） | ✅ | ✅ | ✅ |
| `change` | 涨跌额（元） | ✅ | ❌ | ❌ |
| `amplitude_pct` | 振幅（%） | ✅ | ❌ | ❌ |

### 7.2 标的元数据 (quant_instrument)

| 字段 | 说明 | 东财 | 其他 |
|---|---|---|---|
| `name` | 股票名称 | ✅（自动填充） | ❌（留空，需手动补） |

## 8. 快速排障

### 问题：客户端 claim 不到任务

- 检查任务池：`/quant/client/tasks/list`
- 确认 scheduled worker 正常运行，已创建 data_sync 调度配置
- 或手动创建任务：`/quant/client/tasks/create`

### 问题：数据源全部失败

- 检查网络能否访问东方财富 / Baostock
- 检查 `auto` provider 的错误信息（会列出每个 provider 的失败原因）
- 国内服务器部署可解决东财/AKShare 网络问题

### 问题：任务状态 stuck 在 leased

- 客户端异常退出导致租约未释放
- 等待 10 分钟后自动回收，或手动 `reset`

### 问题：数据库锁定

- SQLite 单写锁设计，多客户端同时写入时会排队
- 确认只运行一个 Web 实例（runbook 硬约束）
- 检查 `busy_timeout` 参数（当前 5000ms）

## 9. 生产环境建议

1. **服务端部署在国内云服务器**，确保东财/AKShare 数据源可达
2. **每天至少一个数据客户端常驻运行**（循环脚本 + systemd/pm2）
3. **调度时间建议**：data_sync 15:20, analysis_report 15:35, memory_digest 21:30
4. **定期检查** `/quant/data/import-batches` 确认数据正常入库
5. **quant.db 独立存放**，不要与 log.db 混用，避免被日志清理策略误删
