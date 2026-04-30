# 策略与规则模块说明

## 1. 当前目标

这版策略模块先解决一个最小但完整的问题：

- 主服务里可以配置策略
- 策略可以绑定 A 股股票池
- 策略可以配置一组日线规则
- 服务端可以基于 `quant.db` 已导入的日线数据执行策略
- 执行结果会落库存档
- 可以查询每次运行的信号结果

这一版还不追求：

- 复杂 DSL
- 自动调参
- 多周期混合规则
- 完整回测框架
- 组合级持仓管理

## 2. 新增存储

新增表：

- `quant_strategy`
- `quant_strategy_run`
- `quant_strategy_signal`

作用：

- `quant_strategy`：保存策略定义
- `quant_strategy_run`：保存每次执行摘要
- `quant_strategy_signal`：保存单个标的在一次执行中的结果

## 3. 当前支持的规则类型

规则配置放在 `rule_config.rules` 里，当前支持：

- `field_compare`
- `close_above_ma`
- `close_below_ma`
- `volume_ratio`
- `period_return`
- `breakout_high`

### 3.1 `field_compare`

直接比较当前 bar 的字段值。

示例：

```json
{
  "type": "field_compare",
  "field": "pct_change",
  "operator": ">=",
  "value": 2,
  "label": "涨跌幅至少 2%"
}
```

可用字段：

- `open_price`
- `high_price`
- `low_price`
- `close_price`
- `preclose_price`
- `volume`
- `amount`
- `turnover_rate`
- `pct_change`

### 3.2 `close_above_ma`

当前收盘价是否站上 N 日均线。

示例：

```json
{
  "type": "close_above_ma",
  "window": 5,
  "label": "收盘价站上 5 日均线"
}
```

### 3.3 `close_below_ma`

当前收盘价是否跌破 N 日均线。

### 3.4 `volume_ratio`

当前成交量与前 N 日平均成交量的比值。

示例：

```json
{
  "type": "volume_ratio",
  "window": 5,
  "operator": ">=",
  "value": 1.5,
  "label": "量比至少 1.5"
}
```

### 3.5 `period_return`

当前收盘价相对 N 日前收盘价的涨幅。

示例：

```json
{
  "type": "period_return",
  "lookback": 5,
  "operator": ">=",
  "value": 8,
  "label": "5 日涨幅至少 8%"
}
```

### 3.6 `breakout_high`

当前收盘价是否突破前 N 日最高价。

示例：

```json
{
  "type": "breakout_high",
  "window": 20,
  "label": "突破前 20 日高点"
}
```

## 4. 规则配置结构

完整示例：

```json
{
  "logic": "all",
  "signal_type": "watch",
  "min_score": 2,
  "rules": [
    {
      "type": "field_compare",
      "field": "turnover_rate",
      "operator": ">=",
      "value": 1.0,
      "weight": 1,
      "label": "换手率至少 1%"
    },
    {
      "type": "close_above_ma",
      "window": 5,
      "weight": 1,
      "label": "收盘站上 5 日线"
    },
    {
      "type": "volume_ratio",
      "window": 5,
      "operator": ">=",
      "value": 1.2,
      "weight": 1,
      "label": "量比至少 1.2"
    }
  ]
}
```

字段含义：

- `logic`
  - `all`：所有规则都通过才算通过
  - `any`：任一规则通过即可
- `signal_type`
  - 当前只是结果标签，例如 `watch`、`buy_watch`
- `min_score`
  - 通过规则累加的最小得分阈值
- `weight`
  - 每条规则通过后增加的分值

## 5. 接口

### 5.1 策略管理

- `GET /never_guess_my_usage/quant/strategy/list`
- `GET /never_guess_my_usage/quant/strategy/get/<strategy_id>`
- `POST /never_guess_my_usage/quant/strategy/create`
- `POST /never_guess_my_usage/quant/strategy/update`
- `POST /never_guess_my_usage/quant/strategy/delete`

### 5.2 策略执行

- `POST /never_guess_my_usage/quant/strategy/run`

支持：

- 指定 `strategy_id`
- 可选指定 `trade_date`
- 可选 `save_all_signals`

如果不传 `trade_date`，服务端会自动使用当前 `quant_daily_bar` 中的最新交易日。

### 5.3 结果查询

- `GET /never_guess_my_usage/quant/strategy/runs`
- `GET /never_guess_my_usage/quant/strategy/signals`
- `GET /never_guess_my_usage/quant/symbols`

## 6. 创建策略示例

```bash
curl -X POST "http://localhost:39997/never_guess_my_usage/quant/strategy/create" \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "放量突破观察",
    "description": "A股日线放量突破筛选",
    "symbols": ["600519.SH", "000001.SZ", "300750.SZ"],
    "rule_config": {
      "logic": "all",
      "signal_type": "watch",
      "min_score": 3,
      "rules": [
        {
          "type": "field_compare",
          "field": "turnover_rate",
          "operator": ">=",
          "value": 1.0,
          "weight": 1,
          "label": "换手率至少1%"
        },
        {
          "type": "close_above_ma",
          "window": 5,
          "weight": 1,
          "label": "收盘站上5日线"
        },
        {
          "type": "volume_ratio",
          "window": 5,
          "operator": ">=",
          "value": 1.2,
          "weight": 1,
          "label": "量比至少1.2"
        }
      ]
    }
  }'
```

## 7. 执行策略示例

```bash
curl -X POST "http://localhost:39997/never_guess_my_usage/quant/strategy/run" \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_id": 1,
    "trade_date": "2025-04-10",
    "save_all_signals": true
  }'
```

## 8. 当前边界

当前这版是规则引擎 MVP，边界很明确：

- 只支持日线数据
- 只支持单次扫描型策略
- 不做组合回测
- 不做仓位管理
- 不做多因子标准化
- 不做自动调参

这版的价值在于：我们现在已经可以把导入的数据真正跑成结构化信号，后面无论做报告、复盘还是调度，都有可复用的服务端执行入口。
