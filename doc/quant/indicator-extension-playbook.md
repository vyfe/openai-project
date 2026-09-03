# 量化指标横向扩展开发指南

> 一份"新增一个指标需要动哪些地方"的执行手册（v2，已用 RSI / ATR / OBV 三个常见指标实践验证）。
>
> 适用场景：往量化子系统里加一个新的数据指标（如 RSI、布林带宽、ATR、换手率分位等），
> 并保证它在**策略 IDE / 试算 dry_run / 回测 / 单元测试 / 前端元数据面板**之间统一可用。

---

## 0. 阅读对象与前置知识

| 角色 | 必读章节 |
|---|---|
| 后端工程师 | §1（架构）、§2（实现 compute）、§3（注册）、§5（联动检查）、§6（测试） |
| 前端工程师 | §1、§4 |
| 想理解全链路的新人 | §1 → §2 → §3 → §4 → §5 → §6 顺序读 |

> 阅读本指南前请先看 `AGENTS.md` §3.5（量化子系统总览）与 `doc/quant/strategy-rule-module.md`（策略规则引擎）。
>
> **v2 修订要点**（v1 错误修正见文末 §11）：
> 1. `_concrete_output_names` 已改为通用展开逻辑，不再需要手工写特例。
> 2. compute 函数 bars 输入约定为**新→旧**顺序（bars[0] 最新，bars[-1] 最旧）。
> 3. 暖启动期判定：第一个有效位置是 `first_valid = n - window - 1`（最旧侧），新增值通过 Wilder 递推填更新侧。

---

## 1. 架构总览：一条总线，五个消费者

新增一个指标只需要在 **registry 注册表** 写一次条目；其它模块都从这里读，不需要改分派代码。

```
                  ┌────────────────────────────────────┐
                  │ service/quant/indicator_registry   │  ← 唯一元数据来源
                  │  IndicatorSpec / ParamSpec /       │     (ParamSpec、OutputSpec、compute 函数)
                  │  OutputSpec + register()           │
                  └────────────────┬───────────────────┘
                                   │ catalog_payload() / INDICATOR_REGISTRY
            ┌──────────────────────┼─────────────────────────────────┐
            │                      │                                 │
   ┌────────▼─────────┐   ┌────────▼──────────┐         ┌────────────▼────────────┐
   │ indicator_       │   │ rule_engine        │         │ strategy_routes          │
   │ service.compute_*│   │ evaluate_series    │         │ /strategy/dry_run         │
   │ + upsert_daily_* │   │ (v2 表达式路径)    │         │ /strategy/validate       │
   └────────┬─────────┘   └────────┬──────────┘         │ /meta/indicators         │
            │                      │                     └────────────┬────────────┘
            │              ┌───────▼──────────┐                      │
            │              │ backtest_service │                      │ catalog_payload()
            │              │ evaluate_series  │                      │
            │              └───────┬──────────┘                      │
            │                      │                                 │
   ┌────────▼──────────────────────▼────────────────┐    ┌──────────▼───────────┐
   │ data_routes                                      │    │ 前端 IndicatorPalette│
   │ /data/indicators/compute（无状态计算）          │    │ + useStrategyIde     │
   │ /data/indicators（持久层读取）                  │    │ + dryRun / validate  │
   │ _concrete_output_names 模板展开                │    └──────────────────────┘
   └─────────────────────────────────────────────────┘
            │
   ┌────────▼───────────────┐
   │ tests/unit / service   │  ← 单元/集成/路由测试，按本指南 §6 模板照抄
   └────────────────────────┘
```

**核心原则**：

- **单一来源**：registry 是元数据的唯一权威；compute 函数是行为的唯一权威。
- **零分派**：消费者（rule_engine、backtest、IDE 校验、LLM 生成 expr）从 registry 取 `key/outputs/compute`，**不**写 if-elif。
- **派生而非复制**：`INDICATOR_BASE_LOOKBACK` / `SUPPORTED_INDICATOR_GROUPS` 是从 registry 派生的别名，**不要**手维护。
- **bars 输入约定**：compute 函数接收的是**新→旧**顺序（bars[0] 最新，bars[-1] 最旧），与 `compute_vol_ratio` / `compute_rolling_high_low` 等老 compute 一致。引擎（`evaluate_series`）会自动按调用方传入的顺序使用，但**不会**重新排序。

