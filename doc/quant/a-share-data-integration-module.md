# A 股数据集成模块设计说明

## 1. 目标范围

本模块聚焦 A 股为主的数据集成，第一阶段目标是：

- 支持 `AkShare` 与 `Baostock` 双数据源
- 支持 `auto` 回退策略，优先 `AkShare`，失败时自动退到 `Baostock`
- 支持按需拉取近 3~5 年日线数据
- 服务端使用独立 `quant.db` 存储量化数据
- 提供通用的数据 bundle 导入接口
- 提供独立 `quant_client` package 与可打包二进制入口
- Web 服务提供任务分派与客户端上报接口
- 支持通过“客户端轮询任务 -> 采集 -> 上报”的方式完成多终端数据中转
- 同时保留“人肉运行 + 人肉传文件 + 手工导入”的兜底模式

暂不包含：

- 高频分钟级数据
- 自动调度抓数
- 自动化下单
- 多实例 worker 协调

## 2. 数据源选择

### 2.1 AkShare

适合作为主数据源，优点：

- 接口覆盖广
- A 股、ETF、指数等数据源较丰富
- 对后续扩展财务、行业、宏观数据更友好

风险：

- 依赖公开站点或第三方源，存在限流、限 IP 或字段变化风险

适用定位：

- 默认主源
- 研究扩展源
- 在 `auto` 模式下作为首选尝试源

## 2.2 Baostock

适合作为稳定兜底源，优点：

- 历史日线接口较稳定
- A 股基础行情抓取足够实用

限制：

- 覆盖面和扩展性不如 AkShare
- 更适合作为 K 线级别的补源

适用定位：

- 日线兜底源
- 跨终端手工抓数的备用方案
- `AkShare` 失败时的 fallback 源

## 3. 为什么要做独立可分发采集器

核心原因不是“好看”，而是为了绕开服务端单点抓数的脆弱性。

如果数据源出现：

- 限流
- 限 IP
- 单机网络不稳定
- 目标环境无法直接访问

就可以在其他 Windows 或 macOS 终端上手工执行采集器，生成 bundle 文件，再通过人工方式回传到主服务导入。

因此采集器必须满足：

- 无需依赖当前 Web 服务在线抓数
- 可独立运行
- 输出标准 bundle 文件
- 可被 PyInstaller 打包为独立二进制

## 4. 当前实现结构

### 4.1 服务端

新增内容：

- 独立量化数据库配置：`[quant].sqlite3_file`
- 独立量化数据库：`quant.db`
- 量化数据表：
  - `quant_instrument`
  - `quant_daily_bar`
  - `quant_import_batch`
- 量化接口：
  - `/never_guess_my_usage/quant/providers`
  - `/never_guess_my_usage/quant/data/import`
  - `/never_guess_my_usage/quant/data/import_batches`
  - `/never_guess_my_usage/quant/data/daily_bars`

### 4.2 采集客户端 package

新增 package：

- `cyf/project/server/quant_client/`

兼容入口：

- `cyf/project/server/worker/quant_data_agent.py`

支持：

- 查看支持的数据源
- 拉取 A 股日线
- 输出标准 bundle JSON
- 输出 gzip 压缩 bundle
- 向服务端认领任务
- 拉取任务后执行一次采集并上报

### 4.3 服务端任务接口

新增任务分派相关接口：

- `POST /never_guess_my_usage/quant/client/tasks/create`
- `GET /never_guess_my_usage/quant/client/tasks/list`
- `POST /never_guess_my_usage/quant/client/tasks/reset`
- `POST /never_guess_my_usage/quant/client/tasks/claim`
- `POST /never_guess_my_usage/quant/client/tasks/report`

当前实现方式：

- 服务端内存态任务存储
- 单机进程内任务分派
- 客户端主动轮询认领

后续可替换为：

- Redis
- 消息队列
- 专用任务系统

## 5. Bundle 协议

当前 bundle 数据集类型为：

- `a_share_daily_bars_v1`

字段口径约定：

- `volume` 统一使用“股”
- `amount` 统一使用“元”
- `pct_change` 统一使用百分数数值，例如 `3.12` 表示 `3.12%`
- `trade_date` 统一使用 `YYYY-MM-DD`

核心字段：

```json
{
  "dataset": "a_share_daily_bars_v1",
  "bundle_version": 1,
  "batch_id": "uuid",
  "source": "akshare",
  "source_run_id": "uuid",
  "generated_at": "2026-04-30T12:00:00",
  "market": "A_SHARE",
  "provider_meta": {
    "provider_name": "akshare",
    "provider_version": "stock_zh_a_hist",
    "adjust_flag": "qfq",
    "start_date": "2022-01-01",
    "end_date": "2025-04-30"
  },
  "records": [
    {
      "symbol": "600519.SH",
      "code": "600519",
      "exchange": "SH",
      "trade_date": "2025-04-30",
      "adjust_flag": "qfq",
      "open_price": 1600.0,
      "high_price": 1615.0,
      "low_price": 1588.0,
      "close_price": 1602.0,
      "preclose_price": 1590.0,
      "volume": 123456.0,
      "amount": 190000000.0,
      "turnover_rate": 0.52,
      "pct_change": 0.75,
      "source": "akshare",
      "data_source_version": "stock_zh_a_hist"
    }
  ]
}
```

