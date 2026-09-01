"""用大模型把用户的自然语言策略描述生成 rule_config 表达式。

仅依赖现有指标元数据（indicator_registry）+ 表达式语法说明，
不修改 rule_config 结构，不入库。
"""
from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from service.host_service import get_client_for_user
from service.quant.indicator_registry import INDICATOR_REGISTRY, catalog_payload


logger = logging.getLogger("quant.expr_llm")


SYSTEM_PROMPT_TEMPLATE = """你是量化策略表达式生成助手。给定用户的自然语言描述和当前已启用的指标，输出一条**纯表达式字符串**（不要任何解释、不要代码块包裹）。

## 表达式语法（受限 AST）

### 字段
- bar 字段（直接用）：{bar_fields}
- 别名（也支持）：close, open, high, low, vol, amt, pct, turnover（分别等价于 close_price 等）

### 算子（仅这些）
>, >=, <, <=, ==, !=

### 布尔
and, or, not

### 白名单函数（只能调用这些）
- prev(x)        → x 的前 1 根
- ref(x, n)       → x 的前 n 根
- avg(x, n)       → x 在当前及之前 n-1 根的均值
- abs(x)          → 绝对值
- min(a, b, ...)  → 最小值，跳过 None
- max(a, b, ...)  → 最大值，跳过 None
- cross_up(a, b)  → a 上穿 b（当前 a>b 且前一根 a<=b）
- cross_down(a,b) → a 下穿 b

### 变量（下标取前 N 根）
x[1] 等价于 prev(x)；x[n] 取前 n 根。只能是非负整数。

### 字符串字面量必须带双引号
例如 td_signal == "buy_setup_complete"

## 当前策略已启用指标（按用户的 indicator 配置动态生成）
{indicator_list}

## 输出格式（严格遵守）
仅返回一行 JSON，例如：
{{"expr": "close > ma_5"}}

不要 markdown 代码块、不要解释、不要多余文字。"""


USER_PROMPT_TEMPLATE = """用户的自然语言策略描述：
{description}

请生成一条表达式字符串（单一规则 expr，不要 gate 表达式）。"""


def _build_indicator_list(indicator_keys: list[str] | None) -> str:
    """把当前启用的指标列成清单，连同输出名一起给大模型看。"""
    keys = indicator_keys or []
    if not keys:
        return "（当前未启用任何指标；只能使用 bar 字段）"
    lines = []
    seen = set()
    for k in keys:
        spec = INDICATOR_REGISTRY.get(k)
        if not spec or k in seen:
            continue
        seen.add(k)
        out_names = ", ".join(o.name for o in spec.outputs if "{" not in o.name)
        if spec.outputs and any("{" in o.name for o in spec.outputs):
            # 模板输出名（如 ma_{window}），举例一个常用窗口
            tpl = next((o.name for o in spec.outputs if "{" in o.name), "")
            out_names += f", 模板示例：{tpl.replace('{window}', '5')}"
        lines.append(f"- {spec.label} ({spec.key})：输出 {out_names}")
    return "\n".join(lines) if lines else "（未启用任何指标）"


def generate_expr_from_description(
    username: str,
    description: str,
    indicator_keys: list[str] | None = None,
    model: str = "gpt-5.6-luna",
) -> dict[str, Any]:
    """调 LLM 生成一条 expr。

    返回 {"expr": "..."} 或 {"error": "..."}。
    """
    if not description.strip():
        return {"error": "策略描述不能为空"}

    try:
        client, _ = get_client_for_user(username)
    except Exception as exc:
        logger.warning("get_client_for_user failed: %s", exc)
        return {"error": f"无法获取 API client: {exc}"}

    # 取 bar 字段全集
    bar_fields = sorted({
        "open_price", "high_price", "low_price", "close_price",
        "volume", "amount", "pct_change", "turnover_rate"
    })
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        bar_fields=", ".join(bar_fields),
        indicator_list=_build_indicator_list(indicator_keys),
    )
    user_prompt = USER_PROMPT_TEMPLATE.format(description=description.strip())

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=200,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        logger.warning("LLM call failed for user=%s model=%s: %s", username, model, exc)
        return {"error": f"大模型调用失败：{exc}"}

    raw = (resp.choices[0].message.content or "").strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # 容错：模型可能输出 ```json ... ```，剥掉再 parse
        cleaned = raw.strip().strip("`").removeprefix("json").strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            return {"error": f"大模型返回无法解析：{raw[:200]}"}

    expr = str(parsed.get("expr") or "").strip()
    if not expr:
        return {"error": "大模型未返回表达式"}

    return {
        "expr": expr,
        "model": model,
        "usage": {
            "prompt_tokens": getattr(resp.usage, "prompt_tokens", 0) if resp.usage else 0,
            "completion_tokens": getattr(resp.usage, "completion_tokens", 0) if resp.usage else 0,
        },
    }


def build_system_prompt_preview(indicator_keys: list[str] | None = None) -> str:
    """前端 IDE 调试用：返回将发送给大模型的 system prompt 预览。"""
    bar_fields = sorted({
        "open_price", "high_price", "low_price", "close_price",
        "volume", "amount", "pct_change", "turnover_rate"
    })
    return SYSTEM_PROMPT_TEMPLATE.format(
        bar_fields=", ".join(bar_fields),
        indicator_list=_build_indicator_list(indicator_keys),
    )