> ✅ 推荐读者先在 IDE 里把 `indicator_registry.py`（140 行）和 `indicator_service._bind_registry()`（约 100 行）整体读一遍，再回头看下文。

---

## 2. 第一步：实现 compute 函数（行为层）

`compute` 函数是指标的"算法本体"，**所有消费者最终都通过它拿数据**。

### 2.1 函数签名（强制）

```python
from typing import Optional

def compute_<name>(bars: list, **params) -> dict[str, list]:
    """短一句描述。一句话即可。

    Args:
        bars: K 线序列（**新→旧顺序**：bars[0] 是最新，bars[-1] 是最旧）。
              duck type（只需 getattr 出字段）。
        **params: registry 里 ParamSpec 的 name → value。
                  类型在 ParamSpec.type 已声明；调用方负责校验。

    Returns:
        {output_name: list}；每个 list 长度 = len(bars)，
        顺序与 bars 对齐，缺位填 None。
    """
```

### 2.2 现有 compute 函数清单（可作为模板）

| 指标 | 文件 | 行数 | 输出 | 备注 |
|---|---|---|---|---|
| `compute_vol_ratio` | `indicator_service.py` | ~22 行 | `vol_ratio_{window}` | 量比；窗口内 None 清洗后取均值；当前 bar 为 0/None 返回 None |
| `compute_period_return` | `indicator_service.py` | ~16 行 | `period_return_{lookback}` | N 日涨幅（百分比）；越界返回 None |
| `compute_rolling_high_low` | `indicator_service.py` | ~21 行 | `rolling_high_{w}` / `rolling_low_{w}` | **排除当前 bar**（避免未来函数） |
| `compute_rsi` | `indicator_service.py` | ~45 行 | `rsi_{window}` | Wilder 平滑；首期均值按有效值数作分母（兼容 None 边界） |
| `compute_atr` | `indicator_service.py` | ~50 行 | `atr_{window}` | True Range；最旧 bar 退化为 `\|high-low\|` |
| `compute_obv` | `indicator_service.py` | ~25 行 | `obv` | 累计能量潮；无参数 |

### 2.3 必须遵守的不变量

1. **顺序对齐**：返回 list 长度必须等于 `len(bars)`，下标 `i` 对应 `bars[i]`（bars[i] 越新，返回值越新）。
3. **None 传播**：计算不出就返回 `None`，**不要**返回 `0` 或 `nan`——`expression_engine` 把 `None` 视为"未通过 / 暖启动期"。
4. **排除当前 bar**：所有 `*_high_N` / `*_low_N` / `*_N_ago` 这类回看型指标，**必须**从 `i+1` 开始往前取（见 `compute_rolling_high_low`）。
5. **窗口清洗**：分母/均值计算跳过 `None`（用 `[v for v in arr if v is not None]`），但返回的 list 中分母为 0 的位置仍填 `None`。
6. **数值精度**：保留 4~6 位小数；超过 6 位没有意义（下游规则引擎和持久化都用 Python float）。
7. **不要抛异常**：参数越界、空 bars、未来函数等场景返回空 dict 或全 None list——上层会优雅降级。
8. **bars 顺序**：见 §2.1，必须新→旧。`_make_history` 默认就是新→旧（reverse 过的），所以测试里通常不需要再 reverse。

### 2.4 暖启动期语义（关键）

绝大多数滑动窗口指标的"第一个有效位置"是 `first_valid = n - window - 1`（最旧的有效位置）。算法的填值逻辑：

```
out[first_valid]                              ← 首次均值（最旧侧）
for i in range(first_valid - 1, -1, -1):      ← 向 0 方向递推（Wilder 平滑：滑入 gains[i]）
    out[i] = ...
out[first_valid + 1 ...] = None               ← 比 first_valid 还旧的位置无前置数据
```

