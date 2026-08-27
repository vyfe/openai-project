from __future__ import annotations

from abc import ABC, abstractmethod


class BaseAshareProvider(ABC):
    provider_name = ""
    provider_version = ""

    @abstractmethod
    def fetch_daily_bars(self, symbols: list[str], start_date: str, end_date: str, adjust_flag: str = "qfq") -> list[dict]:
        raise NotImplementedError

    def fetch_minute_bars(
        self,
        symbols: list[str],
        interval: str,
        start_dt: str,
        end_dt: str,
        adjust_flag: str = "qfq",
    ) -> list[dict]:
        """拉取分时 K 线（如 5m/15m/30m）。

        各 provider 按需覆盖；未实现的 provider 抛 NotImplementedError，factory 在
        入口处用 hasattr 检查防止误用——避免跨语义 auto-chain 降级（参考项目记忆
        `quant-auto-chain-seed-based`）。
        """
        raise NotImplementedError(
            f"{self.provider_name or self.__class__.__name__} 不支持分时 K 线"
        )

