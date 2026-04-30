from quant_client.provider_akshare import AkshareAshareProvider
from quant_client.provider_base import BaseAshareProvider
from quant_client.provider_baostock import BaostockAshareProvider


class AutoAshareProvider(BaseAshareProvider):
    provider_name = "auto"
    provider_version = "akshare_then_baostock"

    def fetch_daily_bars(self, symbols: list[str], start_date: str, end_date: str, adjust_flag: str = "qfq") -> list[dict]:
        errors = []
        for provider_cls in (AkshareAshareProvider, BaostockAshareProvider):
            provider = provider_cls()
            try:
                records = provider.fetch_daily_bars(symbols=symbols, start_date=start_date, end_date=end_date, adjust_flag=adjust_flag)
                if records:
                    return records
                errors.append(f"{provider.provider_name}: empty result")
            except Exception as exc:
                errors.append(f"{provider.provider_name}: {exc}")
        raise RuntimeError("auto provider 获取失败; " + " | ".join(errors))


PROVIDER_MAP = {
    "auto": AutoAshareProvider,
    "akshare": AkshareAshareProvider,
    "baostock": BaostockAshareProvider,
}


def get_provider(provider_name: str):
    provider_cls = PROVIDER_MAP.get((provider_name or "").strip().lower())
    if not provider_cls:
        raise ValueError(f"不支持的数据源: {provider_name}")
    return provider_cls()


def list_supported_providers():
    return sorted(PROVIDER_MAP.keys())