**反直觉之处**：`bars[0]` 是最新，`out[0]` 通常**有**值（已经被 Wilder 递推填过）；`out[-1]` 通常是 `None`（最早的位置没有足够的前置数据）。这一点跟 `compute_vol_ratio` / `compute_period_return` 语义**完全一致**——它们的"无值区"也都在最旧侧。

### 2.5 最小可运行模板（RSI 完整版）

```python
def compute_rsi(bars: list, window: int = 14) -> dict[str, list]:
    """RSI 相对强弱指标（N 日，Wilder 平滑）。

    返回 {f"rsi_{window}": list[float|None]}，长度 = len(bars)，顺序与 bars 对齐。
    bars 数不足 window+1 → 全 None；窗口内 avg_loss == 0 → 100.0。
    暖启动期：out[n-window ... n-1] = None（最旧侧 window 根）。
    """
    n = len(bars)
    out: list[Optional[float]] = [None] * n
    if n <= window:                           # 至少需要 window+1 根 bars
        return {f"rsi_{window}": out}

    diffs = [None] * n
    for i in range(n - 1):                    # 最后一根 bars 没有 prev_close → diffs[n-1]=None
        cur = getattr(bars[i], "close_price", None)
        prev = getattr(bars[i + 1], "close_price", None)
        if cur is None or prev in (None, 0):
            continue
        diffs[i] = cur - prev

    gains = [(d if d > 0 else 0.0) if d is not None else None for d in diffs]
    losses = [(-d if d < 0 else 0.0) if d is not None else None for d in diffs]

    first_valid = n - window - 1              # 最旧的有效位置
    if first_valid < 0:
        return {f"rsi_{window}": out}

    # 首次均值按"有效值数"作分母（diffs[n-1] 是 None，所以 init_count = window 而非 window+1）
    init_gains = [gains[j] for j in range(first_valid, first_valid + window) if gains[j] is not None]
    init_losses = [losses[j] for j in range(first_valid, first_valid + window) if losses[j] is not None]
    init_count = max(len(init_gains), len(init_losses), 1)
    avg_gain = sum(init_gains) / init_count if init_gains else 0.0
    avg_loss = sum(init_losses) / init_count if init_losses else 0.0

    out[first_valid] = (
        100.0 if avg_loss == 0 else round(100 - 100 / (1 + avg_gain / avg_loss), 6)
    )
    # Wilder 平滑向 0（最新）方向递推
    for i in range(first_valid - 1, -1, -1):
        g = gains[i] or 0.0
        l = losses[i] or 0.0
        avg_gain = (avg_gain * (window - 1) + g) / window
        avg_loss = (avg_loss * (window - 1) + l) / window
        out[i] = (
            100.0 if avg_loss == 0 else round(100 - 100 / (1 + avg_gain / avg_loss), 6)
        )
    return {f"rsi_{window}": out}
```

---

## 3. 第二步：注册到 registry（元数据层）

把 compute 函数和元数据挂到 `indicator_service._bind_registry()` 里，**紧挨着**已有 register 调用追加。

### 3.1 四种"输出名"模式

| 场景 | outputs 写法 | 模板展开位置 |
|---|---|---|
| 字面输出名（如 `macd_dif`） | `OutputSpec("macd_dif", "DIF", "numeric")` | — |
| 参数化单输出（如 `vol_ratio_5`） | `OutputSpec("vol_ratio_{window}", "量比{window}", "numeric")` | `_concrete_output_names` 通用展开逻辑 |
| 参数化多输出（如 `ma_5/ma_10`） | `OutputSpec("ma_{window}", "MA{window}", "numeric")` | 同上，按 `params[0].default`（int_list）逐项展开 |
| 多字段输出（如 `boll_mid/upper/lower`） | 写多条 `OutputSpec` | — |

### 3.2 register 模板

