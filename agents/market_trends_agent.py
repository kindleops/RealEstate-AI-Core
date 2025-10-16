"""Agent responsible for monitoring external market trends."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from statistics import mean
from typing import Dict, Iterable, List

import requests

from data.logger import StructuredLogger, get_logger


@dataclass
class MarketTrend:
    zipcode: str
    source: str
    price_index: float
    volume_change: float
    inventory_change: float

    @property
    def heat_score(self) -> float:
        return self.price_index * (1 + self.volume_change / 100.0) * (
            1 - self.inventory_change / 100.0
        )


class MarketTrendsAgent:
    """Aggregate market data from real estate data providers."""

    def __init__(self, logger: StructuredLogger | None = None) -> None:
        self.logger = logger or get_logger("market_trends")

    # ------------------------------------------------------------------
    # Public API
    def fetch_trends(self, zip_codes: Iterable[str]) -> List[MarketTrend]:
        results: List[MarketTrend] = []
        for source in ("zillow", "redfin", "realtor"):
            handler = getattr(self, f"_fetch_{source}_data")
            results.extend(handler(zip_codes))
        return results

    def detect_trending_zips(
        self, trends: Iterable[MarketTrend], *, top_n: int = 10
    ) -> List[Dict[str, float]]:
        aggregate: Dict[str, List[float]] = {}
        for trend in trends:
            aggregate.setdefault(trend.zipcode, []).append(trend.heat_score)
        scored = [
            {"zipcode": zipcode, "score": mean(scores)}
            for zipcode, scores in aggregate.items()
        ]
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:top_n]

    def log_trending_areas(self, trends: List[Dict[str, float]]) -> None:
        for item in trends:
            self.logger.log_event("market_trend", item)

    # ------------------------------------------------------------------
    # Provider integrations
    def _fetch_zillow_data(self, zip_codes: Iterable[str]) -> List[MarketTrend]:
        api_key = os.getenv("ZILLOW_API_KEY")
        if api_key:
            return list(self._call_external_api("zillow", zip_codes, api_key))
        return [self._simulate_trend(zip_code, "zillow") for zip_code in zip_codes]

    def _fetch_redfin_data(self, zip_codes: Iterable[str]) -> List[MarketTrend]:
        api_key = os.getenv("REDFIN_API_KEY")
        if api_key:
            return list(self._call_external_api("redfin", zip_codes, api_key))
        return [self._simulate_trend(zip_code, "redfin") for zip_code in zip_codes]

    def _fetch_realtor_data(self, zip_codes: Iterable[str]) -> List[MarketTrend]:
        api_key = os.getenv("REALTOR_API_KEY")
        if api_key:
            return list(self._call_external_api("realtor", zip_codes, api_key))
        return [self._simulate_trend(zip_code, "realtor") for zip_code in zip_codes]

    # ------------------------------------------------------------------
    def _call_external_api(
        self, source: str, zip_codes: Iterable[str], api_key: str
    ) -> Iterable[MarketTrend]:  # pragma: no cover - exercised in prod
        for zipcode in zip_codes:
            response = requests.get(
                f"https://api.{source}.com/market-trends",
                params={"zipcode": zipcode, "api_key": api_key},
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
            yield MarketTrend(
                zipcode=zipcode,
                source=source,
                price_index=payload.get("price_index", 100.0),
                volume_change=payload.get("volume_change", 0.0),
                inventory_change=payload.get("inventory_change", 0.0),
            )

    def _simulate_trend(self, zipcode: str, source: str) -> MarketTrend:
        digest = hashlib.sha256(f"{source}:{zipcode}".encode("utf-8")).hexdigest()
        bucket = int(digest[:8], 16)
        price_index = 80 + (bucket % 80)
        volume_change = (bucket % 20) - 5
        inventory_change = (bucket % 15) - 7
        return MarketTrend(
            zipcode=zipcode,
            source=source,
            price_index=float(price_index),
            volume_change=float(volume_change),
            inventory_change=float(inventory_change),
        )


__all__ = ["MarketTrendsAgent", "MarketTrend"]

