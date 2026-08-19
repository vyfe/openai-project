import logging
import warnings

from quant_client.provider_akshare import AkshareAshareProvider
from quant_client.provider_sina import SinaAshareProvider
from quant_client.provider_base import BaseAshareProvider
from quant_client.provider_baostock import BaostockAshareProvider
from quant_client.provider_eastmoney import EastmoneyAshareProvider
from quant_client.provider_tencent import TencentAshareProvider
from quant_client.provider_yahoo import YfinanceAshareProvider

logger = logging.getLogger("quant.provider_factory")


# auto 模式下 provider 优先级（数字越小越优先）。
# 字段完整度排序（按 13 项核心字段的可填充数）：Baostock 9 > 腾讯 7 > 新浪 5。
# 主力三家是股票 K 线主力，但**对沪深主要指数的支持有限**（baostock/tencent/sina 对
# sh.000300 / sz.399001 等可能返回空），所以用 Yahoo Finance 兜底——
# Yahoo 是国际可访问数据源，**指数 + ETF 全覆盖**，且不易限流（无 API key 额度限制）。
#
# eastmoney / akshare 因**外网访问默认超时**已被弃用（见 _DEPRECATED_PROVIDERS 与备注），
# 仍可显式调用兼容旧任务/旧配置。
_AUTO_CHAIN = [
    (0, BaostockAshareProvider),    # 主力：字段最全（OHLCV + 成交额 + 换手率 + 涨跌幅 + 前收盘价）
    (1, TencentAshareProvider),     # 主力：OHLCV + 涨跌幅/前收盘价反算
    (2, SinaAshareProvider),        # 主力：仅 OHLCV
    (3, YfinanceAshareProvider),    # 兜底：指数 + ETF 国际可访问
]


# eastmoney / akshare 因外网访问默认超时（2026-08-19 验证），从 auto chain 移除。
# 仍可显式调用兼容旧任务/旧配置，但调用时会发 DeprecationWarning 提示用户迁移。
_DEPRECATED_PROVIDERS: set[str] = {"eastmoney", "akshare"}


class AutoAshareProvider(BaseAshareProvider):
    """按优先级聚合多数据源：高优先级覆盖低优先级，缺失的 symbol+日期 由下游补齐。

    合并策略：
    1. 从高到低依次请求各 provider
    2. 每个 record 以 (symbol, trade_date, adjust_flag) 为去重键
    3. 高优先级已覆盖的键，低优先级不再重复加入
    4. 最终返回一份聚合后的全量数据，source 字段保留实际来源
    """

    provider_name = "auto"
    provider_version = "merged_priority_chain"

    def fetch_daily_bars(self, symbols: list[str], start_date: str, end_date: str, adjust_flag: str = "qfq") -> list[dict]:
        merged: dict[tuple, dict] = {}  # key=(symbol, trade_date, adjust_flag) → record
        errors = []

        for priority, provider_cls in _AUTO_CHAIN:
            provider = provider_cls()
            try:
                records = provider.fetch_daily_bars(
                    symbols=symbols, start_date=start_date, end_date=end_date, adjust_flag=adjust_flag
                )
                added = 0
                for record in records:
                    # 只保留与请求复权类型匹配的记录（Sina 返回 raw，需 qfq 时会被过滤）
                    rec_adj = record.get("adjust_flag", adjust_flag)
                    if rec_adj != adjust_flag:
                        continue
                    key = (
                        record.get("symbol", ""),
                        record.get("trade_date", ""),
                        rec_adj,
                    )
                    if key not in merged:
                        merged[key] = record
                        added += 1
                if records:
                    errors.append(f"{provider.provider_name}: {len(records)}条, 新增{added}条")
                else:
                    errors.append(f"{provider.provider_name}: 空结果")
            except Exception as exc:
                errors.append(f"{provider.provider_name}: {exc}")

        if not merged:
            raise RuntimeError("auto provider 获取失败; " + " | ".join(errors))

        # 按 trade_date 排序
        result = sorted(merged.values(), key=lambda r: (r.get("symbol", ""), r.get("trade_date", "")))
        return result


PROVIDER_MAP = {
    "auto": AutoAshareProvider,
    "tencent": TencentAshareProvider,
    "sina": SinaAshareProvider,
    "baostock": BaostockAshareProvider,
    "yahoo": YfinanceAshareProvider,
    "eastmoney": EastmoneyAshareProvider,   # 已弃用：仅保留显式调用兼容
    "akshare": AkshareAshareProvider,        # 已弃用：仅保留显式调用兼容
}


def get_provider(provider_name: str):
    name = (provider_name or "").strip().lower()
    if name in _DEPRECATED_PROVIDERS:
        msg = (
            f"数据源 {provider_name!r} 已弃用（断网率高、限流频繁），"
            f"建议切换到 'tencent' / 'sina' / 'baostock' 或 'auto'。"
            f"本次仍按显式请求执行，请尽快调整。"
        )
        warnings.warn(msg, DeprecationWarning, stacklevel=2)
        logger.warning("deprecated provider in use: %s", provider_name)
    provider_cls = PROVIDER_MAP.get(name)
    if not provider_cls:
        raise ValueError(f"不支持的数据源: {provider_name}")
    return provider_cls()


def list_supported_providers():
    return sorted(PROVIDER_MAP.keys())