```python
ireg.register(ireg.IndicatorSpec(
    key="rsi",                                 # registry key
    label="RSI",                                # 前端面板标题
    category="momentum",                        # trend/momentum/volume/structure/volatility
    base_lookback=14,                           # 至少需要多少根 K 线（用于 get_required_history_size_v2）
    params=(ireg.ParamSpec(
        "window", "周期(天)", "int", 14, min=2, max=120,
        help="N 日 RSI；超过 70 视为超买区，低于 30 视为超卖区"
    ),),
    outputs=(ireg.OutputSpec("rsi_{window}", "RSI{window}", "numeric"),),
    compute=compute_rsi,
))
```

### 3.3 注册后系统会自动发生的事

下面这些**不需要**手动改：

- ✅ `catalog_payload()` 自动包含新指标 → 前端 `/quant/meta/indicators` 拉取后 `IndicatorPalette` 自动渲染。
- ✅ `INDICATOR_BASE_LOOKBACK` / `SUPPORTED_INDICATOR_GROUPS` 别名派生自 registry。
- ✅ `max_lookback_bars()` 走 `ireg.get_spec(name).base_lookback`。
- ✅ `_concrete_output_names()`（v2 已重写为通用展开）自动把 `rsi_{window}` 展开为 `rsi_14`，**无需**改 `data_routes`。
- ✅ `rule_engine._v2_compute_new_indicators` 自动调 `compute_rsi(bars, window=14)`。
- ✅ `rule_engine.get_required_history_size_v2` 自动取 `base_lookback=14`。

### 3.4 必须手工改的（剩下的两个补丁点）

- ⚠️ `rule_engine._v2_resolve_indicator_keys`：新增前缀映射（如果输出名是模板）
- ⚠️ `rule_engine._PARAM_NAME_PATTERNS` + 对应解析分支：让用户写 `rsi_30` 时自动提取 `window=30`

详见 §5.1、§5.2。

### 3.5 校验（必须做）

```bash
cd cyf/project/server
python -c "from service.quant import indicator_registry as ireg; print(ireg.all_keys())"
# 应包含新 key

python -c "from routes.quant import data_routes; print('rsi_14' in data_routes._INDICATOR_FIELD_NAMES)"
# 应输出 True

python -m pytest tests/unit/test_indicator_registry.py -v
# 全部通过
```

---

## 4. 第三步：接入策略 IDE / dry_run / validate / 回测

**好消息**：完成 §3 后，这些全部"自动可用"——IDE、validate、dry_run、回测、LLM 生成 expr 都通过同一份 `catalog_payload()` 拿到新指标。**不需要改前端任何代码**，只需在浏览器里刷新页面确认新指标出现在"指标"面板中。

### 4.1 IDE

- `/quant/meta/indicators` 自动返回新指标。
- `IndicatorPalette.expandOutputName` 自动把 `rsi_{window}` 展开成 `rsi_14`，点击插入到表达式。
- 前端类型 `IndicatorSpec`（`composables/quant/strategyIdeTypes.ts`）无需改——`catalog_payload` 字段稳定。

### 4.2 validate（`strategy_routes.quant_strategy_validate`）

- `strategy_routes.py:436–451` 已经从 registry 收所有 output 名到 `known` 白名单。
- 测试用例：在策略里写 `expr: "rsi_14 < 30"`，POST `/strategy/validate` 应返回 `{ok: true, ...}`。

### 4.3 dry_run / 回测

- 两个端点最终都走 `rule_engine.evaluate_series(cfg, bars_desc)`。
- `evaluate_series` 内部把 needed_keys 分桶：
  - **legacy 桶**：`ma / boll / macd / kdj / td_sequential / bottom_structure`（走 `compute_indicators` 一次性算）
  - **registry 桶**：其它带 `compute=` 的指标（包括 RSI / ATR / OBV）走 `_v2_compute_new_indicators`
- 回测的 `get_required_history_size_v2` 自动取 `base_lookback`。

### 4.4 LLM 表达生成（`expr_llm_service`）

- 把 `catalog_payload()` 喂给 LLM，让它从自然语言生成 expr。**不需要改 service 代码**。

---

## 5. 第四步：跨层联动检查（最容易漏的地方）

