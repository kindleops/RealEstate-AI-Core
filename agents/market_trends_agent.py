"""Market Trends Agent for retrieving real estate market data by ZIP code.

This module defines :class:`MarketTrendsAgent` which can query Zillow or Redfin
style APIs for current market metrics, optionally cache the responses locally,
and fall back to user-provided static data if the live API is unavailable.

The agent favors asynchronous I/O for HTTP requests so that it can be plugged
into event-driven systems without blocking.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import aiohttp


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


@dataclass
class MarketTrendsAgent:
    """Agent responsible for fetching and caching market trend data.

    Parameters
    ----------
    provider: str
        The data provider to use. Supported values are ``"zillow"`` and
        ``"redfin"``. The choice determines which endpoint and environment
        variable is used for authentication.
    cache_path: Optional[Path]
        Where to persist cache data. If ``None``, caching is disabled.
    cache_ttl: timedelta
        How long cached data remains valid. Defaults to 24 hours.
    http_timeout: int
        Timeout (in seconds) for outbound HTTP requests.
    session_headers: Optional[Dict[str, str]]
        Extra headers to include on every request, useful for tracing.
    """

    provider: str = "zillow"
    cache_path: Optional[Path] = Path("data/market_trends_cache.json")
    cache_ttl: timedelta = timedelta(hours=24)
    http_timeout: int = 30
    session_headers: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.provider = self.provider.lower()
        if self.provider not in {"zillow", "redfin"}:
            raise ValueError("provider must be either 'zillow' or 'redfin'")

        # Initialize cache storage.
        self._cache: Dict[str, Dict[str, Any]] = {}
        if self.cache_path is not None:
            self._load_cache()

        # Fallback data storage, keyed by ZIP code.
        self._fallback_data: Dict[str, Dict[str, Any]] = {}

        logger.debug(
            "Initialized MarketTrendsAgent with provider=%s cache=%s", 
            self.provider,
            self.cache_path,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_trends(self, zip_code: str) -> Dict[str, Any]:
        """Synchronously fetch market trends for ``zip_code``.

        The method runs the asynchronous implementation in a dedicated event
        loop by calling :func:`asyncio.run`. Applications that already operate
        inside an event loop should directly call :meth:`get_trends_async` to
        avoid nested loop issues.
        """

        logger.debug("Fetching market trends synchronously for %s", zip_code)
        return asyncio.run(self.get_trends_async(zip_code))

    async def get_trends_async(self, zip_code: str) -> Dict[str, Any]:
        """Asynchronously fetch market trends for ``zip_code``.

        This method respects the configured cache and fallback data. It logs a
        concise summary of the resulting metrics and returns the parsed data as
        a dictionary.
        """

        zip_code = zip_code.strip()
        if not zip_code:
            raise ValueError("zip_code must be a non-empty string")

        logger.info("Requesting market trends for ZIP %s", zip_code)

        # 1. Attempt to return fresh cache data.
        cached = self._get_cached_value(zip_code)
        if cached is not None:
            logger.debug("Returning cached market trends for %s", zip_code)
            self._log_summary(zip_code, cached, source="cache")
            return cached

        # 2. Attempt to fetch from the remote API.
        try:
            data = await self._fetch_trends_from_api(zip_code)
        except Exception as exc:  # broad catch to enable fallback
            logger.warning(
                "Market API request failed for ZIP %s: %s", zip_code, exc,
                exc_info=logger.isEnabledFor(logging.DEBUG),
            )
            data = None

        if data is None:
            # 3. Fall back to static data if available.
            data = self._fallback_data.get(zip_code)
            if data is None:
                raise RuntimeError(
                    f"Unable to retrieve market trends for {zip_code} and no fallback data was set."
                )
            source = "fallback"
        else:
            source = "api"
            self._cache_value(zip_code, data)

        self._log_summary(zip_code, data, source=source)
        return data

    def set_fallback_data(self, zip_code: str, data: Dict[str, Any]) -> None:
        """Configure static fallback data for a ZIP code."""

        if not isinstance(data, dict):
            raise TypeError("Fallback data must be a dictionary")

        zip_code = zip_code.strip()
        if not zip_code:
            raise ValueError("zip_code must be a non-empty string")

        self._fallback_data[zip_code] = data
        logger.debug("Registered fallback data for ZIP %s", zip_code)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_provider_config(self) -> Dict[str, str]:
        """Return provider specific configuration such as URL and API key."""

        if self.provider == "zillow":
            return {
                "env_key": "ZILLOW_API_KEY",
                "endpoint": "https://api.zillow.com/v1/markets/{zip}/trends",
                "provider_name": "Zillow",
            }

        return {
            "env_key": "REDFIN_API_KEY",
            "endpoint": "https://api.redfin.com/v1/markets/{zip}/trends",
            "provider_name": "Redfin",
        }

    async def _fetch_trends_from_api(self, zip_code: str) -> Optional[Dict[str, Any]]:
        """Perform the HTTP request to fetch market trends.

        Returns ``None`` when the provider is unreachable or returns an error.
        ``aiohttp`` is used so that calling code can take advantage of asyncio.
        """

        config = self._get_provider_config()
        api_key = os.getenv(config["env_key"])
        if not api_key:
            logger.error(
                "%s API key environment variable %s is not set.",
                config["provider_name"],
                config["env_key"],
            )
            return None

        url = config["endpoint"].format(zip=zip_code)
        headers = {"Authorization": f"Bearer {api_key}", **self.session_headers}

        timeout = aiohttp.ClientTimeout(total=self.http_timeout)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            params = {"zip_code": zip_code}
            logger.debug("Issuing GET %s with params=%s", url, params)
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    text = await response.text()
                    logger.error(
                        "Market API returned status %s for %s: %s",
                        response.status,
                        zip_code,
                        text,
                    )
                    return None

                payload = await response.json()
                logger.debug("Market API response for %s: %s", zip_code, payload)
                return self._normalize_payload(payload)

    def _normalize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize provider specific payloads into a unified structure."""

        # Example structure. Adjust keys to match actual provider responses.
        metrics = payload.get("metrics", payload)
        normalized = {
            "median_sale_price": metrics.get("median_sale_price"),
            "price_per_sqft": metrics.get("price_per_sqft"),
            "days_on_market": metrics.get("days_on_market"),
            "inventory": metrics.get("inventory"),
            "last_updated": payload.get("last_updated") or datetime.utcnow().isoformat(),
            "provider": self.provider,
        }
        return {k: v for k, v in normalized.items() if v is not None}

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------
    def _load_cache(self) -> None:
        if self.cache_path is None:
            return

        try:
            if self.cache_path.exists():
                self._cache = json.loads(self.cache_path.read_text())
                logger.debug("Loaded market trends cache from %s", self.cache_path)
        except Exception as exc:
            logger.warning("Failed to load cache %s: %s", self.cache_path, exc)
            self._cache = {}

    def _save_cache(self) -> None:
        if self.cache_path is None:
            return

        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self._cache, indent=2, sort_keys=True))
            logger.debug("Persisted market trends cache to %s", self.cache_path)
        except Exception as exc:
            logger.warning("Failed to save cache %s: %s", self.cache_path, exc)

    def _get_cached_value(self, zip_code: str) -> Optional[Dict[str, Any]]:
        if self.cache_path is None:
            return None

        entry = self._cache.get(zip_code)
        if not entry:
            return None

        timestamp_str = entry.get("timestamp")
        if not timestamp_str:
            return None

        try:
            timestamp = datetime.fromisoformat(timestamp_str)
        except ValueError:
            logger.debug("Invalid timestamp in cache for %s", zip_code)
            return None

        if datetime.utcnow() - timestamp > self.cache_ttl:
            logger.debug("Cached data for %s expired", zip_code)
            return None

        return entry.get("data")

    def _cache_value(self, zip_code: str, data: Dict[str, Any]) -> None:
        if self.cache_path is None:
            return

        self._cache[zip_code] = {
            "timestamp": datetime.utcnow().isoformat(),
            "data": data,
        }
        self._save_cache()

    # ------------------------------------------------------------------
    # Logging helpers
    # ------------------------------------------------------------------
    def _log_summary(self, zip_code: str, data: Dict[str, Any], *, source: str) -> None:
        """Log and print a human readable summary of market metrics."""

        summary_parts = [
            f"ZIP: {zip_code}",
            f"Source: {source}",
        ]
        if "median_sale_price" in data:
            summary_parts.append(f"Median Price: ${data['median_sale_price']:,}")
        if "price_per_sqft" in data:
            summary_parts.append(f"Price/SqFt: ${data['price_per_sqft']:,}")
        if "days_on_market" in data:
            summary_parts.append(f"DOM: {data['days_on_market']}")

        summary = " | ".join(summary_parts)
        logger.info(summary)
        print(summary)


__all__ = ["MarketTrendsAgent"]