## 6. 两种运行模式

### 6.1 任务分派模式

建议优先使用这一模式。

流程：

1. 管理员在服务端创建抓数任务
2. 独立客户端轮询认领任务
3. 客户端本地执行抓数
4. 客户端将 bundle 上报回服务端
5. 服务端导入 `quant.db`

特点：

- 不需要人工回传文件
- 适合多终端协作抓数
- 后续更容易切换到队列

### 6.2 人肉搬运模式

建议流程：

1. 在可访问数据源的终端运行采集器
2. 输出 `bundle.json` 或 `bundle.json.gz`
3. 将文件人工传到主服务可访问的位置
4. 调用服务端导入接口导入主库
5. 通过查询接口验证导入结果

这样可以绕开：

- 服务端 IP 被限
- 公司网络限制
- 生产环境不能直接联网

## 7. 采集客户端示例

列出支持的数据源：

```bash
python cyf/project/server/worker/quant_data_agent.py providers
```

抓取单只股票近 3 年前复权日线：

```bash
python cyf/project/server/worker/quant_data_agent.py fetch-bars \
  --provider akshare \
  --symbols 600519 \
  --start-date 2022-01-01 \
  --end-date 2025-04-30 \
  --adjust-flag qfq \
  --output /tmp/600519-qfq.json
```

抓取多只股票并输出 gzip：

```bash
python cyf/project/server/worker/quant_data_agent.py fetch-bars \
  --provider baostock \
  --symbols 600519,000001,300750 \
  --start-date 2021-01-01 \
  --end-date 2025-04-30 \
  --adjust-flag qfq \
  --output /tmp/a-share-bars.json.gz
```

认领一个任务：

```bash
python cyf/project/server/worker/quant_data_agent.py claim-task \
  --server-url http://localhost:39997 \
  --client-id macbook-01 \
  --user admin \
  --password admin123
```

认领并执行一个任务：

```bash
python cyf/project/server/worker/quant_data_agent.py run-once \
  --server-url http://localhost:39997 \
  --client-id macbook-01 \
  --user admin \
  --password admin123
```

## 8. 服务端接口示例

创建任务：

```bash
curl -X POST "http://localhost:39997/never_guess_my_usage/quant/client/tasks/create" \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["600519.SH", "000001.SZ"],
    "start_date": "2022-01-01",
    "end_date": "2025-04-30",
    "provider": "auto",
    "adjust_flag": "qfq"
  }'
```

客户端上报仍然复用 bundle 导入能力，只是通过 `/client/tasks/report` 走任务完成链路。

手工导入接口仍保留：

支持 multipart 文件上传：

```bash
curl -X POST "http://localhost:39997/never_guess_my_usage/quant/data/import" \
  -H "Authorization: Bearer <admin_token>" \
  -F "bundle=@/tmp/a-share-bars.json.gz"
```

也支持直接传 JSON：

```bash
curl -X POST "http://localhost:39997/never_guess_my_usage/quant/data/import" \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d @/tmp/a-share-bars.json
```

## 9. 为什么当前先用内存态任务分派

当前阶段选择内存态任务分派，是为了先确认协议和执行链路，而不是过早引入额外基础设施。

这样做的好处：

- 改造成本低
- 可以快速验证客户端协议
- 服务端接口后续可平滑切换到队列实现

限制：

- 任务不持久化
- 服务重启后任务丢失
- 不适合多实例 Web 协调

因此当前定位非常明确：

- 开发期和单机试运行可用
- 后续可替换为 Redis 或消息队列

## 10. 可分发二进制建议

推荐路线：

- 保持 `quant_client/cli.py` 为真实 CLI 入口
- `worker/quant_data_agent.py` 仅作为兼容包装入口
- 在 Windows 上分别生成 Windows 可执行文件
- 在 macOS 上分别生成 macOS 可执行文件
- 不尝试跨平台交叉编译

建议使用 PyInstaller 的 one-file 或 one-folder 模式。

打包时注意：

- 打包环境必须安装对应依赖
- Windows 和 macOS 需要各自产包
- 目标机器若只是执行 bundle 抓取，不需要部署整套服务端

## 11. 当前边界与后续建议

当前实现边界：

- 只做 A 股日线
- 只做按需抓取
- 只做主库导入
- 任务分派先用内存
- 不做自动调度

后续可继续扩展：

- 批量股票池抓取
- 任务存储替换为 Redis 或消息队列
- 指数、ETF、财务数据导入
- 失败重试与 source fallback
- bundle 签名校验
- 增量同步水位管理
- 数据源优先级切换
- 策略与规则模块联动执行

## 12. 参考资料

- AkShare 官方文档: https://akshare.akfamily.xyz/
- AkShare GitHub: https://github.com/akfamily/akshare
- Baostock GitHub: https://github.com/myhhub/baostock
- Baostock PyPI: https://pypi.org/project/baostock/
- PyInstaller 官方文档: https://pyinstaller.org/en/stable/