### 5.1 前缀映射：`_v2_resolve_indicator_keys`

文件：`cyf/project/server/service/quant/rule_engine.py`，函数 `_v2_resolve_indicator_keys`。

```python
def _v2_resolve_indicator_keys(used_names: set[str]) -> set[str]:
    keys: set[str] = set()
    for name in used_names:
        if name in ireg.INDICATOR_REGISTRY:
            keys.add(name)
            continue
        # ↓↓↓ 这里追加新指标的前缀规则 ↓↓↓
        if name.startswith("rsi_"):
            keys.add("rsi")
        elif name.startswith("atr_"):
            keys.add("atr")
        # ↑↑↑
        elif name.startswith("ma_"):
            keys.add("ma")
        ...
```

**判断标准**：如果新指标的输出名**有动态模板**（如 `rsi_{window}`），就要在前缀映射里加一行；如果是 `macd_dif` 这种字面名，`if name in ireg.INDICATOR_REGISTRY` 那行就够（不需要改这里）。

### 5.2 参数提取：`_v2_extract_params_from_expr`

文件：同 `rule_engine.py`，函数 `_v2_extract_params_from_expr` 与 `_PARAM_NAME_PATTERNS`。

```python
import re as _re
_PARAM_NAME_PATTERNS = {
    "ma": _re.compile(r"^ma_(\d+)$"),
    "vol_ratio": _re.compile(r"^vol_ratio_(\d+)$"),
    "period_return": _re.compile(r"^period_return_(\d+)$"),
    "rolling_high_low": _re.compile(r"^rolling_(?:high|low)_(\d+)$"),
    # ↓↓↓ 新指标追加 ↓↓↓
    "rsi": _re.compile(r"^rsi_(\d+)$"),
    "atr": _re.compile(r"^atr_(\d+)$"),
}
```

```python
# 在 _v2_extract_params_from_expr 里追加分支：
m = _PARAM_NAME_PATTERNS["rsi"].match(name)
if m and "rsi" not in out:
    out["rsi"] = {"window": int(m.group(1))}
```

**判断标准**：如果用户写 `rsi_30` 时应当自动得到 `window=30`（不必在 v2 cfg.indicators 里手填），就必须追加正则。

### 5.3 持久化（可选）：`upsert_daily_indicators`

如果要把指标落库到 `QuantDailyIndicator` 表：

1. 在 `indicator_service._bind_registry()` 之外，**额外**写一个 `_xxx_records_for_symbol()`；
2. 在 `upsert_daily_indicators()` 里加 `wants_xxx` 分支；
3. 加新列 / 改类型走 `tools/quant_db_migrate.py`（`AGENTS.md` §3.5.1）。

> 大多数新指标**不**需要这一层——registry compute 是"按需算"的，落库只在 dashboard / 数据导出场景才必要。

### 5.4 校验通过条件

```bash
# 1) 后端 pytest
cd cyf/project/server
.venv/bin/python -m pytest tests/unit -v
# 全部通过（491 用例）

.venv/bin/python -m pytest tests/service -v
# 全部通过（204 用例）

# 2) 前端测试
cd ../fe
npm run test

# 3) 浏览器手工验证
#    - 打开 /quant/strategy → 指标面板 → 找到新指标 → 拖入表达式
#    - 试算某只股票 → 命中点应与手工算一致

# 4) curl 验证元数据
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:39997/never_guess_my_usage/quant/meta/indicators \
  | jq '.data[] | select(.key=="rsi")'
```

---

## 6. 第五步：测试（必须）

按四个层级各写 1~3 个用例，模板如下。

### 6.1 单元：compute 函数行为

新建 `tests/unit/test_<name>_indicator.py`：

