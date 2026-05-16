from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from conf.settings import settings
from quant.entities import QuantDailyBar, QuantOperationRecord, QuantStrategySignal
from service.quant.common import normalize_symbol


MEMORY_FILE_VERSION = "memory-md-v1"
MEMORY_SECTION_KEY_MAP = {
    "当前画像": "current_profile",
    "近期事实": "recent_facts",
    "经验归纳": "lessons",
    "最近人工备注": "operator_notes",
    "评估口径": "evaluation_contract",
    "待验证假设": "hypotheses",
}


def _memory_root() -> Path:
    root = Path(settings.quant_memory_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _memory_file_path(symbol: str) -> Path:
    normalized = normalize_symbol(symbol)
    return _memory_root() / "symbols" / f"{normalized}.md"


def _latest_bar(symbol: str):
    return (
        QuantDailyBar.select()
        .where(QuantDailyBar.symbol == symbol)
        .order_by(QuantDailyBar.trade_date.desc())
        .first()
    )


def _recent_signals(symbol: str, since_dt: datetime):
    return (
        QuantStrategySignal.select()
        .where((QuantStrategySignal.symbol == symbol) & (QuantStrategySignal.created_at >= since_dt))
        .order_by(QuantStrategySignal.trade_date.desc(), QuantStrategySignal.id.desc())
        .limit(30)
    )


def _recent_operations(symbol: str, since_dt: datetime):
    return (
        QuantOperationRecord.select()
        .where((QuantOperationRecord.symbol == symbol) & (QuantOperationRecord.updated_at >= since_dt))
        .order_by(QuantOperationRecord.trade_date.desc(), QuantOperationRecord.id.desc())
        .limit(20)
    )


def _safe_rate(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "0.00%"
    return f"{(numerator / denominator) * 100:.2f}%"


def _build_current_profile(symbol: str, lookback_days: int) -> list[str]:
    latest_bar = _latest_bar(symbol)
    since_dt = datetime.now() - timedelta(days=lookback_days)
    signals = list(_recent_signals(symbol, since_dt))
    operations = list(_recent_operations(symbol, since_dt))
    passed_count = len([item for item in signals if item.passed])
    closed_operations = [item for item in operations if item.result_status in ("win", "loss", "flat")]
    win_count = len([item for item in closed_operations if item.result_status == "win"])
    profile = [f"- 记忆版本: `{MEMORY_FILE_VERSION}`"]
    if latest_bar:
        profile.append(
            f"- 最新行情: {latest_bar.trade_date.isoformat()} 收盘 `{latest_bar.close_price}`，涨跌幅 `{latest_bar.pct_change}`%"
        )
    profile.append(f"- 近 {lookback_days} 天信号: `{passed_count}/{len(signals)}` 条通过")
    profile.append(f"- 近 {lookback_days} 天已闭环操作: `{len(closed_operations)}` 条，胜率 `{_safe_rate(win_count, len(closed_operations))}`")
    return profile


def _build_recent_facts(symbol: str, lookback_days: int) -> list[str]:
    since_dt = datetime.now() - timedelta(days=lookback_days)
    signals = list(_recent_signals(symbol, since_dt))
    operations = list(_recent_operations(symbol, since_dt))
    facts = []
    for signal in signals[:8]:
        reasons = signal.to_dict().get("reasons", [])[:2]
        reasons_text = "；".join(reasons) if reasons else "规则通过"
        facts.append(f"- `{signal.trade_date.isoformat()}` 信号 `{signal.signal_type}`，得分 `{signal.score}`：{reasons_text}")
    for operation in operations[:8]:
        result_text = operation.result_status or "待复盘"
        facts.append(
            f"- `{operation.trade_date.isoformat()}` 人工 `{operation.action}`，状态 `{operation.status}`，结果 `{result_text}`，理由：{operation.thesis[:80] or '未填写'}"
        )
    return facts or ["- 最近还没有足够的信号或操作样本。"]


def _build_lessons(symbol: str, lookback_days: int) -> list[str]:
    since_dt = datetime.now() - timedelta(days=lookback_days)
    operations = [item for item in _recent_operations(symbol, since_dt) if item.result_status in ("win", "loss", "flat")]
    if not operations:
        return ["- 当前可复盘样本不足，先持续积累操作与结果。"]

    wins = [item for item in operations if item.result_status == "win"]
    losses = [item for item in operations if item.result_status == "loss"]
    lessons = [
        f"- 已闭环样本 `{len(operations)}` 条，盈利 `{len(wins)}` 条，亏损 `{len(losses)}` 条。"
    ]
    avg_result = [item.result_pct for item in operations if item.result_pct is not None]
    if avg_result:
        lessons.append(f"- 已记录收益率均值约 `{sum(avg_result) / len(avg_result):.4f}`，注意这只是手工回填口径。")
    if len(losses) > len(wins):
        lessons.append("- 最近失败样本偏多，建议回看入场时点和承接质量，不要把信号本身当作必然成交理由。")
    else:
        lessons.append("- 最近样本中正反馈略多，但仍需要结合成交量和次日承接做人工复核。")
    return lessons


def _build_hypotheses(symbol: str) -> list[str]:
    return [
        f"- {symbol} 的记忆仅用于解释增强和复盘参考，不能直接替代当天信号。",
        "- 若后续引入 embedding 召回，也应把这里作为可审阅的原始长期记忆文本。",
    ]


def _build_operator_notes(symbol: str, lookback_days: int) -> list[str]:
    since_dt = datetime.now() - timedelta(days=lookback_days)
    operations = list(_recent_operations(symbol, since_dt))
    notes = []
    for operation in operations[:8]:
        note_parts = [operation.execution_note or "", operation.review_note or "", operation.thesis or ""]
        note_text = "；".join([part.strip() for part in note_parts if str(part or "").strip()])[:120]
        if not note_text:
            continue
        notes.append(f"- `{operation.trade_date.isoformat()}` {operation.action} 备注：{note_text}")
    return notes or ["- 最近没有足够的人工备注，后续可在执行与复盘时持续补充。"]


def _build_evaluation_contract() -> list[str]:
    return [
        "- 当前记忆默认以人工操作闭环结果为主，未闭环样本只记事实，不参与经验归纳。",
        "- 若记录了 `result_pct`，则按该回填口径展示；不同持有期结果暂不混算为统一标签。",
        "- 当前阶段不自动回写参数配置，避免把复盘结论直接污染后续样本。",
    ]


def _parse_memory_sections(content: str) -> dict:
    sections = {value: [] for value in MEMORY_SECTION_KEY_MAP.values()}
    current_key = None
    for raw_line in (content or "").splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            current_key = MEMORY_SECTION_KEY_MAP.get(line[3:].strip())
            continue
        if current_key and line.startswith("- "):
            sections[current_key].append(line)
    return sections


def _build_memory_summary(content: str, sections: dict) -> dict:
    updated_at = None
    for raw_line in (content or "").splitlines():
        line = raw_line.strip()
        if line.startswith("- 更新时间:"):
            updated_at = line.split("`")[1] if "`" in line else line.replace("- 更新时间:", "").strip()
            break
    return {
        "updated_at": updated_at,
        "current_profile_count": len(sections.get("current_profile", [])),
        "recent_facts_count": len(sections.get("recent_facts", [])),
        "lessons_count": len(sections.get("lessons", [])),
        "operator_notes_count": len(sections.get("operator_notes", [])),
        "hypotheses_count": len(sections.get("hypotheses", [])),
    }


def build_symbol_memory_markdown(symbol: str, lookback_days: int = 120) -> str:
    normalized = normalize_symbol(symbol)
    lines = [
        f"# {normalized} 记忆档案",
        "",
        f"- 更新时间: `{datetime.now().isoformat(timespec='seconds')}`",
        "",
        "## 当前画像",
        *_build_current_profile(normalized, lookback_days),
        "",
        "## 近期事实",
        *_build_recent_facts(normalized, lookback_days),
        "",
        "## 经验归纳",
        *_build_lessons(normalized, lookback_days),
        "",
        "## 最近人工备注",
        *_build_operator_notes(normalized, lookback_days),
        "",
        "## 评估口径",
        *_build_evaluation_contract(),
        "",
        "## 待验证假设",
        *_build_hypotheses(normalized),
        "",
    ]
    return "\n".join(lines)


def curate_symbol_memory(symbol: str, lookback_days: int = 120) -> dict:
    normalized = normalize_symbol(symbol)
    file_path = _memory_file_path(normalized)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    content = build_symbol_memory_markdown(normalized, lookback_days=lookback_days)
    file_path.write_text(content, encoding="utf-8")
    return {
        "symbol": normalized,
        "path": str(file_path),
        "updated_at": datetime.now().isoformat(),
    }


def curate_symbol_memories(symbols=None, lookback_days: int = 120, limit: int = 50) -> list[dict]:
    normalized_symbols = []
    if symbols:
        if isinstance(symbols, str):
            symbols = [item.strip() for item in symbols.split(",") if item.strip()]
        normalized_symbols = [normalize_symbol(item) for item in symbols]
    else:
        query = (
            QuantDailyBar.select(QuantDailyBar.symbol)
            .group_by(QuantDailyBar.symbol)
            .order_by(QuantDailyBar.symbol.asc())
            .limit(limit)
        )
        normalized_symbols = [item.symbol for item in query.iterator()]

    results = []
    for symbol in normalized_symbols[:limit]:
        results.append(curate_symbol_memory(symbol, lookback_days=lookback_days))
    return results


def list_memory_files(limit: int = 200) -> list[dict]:
    root = _memory_root() / "symbols"
    if not root.exists():
        return []
    items = []
    for path in sorted(root.glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True)[:limit]:
        stat = path.stat()
        items.append(
            {
                "symbol": path.stem,
                "path": str(path),
                "updated_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "size": stat.st_size,
            }
        )
    return items


def read_symbol_memory(symbol: str) -> dict:
    file_path = _memory_file_path(symbol)
    if not file_path.exists():
        return {
            "symbol": normalize_symbol(symbol),
            "path": str(file_path),
            "content": "",
            "exists": False,
            "sections": {value: [] for value in MEMORY_SECTION_KEY_MAP.values()},
            "summary": {},
        }
    content = file_path.read_text(encoding="utf-8")
    sections = _parse_memory_sections(content)
    return {
        "symbol": normalize_symbol(symbol),
        "path": str(file_path),
        "content": content,
        "exists": True,
        "sections": sections,
        "summary": _build_memory_summary(content, sections),
    }


def extract_memory_snippets(symbols, max_items: int = 6) -> list[dict]:
    snippets = []
    seen = set()
    for raw_symbol in symbols or []:
        symbol = normalize_symbol(raw_symbol)
        if symbol in seen:
            continue
        seen.add(symbol)
        payload = read_symbol_memory(symbol)
        if not payload["content"]:
            continue
        sections = payload.get("sections") or {}
        lines = (
            sections.get("recent_facts", [])[:3]
            + sections.get("lessons", [])[:2]
            + sections.get("operator_notes", [])[:1]
        )
        if not lines:
            lines = [line for line in payload["content"].splitlines() if line.startswith("- ")]
        snippets.append(
            {
                "symbol": symbol,
                "path": payload["path"],
                "snippets": lines[:6],
            }
        )
        if len(snippets) >= max_items:
            break
    return snippets
