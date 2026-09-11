import json
from datetime import datetime, timedelta

from flask import Blueprint, request

from dto.common import error_response, get_request_data, parse_json_list, success_response
from quant.entities import QuantInstrument
from quant_client.bundle_builder import build_fetch_bundle
from service.quant.dashboard_service import get_dashboard_overview
from service.quant.import_service import fetch_import_batches, import_bundle, parse_bundle_bytes
from service.quant.indicator_service import (
    DEFAULT_INDICATOR_WINDOWS,
    INDICATOR_SET_VERSION,
    SUPPORTED_INDICATOR_GROUPS,
    compute_indicators,
    list_daily_indicators,
    max_lookback_bars,
)
from service.quant import indicator_registry as ireg
from service.quant.name_refresh_service import refresh_instrument_names
from service.quant.position_service import enqueue_position_backfill_task
from service.quant.provider_factory import list_supported_providers
from service.quant.query_service import fetch_daily_bars, fetch_minute_bars, fetch_weekly_bars
from service.quant.common import (
    infer_exchange,
    normalize_code,
    normalize_symbol,
    parse_trade_date,
    parse_trade_datetime,
)
from service.quant.symbol_search_service import search_symbols_fallback
from service.quant.instrument_display_service import (
    clear_custom_name as clear_instrument_custom_name,
    list_instruments_with_display_name,
    set_custom_name as set_instrument_custom_name,
)
from service.auth_service import require_admin_auth, require_auth


bp = Blueprint("quant_data_routes", __name__, url_prefix="/never_guess_my_usage/quant")


@bp.route("/dashboard/overview", methods=["GET"])
@require_auth
def quant_dashboard_overview(user, password):
    del user, password
    return success_response(data=get_dashboard_overview())


@bp.route("/providers", methods=["GET"])
@require_auth
def quant_providers(user, password):
    del user, password
    return success_response(data={"market": "A_SHARE", "providers": list_supported_providers()})


@bp.route("/data/import", methods=["POST"])
@require_admin_auth
def quant_data_import():
    try:
        if "bundle" in request.files:
            upload = request.files["bundle"]
            file_bytes = upload.read()
            bundle = parse_bundle_bytes(file_bytes)
            result = import_bundle(bundle, file_name=upload.filename or "", payload_bytes=file_bytes)
            return success_response(data=result, msg="导入成功")

        data = get_request_data()
        payload = data.get("bundle")
        if payload is None and isinstance(data, dict):
            payload = data
        if isinstance(payload, str):
            payload = json.loads(payload)
        if not isinstance(payload, dict):
            return error_response("缺少 bundle 数据")

        payload_bytes = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        result = import_bundle(payload, payload_bytes=payload_bytes)
        return success_response(data=result, msg="导入成功")
    except Exception as exc:
        return error_response(f"导入数据失败: {exc}")


@bp.route("/data/import_batches", methods=["GET"])
@require_admin_auth
def quant_import_batches():
    limit = request.args.get("limit", default=20, type=int) or 20
    limit = max(1, min(limit, 200))
    return success_response(data=fetch_import_batches(limit=limit))


@bp.route("/data/backfill", methods=["POST"])
@require_auth
def quant_data_backfill(user, password):
    del password
    try:
        data = get_request_data()
        symbols = parse_json_list(data.get("symbols"))
        if not symbols:
            raw_symbols = str(data.get("symbols_text", "")).strip()
            if raw_symbols:
                symbols = [item.strip() for item in raw_symbols.split(",") if item.strip()]
        all_active = _truthy(data.get("all_active"))
        if all_active and not symbols:
            symbols = _list_active_instrument_symbols()
        if not symbols:
            return error_response("symbols 不能为空（或勾选 all_active 从 quant_instrument 全表拉取）")

        result = enqueue_position_backfill_task(
            symbols=symbols,
            created_by=user,
            lookback_days=int(data.get("lookback_days", 730) or 730),
            provider=str(data.get("provider", "auto")).strip() or "auto",
            adjust_flag=str(data.get("adjust_flag", "qfq")).strip() or "qfq",
            lease_seconds=int(data.get("lease_seconds", 600) or 600),
            note=str(data.get("note", "")).strip(),
        )
        return success_response(data=result, msg="历史补数任务已创建")
    except Exception as exc:
        return error_response(f"创建历史补数任务失败: {exc}")


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return False
    return str(value).strip().lower() in ("true", "1", "yes", "on")