```python
"""<指标名> 单元测试。"""
from service.quant import indicator_service as isvc
from tests.unit.test_rule_engine import MockBar


class TestComputeRsi:
    def test_empty_bars(self):
        out = isvc.compute_rsi([], window=14)
        assert out == {"rsi_14": []}

    def test_warmup_returns_all_none(self):
        bars = [MockBar(close_price=10 + i * 0.1) for i in range(13)]
        out = isvc.compute_rsi(bars, window=14)
        assert all(v is None for v in out["rsi_14"])

    def test_output_aligned_with_bars(self):
        bars = [MockBar(close_price=10 + i * 0.1) for i in range(30)]
        out = isvc.compute_rsi(bars, window=14)
        assert len(out["rsi_14"]) == len(bars)

    def test_monotonic_up_trend_rsi_high(self):
        # bars 是新→旧顺序：先构造旧→新，再 reverse
        bars = [MockBar(close_price=10 + i * 0.5) for i in range(40)]
        bars.reverse()
        out = isvc.compute_rsi(bars, window=14)
        rsi_values = [v for v in out["rsi_14"] if v is not None]
        assert all(60 <= v <= 100 for v in rsi_values[-5:])
```

**注意**：`_make_history(n)` 在 `n > 15` 时会因内部硬编码的日期起点（`2025-01-15`）越界。需要自己构造 bars 或用 `bars.reverse()`。

### 6.2 单元：registry 元数据一致性

往 `tests/unit/test_indicator_registry.py` 追加：

```python
def test_<name>_key_registered():
    assert "<name>" in set(ireg.all_keys())


def test_<name>_base_lookback_matches_legacy():
    assert ireg.get_spec("<name>").base_lookback == 14


def test_<name>_compute_function_bound():
    assert ireg.get_spec("<name>").compute is not None


def test_<name>_output_in_concrete_set():
    from routes.quant import data_routes
    assert "rsi_14" in data_routes._INDICATOR_FIELD_NAMES
```

### 6.3 单元：表达式引擎集成

往 `tests/unit/test_evaluate_series.py` 追加：

```python
class TestRsiExpression:
    def _build_history(self, n: int):
        """绕过 _make_history 的日期越界，自行构造 bars（新→旧）。"""
        import datetime as _dt
        from tests.unit.test_rule_engine import MockBar
        bars = [
            MockBar(
                trade_date=_dt.date(2025, 6, 1) + _dt.timedelta(days=i),
                close_price=12.0 + i * 0.1,
            )
            for i in range(n)
        ]
        bars.reverse()
        return bars

    def test_rsi14_evaluates_through_registry(self):
        bars = self._build_history(40)
        cfg = {"version": 2, "rules": [{"id": "r1", "expr": "rsi_14 > 50", "weight": 1}]}
        out = evaluate_series(cfg, bars)
        m = out[0]["metrics"]["rules"][0]["metrics"]
        assert "value" in m or "error" in m

    def test_rsi_default_window_used_when_no_decl(self):
        cfg = {"version": 2, "rules": [{"id": "r1", "expr": "rsi_14 > 50", "weight": 1}]}
        assert get_required_history_size_v2(cfg) == 14
```

### 6.4 服务层：dry_run / 回测端到端

往 `tests/service/test_backtest_service.py`（或新建 `test_<name>_integration.py`）追加：

```python
def test_backtest_uses_<name>_signal():
    """RSI 超卖信号能正常进入 backtest trades。"""
    series_results = [
        {"passed": True, "score": 1.0, "signal_type": "buy",
         "reasons": ["r1: 通过"],
         "metrics": {"trade_date": "2026-09-01"}}
    ]
    bars_by_symbol = {"000001.SZ": [_fake_bar(date(2026, 9, 1), 10.0, 10.5),
                                     _fake_bar(date(2026, 9, 2), 11.0, 11.5)]}
    result = _run_backtest_with(series_results, bars_by_symbol)
    assert len(result["trades"]) == 1
```

### 6.5 API：路由冒烟（可选）

往 `tests/api/test_indicator_routes.py` 追加：

