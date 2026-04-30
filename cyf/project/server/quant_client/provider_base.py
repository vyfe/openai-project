from __future__ import annotations

from abc import ABC, abstractmethod


class BaseAshareProvider(ABC):
    provider_name = ""
    provider_version = ""

    @abstractmethod
    def fetch_daily_bars(self, symbols: list[str], start_date: str, end_date: str, adjust_flag: str = "qfq") -> list[dict]:
        raise NotImplementedError