def _list_active_instrument_symbols() -> list[str]:
    """拉取 quant_instrument 中所有 status='active' 的 symbol。"""
    from quant.entities import QuantInstrument
    rows = (
        QuantInstrument.select(QuantInstrument.symbol)
        .where(QuantInstrument.status == "active")
    )
    return [r.symbol for r in rows.iterator()]


@bp.route("/symbols/upsert", methods=["POST"])
@require_admin_auth
def quant_symbol_upsert():
    try:
        data = get_request_data()
        raw_symbol = str(data.get("symbol") or data.get("code") or "").strip()
        if not raw_symbol:
            return error_response("symbol 不能为空")

        symbol = normalize_symbol(raw_symbol)
        code = normalize_code(symbol)
        exchange = str(data.get("exchange") or infer_exchange(symbol)).strip().upper()
        name = str(data.get("name") or "").strip()
        source = str(data.get("source") or "manual").strip() or "manual"
        now = datetime.now()
        payload = {
            "symbol": symbol,
            "code": code,
            "exchange": exchange,
            "market": "A_SHARE",
            "name": name,
            "source": source,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        QuantInstrument.insert(payload).on_conflict(
            conflict_target=[QuantInstrument.symbol],
            update={
                QuantInstrument.code: code,
                QuantInstrument.exchange: exchange,
                QuantInstrument.market: "A_SHARE",
                QuantInstrument.name: name,
                QuantInstrument.source: source,
                QuantInstrument.status: "active",
                QuantInstrument.updated_at: now,
            },
        ).execute()
        saved = QuantInstrument.get(QuantInstrument.symbol == symbol)
        # 返回 dict 同步带 custom_name + display_name，前端保存后无需再查一遍
        from service.quant.instrument_display_service import resolve_display_name
        saved_name = saved.name or ""
        saved_custom = saved.custom_name or ""
        return success_response(
            data={
                "symbol": saved.symbol,
                "code": saved.code,
                "exchange": saved.exchange,
                "market": saved.market,
                "name": saved_name,
                "custom_name": saved_custom,
                "display_name": resolve_display_name(saved.symbol, saved_custom, saved_name),
                "source": saved.source,
                "status": saved.status,
            },
            msg="股票池已更新",
        )
    except Exception as exc:
        return error_response(f"保存股票失败: {exc}")


@bp.route("/data/fetch_now", methods=["POST"])
@require_admin_auth
def quant_data_fetch_now():
    try:
        data = get_request_data()
        symbols = parse_json_list(data.get("symbols"))
        if not symbols:
            raw_symbols = str(data.get("symbols_text", "")).strip()
            if raw_symbols:
                symbols = [item.strip() for item in raw_symbols.split(",") if item.strip()]
        if _truthy(data.get("all_active")) and not symbols:
            symbols = _list_active_instrument_symbols()
        if not symbols:
            return error_response("symbols 不能为空（或勾选 all_active 从 quant_instrument 全表拉取）")

        start_date = str(data.get("start_date", "")).strip()
        end_date = str(data.get("end_date", "")).strip()
        if not start_date or not end_date:
            return error_response("start_date 和 end_date 不能为空")

        bundle = build_fetch_bundle(
            provider_name=str(data.get("provider", "auto")).strip() or "auto",
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            adjust_flag=str(data.get("adjust_flag", "qfq")).strip() or "qfq",
            frequency=str(data.get("frequency", "1d")).strip() or "1d",
            interval=str(data.get("interval", "5m")).strip() or "5m",
        )
        payload_bytes = json.dumps(bundle, ensure_ascii=False, sort_keys=True).encode("utf-8")
        result = import_bundle(bundle, payload_bytes=payload_bytes)
        return success_response(
            data={
                **result,
                "source": bundle.get("source"),
                "records_total": len(bundle.get("records") or []),
            },
            msg="手动拉数并导入成功",
        )
    except Exception as exc:
        return error_response(f"手动拉数失败: {exc}")


@bp.route("/data/daily_bars", methods=["GET"])
@require_auth
def quant_daily_bars(user, password):
    try:
        symbol = str(request.args.get("symbol", "")).strip()
        if not symbol:
            return error_response("symbol 不能为空")
        start_date = str(request.args.get("start_date", "")).strip() or None
        end_date = str(request.args.get("end_date", "")).strip() or None
        limit = request.args.get("limit", default=200, type=int) or 200
        limit = max(1, min(limit, 5000))
        include_deleted = _truthy(request.args.get("include_deleted"))
        return success_response(data=fetch_daily_bars(
            symbol=symbol, start_date=start_date, end_date=end_date,
            limit=limit, include_deleted=include_deleted,
        ))
    except Exception as exc:
        return error_response(f"查询日线失败: {exc}")


@bp.route("/data/weekly_bars", methods=["GET"])
@require_auth
def quant_weekly_bars(user, password):
    try:
        symbol = str(request.args.get("symbol", "")).strip()
        if not symbol:
            return error_response("symbol 不能为空")
        start_date = str(request.args.get("start_date", "")).strip() or None
        end_date = str(request.args.get("end_date", "")).strip() or None
        limit = request.args.get("limit", default=200, type=int) or 200
        limit = max(1, min(limit, 5000))
        include_deleted = _truthy(request.args.get("include_deleted"))
        return success_response(data=fetch_weekly_bars(
            symbol=symbol, start_date=start_date, end_date=end_date,
            limit=limit, include_deleted=include_deleted,
        ))
    except Exception as exc:
        return error_response(f"查询周线失败: {exc}")


@bp.route("/data/minute_bars", methods=["GET"])
@require_auth
def quant_minute_bars(user, password):
    try:
        symbol = str(request.args.get("symbol", "")).strip()
        if not symbol:
            return error_response("symbol 不能为空")
        interval = str(request.args.get("interval", "5m")).strip() or "5m"
        start_dt = str(request.args.get("start_datetime", "")).strip() or None
        end_dt = str(request.args.get("end_datetime", "")).strip() or None
        limit = request.args.get("limit", default=480, type=int) or 480
        adjust_flag = str(request.args.get("adjust_flag", "qfq")).strip() or "qfq"
        include_deleted = _truthy(request.args.get("include_deleted"))
        return success_response(
            data=fetch_minute_bars(
                symbol=symbol,
                interval=interval,
                start_dt=start_dt,
                end_dt=end_dt,
                limit=limit,
                adjust_flag=adjust_flag,
                include_deleted=include_deleted,
            )
        )
    except Exception as exc:
        return error_response(f"查询分时失败: {exc}")


@bp.route("/symbols/refresh_names", methods=["POST"])
@require_admin_auth
def quant_symbols_refresh_names():
    """批量回填 quant_instrument.name（走腾讯 qt.gtimg.cn metadata 端点）。"""
    try:
        data = get_request_data() if request.method == "POST" else {}
        only_empty = str(data.get("only_empty", True)).strip().lower() in ("true", "1", "yes", "on")
        batch_size = int(data.get("batch_size", 60) or 60)
        batch_size = max(10, min(batch_size, 200))
        result = refresh_instrument_names(only_empty=only_empty, batch_size=batch_size)
        return success_response(data=result, msg=f"扫描 {result['scanned']} 条，更新 {result['updated']} 条")
    except Exception as exc:
        return error_response(f"刷新股票名称失败: {exc}")


@bp.route("/instruments", methods=["GET"])
@require_auth
def quant_instruments_list(user, password):
    """列出量化标的（带显示名），供前端"数据中心股票池"管理 UI 用。

    query params:
    - keyword: 模糊匹配 symbol/code/name/custom_name
    - exchange: SH/SZ/BJ
    - only_with_custom: true/false，是否只列出自定义名非空的
    - limit: 1..500，默认 200
    """
    del password
    try:
        keyword = str(request.args.get("keyword") or "").strip()
        exchange = str(request.args.get("exchange") or "").strip().upper()
        only_with_custom = str(request.args.get("only_with_custom") or "").strip().lower() in ("true", "1", "yes", "on")
        try:
            limit = int(request.args.get("limit") or 200)
        except (TypeError, ValueError):
            limit = 200
        limit = max(1, min(limit, 500))
        items = list_instruments_with_display_name(
            keyword=keyword,
            exchange=exchange,
            only_with_custom=only_with_custom,
            limit=limit,
        )
        return success_response(data={"items": items, "count": len(items)}, msg="OK")
    except Exception as exc:
        return error_response(f"查询股票池失败: {exc}")


@bp.route("/instruments/custom_name", methods=["POST"])
@require_admin_auth
def quant_instrument_set_custom_name():
    """设置 / 覆盖 / 清空（custom_name 传空串）单个标的的自定义显示名。"""
    try:
        data = get_request_data() or {}
        symbol = str(data.get("symbol") or "").strip()
        if not symbol:
            return error_response("symbol 不能为空")
        custom_name = data.get("custom_name")
        if custom_name is not None:
            custom_name = str(custom_name).strip()
        result = set_instrument_custom_name(symbol, custom_name)
        return success_response(data=result, msg="已更新自定义显示名")
    except ValueError as exc:
        return error_response(str(exc))
    except Exception as exc:
        return error_response(f"更新自定义显示名失败: {exc}")


@bp.route("/instruments/custom_name/clear", methods=["POST"])
@require_admin_auth
def quant_instrument_clear_custom_name():
    """清空单个标的的 custom_name（恢复使用 name）。"""
    try:
        data = get_request_data() or {}
        symbol = str(data.get("symbol") or "").strip()
        if not symbol:
            return error_response("symbol 不能为空")
        result = clear_instrument_custom_name(symbol)
        return success_response(data=result, msg="已重置为官方名称")
    except ValueError as exc:
        return error_response(str(exc))
    except Exception as exc:
        return error_response(f"清除自定义显示名失败: {exc}")


_MAX_COMPUTE_BARS = 5000
_VALID_BAR_FIELDS = {"trade_date", "open_price", "high_price", "low_price", "close_price", "volume", "amount"}


def _normalize_bar_input(raw: dict, idx: int) -> dict:
    out: dict = {}
    if not isinstance(raw, dict):
        raise ValueError(f"bars[{idx}] 必须是对象")
    trade_date = raw.get("trade_datetime") or raw.get("trade_date") or raw.get("date")
    if not trade_date:
        raise ValueError(f"bars[{idx}].trade_date 不能为空")
    out["trade_date"] = str(trade_date)
    for field in ("open_price", "high_price", "low_price", "close_price"):
        value = raw.get(field)
        if value is None:
            continue
        out[field] = float(value)
    for field in ("volume", "amount"):
        value = raw.get(field)
        if value is None:
            continue
        out[field] = float(value)
    return out


class _Bar:
    """鸭子类型 bar：支持 indicator_service 用 getattr 取字段。"""

    __slots__ = ("trade_date", "open_price", "high_price", "low_price", "close_price", "volume", "amount")

    def __init__(self, payload: dict):
        # 分钟 K 线用 trade_datetime 区分同一交易日的不同 bar；日线/周线只有 trade_date
        self.trade_date = payload.get("trade_datetime") or payload["trade_date"]
        self.open_price = payload.get("open_price")
        self.high_price = payload.get("high_price")
        self.low_price = payload.get("low_price")
        self.close_price = payload.get("close_price")
        self.volume = payload.get("volume")
        self.amount = payload.get("amount")


@bp.route("/data/indicators/compute", methods=["POST"])
@require_auth
def quant_indicators_compute(user, password):
    """无状态指标计算。

    支持两种请求形态：
    1. 新形态（推荐）：{symbol, start_date, end_date, interval, indicator_names, params}
       后端根据 indicator_names 算 lookback，自动往前多拉数据；返回结果 trim 到请求区间。
    2. 旧形态（向后兼容）：{bars, indicator_names, params}，调用方自行提供 bars。
    """
    del user, password
    try:
        data = get_request_data() or {}
        if not isinstance(data, dict):
            return error_response("请求体必须是 JSON 对象")

        # 新形态：symbol + 日期区间
        if data.get("symbol") and data.get("start_date") and data.get("end_date"):
            return _compute_indicators_by_range(data)
        # 旧形态：bars 直传
        if isinstance(data.get("bars"), list):
            return _compute_indicators_from_bars(data)
        return error_response("请求体必须包含 bars（旧形态）或 symbol+start_date+end_date（新形态）")
    except ValueError as exc:
        return error_response(f"参数错误: {exc}")
    except Exception as exc:
        return error_response(f"计算指标失败: {exc}")


def _concrete_output_names() -> set[str]:
    """registry 派生：用默认参数把模板输出名展开成具体名（如 ma_{window} → ma_5/ma_10/...）。

    新指标的真实 key 一律经此路径，禁删。
    """
    names: set[str] = set()
    for spec in ireg.INDICATOR_REGISTRY.values():
        for out in spec.outputs:
            if "{" not in out.name:
                names.add(out.name)
                continue
            # 模板输出：用 spec.params 的 int / int_list 类型的 default 展开。
            # 通用规则（不再硬编码 key 列表）：
            # 1. 输出模板里出现 "{window}" 时，按 params 里 name=="window" 的 default 展开
            # 2. 否则按 params[0].default 展开
            template = out.name
            target_param = None
            for p in spec.params:
                if p.name == "window":
                    target_param = p
                    break
            if target_param is None and spec.params:
                target_param = spec.params[0]
            if target_param is None:
                continue
            if target_param.type == "int_list" and isinstance(target_param.default, list):
                for v in target_param.default:
                    names.add(template.replace("{window}", str(v)))
            elif target_param.type == "int":
                names.add(template.replace("{window}", str(target_param.default)))
            else:
                # 模板存在但没有 int 默认值，跳过（旧逻辑会静默丢）
                continue
    return names


_INDICATOR_FIELD_NAMES = _concrete_output_names()


def _validate_indicator_names(indicator_names):
    if indicator_names is None:
        return
    if not isinstance(indicator_names, list):
        raise ValueError("indicator_names 必须是数组")
    valid = {g.lower() for g in SUPPORTED_INDICATOR_GROUPS} | {f.lower() for f in _INDICATOR_FIELD_NAMES}
    unknown = [n for n in indicator_names if str(n).lower() not in valid]
    if unknown:
        raise ValueError(f"不支持的 indicator_name: {unknown}")


def _compute_indicators_from_bars(data):
    raw_bars = data.get("bars") or []
    if not raw_bars:
        raise ValueError("bars 不能为空")
    if len(raw_bars) > _MAX_COMPUTE_BARS:
        raise ValueError(f"bars 长度 {len(raw_bars)} 超过上限 {_MAX_COMPUTE_BARS}")
    bars = [_Bar(_normalize_bar_input(item, idx)) for idx, item in enumerate(raw_bars)]
    indicator_names = data.get("indicator_names")
    _validate_indicator_names(indicator_names)
    params = data.get("params") if isinstance(data.get("params"), dict) else None
    results = compute_indicators(bars, indicator_names=indicator_names, params=params)
    return success_response(
        data={
            "results": results,
            "meta": {
                "bars_count": len(bars),
                "warmup_count": 0,
                "indicator_version": INDICATOR_SET_VERSION,
                "computed_at": datetime.now().isoformat(),
            },
        },
        msg=f"已计算 {len(bars)} 根 K 线的指标",
    )


def _compute_indicators_by_range(data):
    symbol = str(data.get("symbol") or "").strip()
    start_date = str(data.get("start_date") or "").strip()
    end_date = str(data.get("end_date") or "").strip()
    interval = str(data.get("interval") or "daily").strip().lower()
    adjust_flag = str(data.get("adjust_flag") or "qfq").strip() or "qfq"

    if not symbol or not start_date or not end_date:
        raise ValueError("symbol/start_date/end_date 均不能为空")
    if interval not in ("daily", "weekly", "minute"):
        raise ValueError("interval 必须是 daily / weekly / minute")

    indicator_names = data.get("indicator_names")
    _validate_indicator_names(indicator_names)
    params = data.get("params") if isinstance(data.get("params"), dict) else None

    lookback = max_lookback_bars(indicator_names, params)

    if interval == "daily":
        # A 股一周 5 个交易日：lookback 根 K 线 ≈ lookback * 7/5 个日历天，
        # 再 +14 天 buffer 覆盖长假。直接拿 lookback 当日历天会少拉约 1/3 的交易日，
        # 导致请求区间最前面 MA60 等长窗口指标大面积为 null。
        daily_lookback_days = (lookback * 7) // 5 + 14
        extended_start = (parse_trade_date(start_date) - timedelta(days=daily_lookback_days)).strftime("%Y-%m-%d")
        raw = fetch_daily_bars(
            symbol=symbol,
            start_date=extended_start,
            end_date=end_date,
            limit=max(lookback * 2 + 200, 500),
        )
    elif interval == "weekly":
        extended_start = (parse_trade_date(start_date) - timedelta(days=lookback * 7)).strftime("%Y-%m-%d")
        raw = fetch_weekly_bars(
            symbol=symbol,
            start_date=extended_start,
            end_date=end_date,
            limit=max(lookback * 2 + 50, 200),
        )
    else:  # minute
        start_dt_str = str(data.get("start_datetime") or f"{start_date} 00:00:00").strip()
        end_dt_str = str(data.get("end_datetime") or f"{end_date} 23:59:59").strip()
        # 分时 K 线在 A 股有 90 分钟午休断点 + 隔夜隔日，不能按 minutes 连续偏移。
        # 改为按"日历天数"往前推：A 股每个交易日 ~48 根 5m（上午 24 + 下午 24），
        # ceil(lookback/48) 天 + 2 天 buffer（应对假期/半日市/夜盘）。
        lookback_days = max(2, (lookback // 48) + 2)
        fetch_start_dt = (parse_trade_datetime(start_dt_str) - timedelta(days=lookback_days)).strftime("%Y-%m-%d %H:%M:%S")
        raw = fetch_minute_bars(
            symbol=symbol,
            interval="5m",
            start_dt=fetch_start_dt,
            end_dt=end_dt_str,
            limit=max(lookback * 3 + 200, 800),
            adjust_flag=adjust_flag,
        )

    bars = [_Bar(item) for item in raw]
    results = compute_indicators(bars, indicator_names=indicator_names, params=params)
    # 分时 bar 的 key 是 datetime 串（bar.trade_datetime 来自 DB isoformat，用 T 分隔），
    # 但前端传来的 start_datetime/end_datetime 用空格分隔；
    # 字符串比较时 "T"(0x54) > " "(0x20)，会错误剔除 end_date 当天的所有 bar。
    # 统一转成 datetime 对象比较更稳。
    if interval == "minute":
        cmp_start_str = data.get("start_datetime") or f"{start_date} 00:00:00"
        cmp_end_str = data.get("end_datetime") or f"{end_date} 23:59:59"
        cmp_start_dt = datetime.fromisoformat(cmp_start_str.replace(" ", "T"))
        cmp_end_dt = datetime.fromisoformat(cmp_end_str.replace(" ", "T"))
        filtered = {}
        for d, row in results.items():
            try:
                dt = datetime.fromisoformat(d.replace(" ", "T"))
            except ValueError:
                continue
            if cmp_start_dt <= dt <= cmp_end_dt:
                filtered[d] = row
    else:
        filtered = {
            d: row for d, row in results.items()
            if start_date <= d <= end_date
        }
    warmup_count = max(0, len(bars) - len(filtered))
    return success_response(
        data={
            "results": filtered,
            "meta": {
                "bars_count": len(bars),
                "warmup_count": warmup_count,
                "interval": interval,
                "indicator_version": INDICATOR_SET_VERSION,
                "computed_at": datetime.now().isoformat(),
            },
        },
        msg=f"指标计算完成，预热 {warmup_count} 根",
    )


@bp.route("/data/indicators", methods=["GET"])
@require_auth
def quant_indicators_list(user, password):
    """持久层读取：按 symbol + 可选 names + 日期范围返回 QuantDailyIndicator 记录。"""
    del user, password
    try:
        symbol = str(request.args.get("symbol", "")).strip()
        if not symbol:
            return error_response("symbol 不能为空")
        symbol = normalize_symbol(symbol)
        names_param = str(request.args.get("names", "")).strip()
        names_list: list[str] = []
        if names_param:
            names_list = [item.strip() for item in names_param.split(",") if item.strip()]
        start_date = str(request.args.get("start_date", "")).strip() or None
        end_date = str(request.args.get("end_date", "")).strip() or None
        adjust_flag = str(request.args.get("adjust_flag", "qfq")).strip() or "qfq"
        indicator_version = str(request.args.get("indicator_version", "")).strip() or None
        limit = request.args.get("limit", default=1000, type=int) or 1000
        limit = max(1, min(limit, 5000))

        rows: list[dict] = []
        if names_list:
            for name in names_list:
                rows.extend(
                    list_daily_indicators(
                        symbol=symbol,
                        trade_date=None,
                        indicator_name=name,
                        limit=limit,
                        indicator_version=indicator_version,
                    )
                )
        else:
            rows = list_daily_indicators(
                symbol=symbol,
                trade_date=None,
                indicator_name=None,
                limit=limit,
                indicator_version=indicator_version,
            )

        if start_date or end_date:
            filtered = []
            for row in rows:
                trade_date = row.get("trade_date")
                if not trade_date:
                    continue
                if start_date and str(trade_date) < start_date:
                    continue
                if end_date and str(trade_date) > end_date:
                    continue
                filtered.append(row)
            rows = filtered

        if adjust_flag:
            rows = [row for row in rows if row.get("adjust_flag") == adjust_flag]

        return success_response(
            data={"items": rows, "total": len(rows), "limit": limit, "indicator_version": indicator_version or INDICATOR_SET_VERSION},
            msg=f"返回 {len(rows)} 条指标记录",
        )
    except Exception as exc:
        return error_response(f"查询指标失败: {exc}")