```python
def test_meta_indicators_includes_<name>(auth_client):
    res = auth_client.get("/never_guess_my_usage/quant/meta/indicators")
    keys = [item["key"] for item in res.get_json()["data"]]
    assert "<name>" in keys


def test_compute_<name>_endpoint(auth_client):
    res = auth_client.post(
        "/never_guess_my_usage/quant/data/indicators/compute",
        json={
            "symbol": "000001.SZ",
            "start_date": "2026-01-01",
            "end_date": "2026-06-01",
            "indicator_names": ["<name>"],
            "params": {"<name>": {"window": 14}},
        },
    )
    assert res.status_code == 200
```

---

## 7. 完整 checklist（提交前自检）

- [ ] `compute_<name>` 函数签名遵循 §2.1，bars 是**新→旧**顺序，暖启动期填 `first_valid = n - window - 1` 之后的值
- [ ] `ireg.register(...)` 写在 `_bind_registry()` 末尾，`key` 唯一不重复
- [ ] `base_lookback` 与 compute 实际最少 K 线需求一致
- [ ] 输出名有 `{...}` 模板时：
  - [ ] `_concrete_output_names`（v2 已通用）能正确展开——单元测试覆盖
  - [ ] `_v2_resolve_indicator_keys` 加了前缀规则（§5.1）
  - [ ] `_PARAM_NAME_PATTERNS` 加了正则（§5.2）
- [ ] 五个测试文件各加至少 1 个用例（§6.1–§6.3 必做，§6.4–§6.5 按需）
- [ ] 后端 `pytest tests/unit tests/service` 全绿
- [ ] 前端 `npm run test` 全绿
- [ ] 浏览器手工验证：IDE 面板出现新指标；dry_run 命中点合理
- [ ] 若改了 DB schema，走 `tools/quant_db_migrate.py`（`AGENTS.md` §3.5.1）落档
- [ ] 提交信息遵循仓库习惯（参考最近 commit：`reformat：指标机制后端化+数据中心升级`）

---

## 8. 反模式（不要这样做）

| ❌ 反模式 | ✅ 正确做法 |
|---|---|
| 在 `rule_engine._evaluate_one_rule` 里加 `if rule_type == "<name>":` 分支 | 走 registry + 表达式引擎 |
| 在 `data_routes._validate_indicator_names` 手维护白名单 | 已有逻辑自动从 `_concrete_output_names()` 派生 |
| 把 `<name>_window` 同时写进 `indicator_service.compute_indicators` 与 registry | 只在 registry 的 `compute=` 绑定，前者不再管 |
| 在 `_concrete_output_names` 里加 `if spec.key == "<name>":` 特例 | v2 通用展开：按 `params[0].default`（int / int_list）展开 |
| 在前端 `IndicatorSpec` 类型加新字段（如果只是后端加新指标） | TS 类型稳定；前端从 catalog 动态渲染 |
| 让 compute 函数抛异常处理"参数错误" | 用 None + 暖启动期语义；让上层优雅降级 |
| 把 compute 写成 async / 调外部 IO | compute 必须是纯 CPU 同步函数；数据从 `bars` 入参传入 |
| 让 compute 输出 dict 但 key 不在 `outputs` 里声明 | registry 是契约，compute 输出必须严格等于 `OutputSpec` 展开后的 key |
| 在 compute 内调用 `_ordered_bars()` 强行重排 | bars 已经约定为新→旧；自行重排会与上层语义不一致 |
| 在测试里用 `_make_history(40)` | 该 helper 内部日期起点硬编码 `2025-01-15`，n>15 会越界；自行构造 bars |

---

## 9. 进阶话题（按需阅读）

### 9.1 多输出 / 复合指标

如果一个指标同时产出多个相关字段（如布林线 mid/upper/lower），在 `outputs` 里写多条即可。`compute` 返回 dict 的 key 与 `OutputSpec.name` 必须一一对应。

### 9.2 参数枚举型（enum）

`ParamSpec.type = "enum"`，配合 `options=["buy", "sell", "watch"]`。前端下拉框自动渲染；后端校验在 `_validate_indicator_names` 不做枚举校验，靠 ParamSpec 帮助。

### 9.3 缓存 / 性能

