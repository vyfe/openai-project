from quant_client.provider_eastmoney import EastmoneyAshareProvider
from quant_client.provider_sina import SinaAshareProvider
from quant_client.provider_akshare import AkshareAshareProvider
from quant_client.provider_base import BaseAshareProvider
from quant_client.provider_baostock import BaostockAshareProvider


# auto 模式下 provider 优先级（数字越小越优先）
_AUTO_CHAIN = [
    (0, EastmoneyAshareProvider),   # 字段最全（振幅、涨跌额、名称）
    (1, AkshareAshareProvider),     # 完整 OHLCV
    (2, BaostockAshareProvider),    # 完整 OHLCV
    (3, SinaAshareProvider),        # OHLCV（无成交额/换手率）
]


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
    "eastmoney": EastmoneyAshareProvider,
    "akshare": AkshareAshareProvider,
    "baostock": BaostockAshareProvider,
    "sina": SinaAshareProvider,
}


def get_provider(provider_name: str):
    provider_cls = PROVIDER_MAP.get((provider_name or "").strip().lower())
    if not provider_cls:
        raise ValueError(f"不支持的数据源: {provider_name}")
    return provider_cls()


def list_supported_providers():
    return sorted(PROVIDER_MAP.keys())