`compute_indicators`（legacy 路径）有 `_compute_indicator_snapshot` 单 bar 内重复算历史均值的 O(N²) 行为——**新指标不要走这里**。在 registry 的 `compute=` 里实现，引擎会一次算完整个序列（O(N)）。

`expression_engine.compile_expression` 用 `lru_cache(maxsize=4096)`——同一 expr 不会重复解析。

### 9.4 v1 → v2 兼容

策略历史数据可能是 v1 形态（`rule_config` 里直接写 `"rule_type": "macd_golden_cross"`）。`rule_migration.migrate_v1_to_v2` 自动转换。新指标**只**写 v2 即可，不需要为 v1 加迁移路径。

---

## 10. 相关文件索引

| 关注点 | 文件 |
|---|---|
| 元数据 schema | `cyf/project/server/service/quant/indicator_registry.py` |
| compute 函数实现 | `cyf/project/server/service/quant/indicator_service.py` |
| `_bind_registry()` 入口 | `cyf/project/server/service/quant/indicator_service.py:_bind_registry()` |
| 表达式求值 | `cyf/project/server/service/quant/expression_engine.py` |
| 规则引擎（v2） | `cyf/project/server/service/quant/rule_engine.py` |
| 前缀映射 + 参数提取 | `cyf/project/server/service/quant/rule_engine.py:_v2_resolve_indicator_keys` / `_v2_extract_params_from_expr` |
| 回测入口 | `cyf/project/server/service/quant/backtest_service.py` |
| API 路由 | `cyf/project/server/routes/quant/strategy_routes.py`（`/meta/indicators`、`/strategy/validate`、`/strategy/dry_run`）|
| 计算 API + 模板展开 | `cyf/project/server/routes/quant/data_routes.py`（`/data/indicators/compute`、`/data/indicators`、`_concrete_output_names`）|
| 前端元数据消费 | `cyf/project/fe/src/views/quant/strategy/IndicatorPalette.vue` |
| 前端 IDE 状态 | `cyf/project/fe/src/composables/useStrategyIde.ts` |
| 前端 API 客户端 | `cyf/project/fe/src/services/quantApi.ts`（`quantMetaAPI.indicators()`）|
| 元数据一致性测试 | `cyf/project/server/tests/unit/test_indicator_registry.py` |
| 表达式引擎测试 | `cyf/project/server/tests/unit/test_evaluate_series.py` |
| DB schema 变更 | `cyf/project/server/tools/quant_db_migrate.py` |

---

## 11. v1 → v2 修订记录

| v1 错误描述 | v2 修正 |
|---|---|
| §1.3 说"_concrete_output_names 自动展开" | 实测：`data_routes._concrete_output_names` 在 v1 之前是硬编码 4 个 key 的特例，其它模板输出（如 `rsi_{window}`）不会展开。v2 已重写为通用展开逻辑（按 `params[0].default` 展开）。**新指标不需要再改 data_routes**。 |
| §1.3 说"compute bars 顺序引擎不挑" | 实测：compute 函数（`compute_vol_ratio` 等老 compute）以及新加的 RSI / ATR / OBV 都假设 bars 是**新→旧**顺序（bars[0] 最新）。`evaluate_series` 直接按入参顺序消费，**不会**重排。文档里把这一约定明确写出。 |
| §2.4 RSI 模板方向反了 | 把"Wilder 初始化用 `bars[:window]`"改成 `first_valid = n - window - 1` 的最旧侧起算；并补充首次均值按有效值数作分母（diffs[n-1] 永远是 None）。 |
| §2.4 没强调"暖启动期在最旧侧" | 加 §2.4 专门讲这一点（`first_valid = n - window - 1`，out[first_valid+1..] 是 None）。 |
| §6.3 测试用 `_make_history(40)` | 实际会因日期起点越界。改为自行构造 bars 或写 `_build_history` helper。 |
| §3.3 承诺"`_concrete_output_names` 自动展开 `rsi_{window}`" | 不再成立；改为"已改为通用展开，新指标无需改 data_routes"。 |

> 文档维护者：量化子系统。改动本文件后请同步更新 `AGENTS.md` §10.1 索引。