<<<<<<< HEAD
"""Agent that scores Airtable property records using a local Ollama model."""
=======
"""Lead scoring agent for evaluating real estate opportunities.

This module exposes a FastAPI router that accepts a property identifier
(APN) and returns a score along with a qualitative assessment of the lead.

The implementation intentionally stubs out external dependencies such as
Airtable and market data providers so the module can be exercised in
isolation. These stubs are written in a way that makes it straightforward
to replace them with real integrations.
"""
from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "weights.json"


class ScoreWeights(BaseModel):
    """Container for dynamic scoring weights and thresholds."""

    weights: Dict[str, int]
    thresholds: Dict[str, float]


@lru_cache(maxsize=1)
def load_weight_config() -> ScoreWeights:
    """Load scoring configuration from the shared JSON file.

    The configuration is cached because the file rarely changes at runtime
    and parsing it repeatedly would be unnecessary work.
    """

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            "Expected scoring configuration at config/weights.json. "
            "Create the file or adjust CONFIG_PATH."
        )

    data = json.loads(CONFIG_PATH.read_text())
    return ScoreWeights(**data)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ScoreRequest(BaseModel):
    """Incoming payload for the scoring endpoint."""

    apn: str = Field(..., description="Assessor parcel number for the property")
    override_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Optional dictionary to override mocked data when testing or "
            "integrating with real services."
        ),
    )
    use_live_data: bool = Field(
        default=False,
        description="Toggle to enable live integrations once implemented.",
    )


class ScoreResponse(BaseModel):
    """Structured response for the lead score."""

    score: int
    tags: List[str]
    reasoning: List[str]
    recommendation: str
    metadata: Dict[str, Any]


# ---------------------------------------------------------------------------
# Mocked data providers (replace with real integrations as needed)
# ---------------------------------------------------------------------------


async def fetch_property_data(apn: str, overrides: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Stub that emulates pulling property data from Airtable.

    A real implementation would authenticate against Airtable and pull
    the record matching the APN. The structure returned here contains the
    metrics needed for scoring and can be overridden via the request for
    deterministic testing.
    """

    # Example baseline data. Replace with Airtable query results.
    property_data: Dict[str, Any] = {
        "apn": apn,
        "zip_code": "33147",
        "owner_type": "Absentee",
        "year_built": 1975,
        "equity_percent": 0.52,
        "last_sale_date": "2019-03-11",
        "is_vacant": True,
        "absentee_owner": True,
        "estimated_arv": 365000,
        "estimated_repair_cost": 82000,
        "estimated_purchase_price": 210000,
    }

    if overrides:
        property_data.update(overrides)

    return property_data


async def fetch_market_insights(zip_code: str, use_live_data: bool) -> Dict[str, Any]:
    """Stub to emulate pulling market insights from search or MLS APIs."""

    # Placeholder logic. Swap with Zillow/Redfin integrations when ready.
    return {
        "zip_code": zip_code,
        "median_days_on_market": 27,
        "price_trend": "appreciating",
        "average_flip_roi": 0.19,
        "recent_sales_24mo": 2,
    }


async def fetch_cash_buyer_activity(zip_code: str, use_live_data: bool) -> Dict[str, Any]:
    """Stub to emulate cash buyer analytics for the zip code."""

    return {
        "zip_code": zip_code,
        "recent_cash_sales_90d": 18,
        "flips_last_12mo": 22,
        "active_rentals": 34,
    }


# ---------------------------------------------------------------------------
# Scoring logic
# ---------------------------------------------------------------------------


def parse_date(date_value: Optional[str]) -> Optional[datetime]:
    if not date_value:
        return None
    try:
        return datetime.fromisoformat(date_value)
    except ValueError:
        return None


def months_between(start: datetime, end: datetime) -> float:
    """Approximate number of months between two datetimes."""

    return (end - start).days / 30.44


def evaluate_metrics(
    property_data: Dict[str, Any],
    market_insights: Dict[str, Any],
    cash_activity: Dict[str, Any],
    config: ScoreWeights,
) -> Dict[str, Any]:
    """Apply scoring rules and derive tags / reasoning."""

    weights = config.weights
    thresholds = config.thresholds

    score = 0
    tags: List[str] = []
    reasoning: List[str] = []

    # 1. Property has not sold within the last 24 months.
    last_sale_date = parse_date(property_data.get("last_sale_date"))
    sold_recently = False
    if last_sale_date is None:
        score += weights.get("not_sold_24_months", 0)
        reasoning.append("No recorded sale in past 24 months")
    else:
        delta_months = months_between(last_sale_date, datetime.utcnow())
        sold_recently = delta_months <= thresholds.get("recent_sale_months", 24)
        if not sold_recently:
            score += weights.get("not_sold_24_months", 0)
            reasoning.append("No sale in 24 months")

    # 2. High equity check.
    equity_percent = property_data.get("equity_percent") or 0
    if equity_percent >= thresholds.get("equity_percent", 0.4):
        score += weights.get("high_equity", 0)
        tags.append("High Equity")
        reasoning.append(f"High equity ({equity_percent:.0%})")

    # 3. Cash buyer activity (recent cash sales).
    cash_sales = cash_activity.get("recent_cash_sales_90d", 0)
    if cash_sales >= thresholds.get("cash_sales_minimum", 15):
        score += weights.get("cash_sales", 0)
        tags.append("Cash Buyer Hotspot")
        reasoning.append(
            f"ZIP {cash_activity['zip_code']} has {cash_sales} cash sales in last 90 days"
        )

    # 4. Vacancy.
    if property_data.get("is_vacant"):
        score += weights.get("vacant", 0)
        tags.append("Vacant")
        reasoning.append("Property flagged as vacant")

    # 5. Absentee owner.
    if property_data.get("absentee_owner") or (
        isinstance(property_data.get("owner_type"), str)
        and property_data.get("owner_type", "").lower() == "absentee"
    ):
        score += weights.get("absentee_owner", 0)
        tags.append("Absentee Owner")
        reasoning.append("Absentee ownership")

    # 6. Flip activity in the area.
    flips = cash_activity.get("flips_last_12mo", 0)
    if flips >= thresholds.get("flip_activity_minimum", 15):
        score += weights.get("flip_activity", 0)
        tags.append("Flip Zone")
        reasoning.append(
            f"ZIP {cash_activity['zip_code']} shows {flips} flips in last 12 months"
        )

    # 7. Margin analysis (ARV vs repair costs).
    arv = property_data.get("estimated_arv") or 0
    repair_cost = property_data.get("estimated_repair_cost") or 0
    purchase_price = property_data.get("estimated_purchase_price") or 0
    if arv > 0 and purchase_price > 0:
        net_value = arv - repair_cost - purchase_price
        margin_ratio = net_value / arv if arv else 0
        if margin_ratio >= thresholds.get("margin_ratio", 0.3):
            score += weights.get("margin", 0)
            tags.append("Strong Margin")
            reasoning.append(
                f"Projected margin {margin_ratio:.0%} after repairs"
            )

    # Clamp score to 0-100 range just in case weight tuning exceeds bounds.
    score = max(0, min(100, score))

    # Recommendation tiering.
    if score >= thresholds.get("high_priority_cutoff", 70):
        recommendation = (
            "High-priority lead for outreach. Strong flip zone with recent cash "
            "activity and margin potential."
        )
    elif score >= thresholds.get("medium_priority_cutoff", 40):
        recommendation = "Moderate priority. Validate rehab budget and timeline."
    else:
        recommendation = "Low priority at this time. Monitor for future activity."

    return {
        "score": int(round(score)),
        "tags": sorted(set(tags)),
        "reasoning": reasoning,
        "recommendation": recommendation,
    }


# ---------------------------------------------------------------------------
# FastAPI router
# ---------------------------------------------------------------------------


router = APIRouter(prefix="/score", tags=["score"])


@router.post("/", response_model=ScoreResponse)
async def score_lead(request: ScoreRequest) -> ScoreResponse:
    """Entry point for scoring leads via HTTP."""

    try:
        config = load_weight_config()
    except FileNotFoundError as exc:  # pragma: no cover - configuration error
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    property_data = await fetch_property_data(request.apn, request.override_data)
    if not property_data:
        raise HTTPException(status_code=404, detail="Property data not found")

    market_insights = await fetch_market_insights(
        property_data.get("zip_code", ""), request.use_live_data
    )
    cash_activity = await fetch_cash_buyer_activity(
        property_data.get("zip_code", ""), request.use_live_data
    )

    evaluation = evaluate_metrics(property_data, market_insights, cash_activity, config)

    response_payload = {
        **evaluation,
        "metadata": {
            "property": property_data,
            "market_insights": market_insights,
            "cash_buyer_activity": cash_activity,
        },
    }

    return ScoreResponse(**response_payload)


__all__ = ["router", "score_lead", "evaluate_metrics"]
"""Agent that scores property records based on configurable weights."""
>>>>>>> 03fa71e26e95e4a858304c460a4c5009a6a397d2
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

import requests

from data.airtable_client import get_properties, update_property
from data.logger import append_score_log
from logger import get_logger

LOGGER = get_logger()

PROMPT_TEMPLATE = (
    "You are an AI analyst for a wholesale real estate company.\n"
    "Evaluate the following property based on its potential motivation and distress level for a quick cash sale.\n\n"
    "Analyze:\n"
    "- Property details (year built, beds, baths, sqft, type, location)\n"
    "- Ownership and situation (vacant, absentee, inherited, tax delinquent, preforeclosure)\n"
    "- Market context (recent sales, price trends, demand in ZIP)\n"
    "- Visible distress indicators (repairs needed, liens, age of home, long ownership)\n"
    "- Online listings and sale history from Zillow, Realtor, Propwire, and general market knowledge\n\n"
    "Scoring rules:\n"
    "1. If sold within the last 24 months → score = 0\n"
    "2. Otherwise, assign a score 1–100 (90–100 = very motivated, 70–89 = likely motivated, "
    "40–69 = mild, 1–39 = low)\n"
    "Return only the numeric score, nothing else.\n\n"
    "Property data:\n"
    "{property_data}\n"
)


@dataclass(slots=True)
class ScoreAgentConfig:
    """Runtime options for the score agent."""

    table_name: str = "Properties"
    target_field: str = "Motivation Score"
    model: str = "mistral:7b"
    ollama_url: str = "http://localhost:11434/api/generate"
    request_timeout: int = 120
    key_fields: Sequence[str] = (
        "Address",
        "City",
        "State",
        "Zip",
        "Year Built",
        "Beds",
        "Baths",
        "Square Feet",
        "Lot Size",
        "Property Type",
        "Vacancy",
        "Owner Type",
        "Ownership Length",
        "Preforeclosure",
        "Tax Delinquent",
        "Liens",
        "Auction Date",
        "Last Sold Date",
        "Last Sale Price",
    )
    sale_date_fields: Sequence[str] = ("Last Sold Date", "Last Sale Date", "last_sold_date")
    max_records: Optional[int] = None


@dataclass(slots=True)
class ScoreResult:
    """Outcome of processing a single Airtable record."""

    record_id: str
    score: Optional[int]
    status: str
    error: Optional[str] = None


class ScoreAgent:
    """Fetch property records, score them with an LLM, and persist results."""

    def __init__(
        self,
        config: ScoreAgentConfig | None = None,
        fetch_records: Callable[[str], Iterable[Dict[str, Any]]] = get_properties,
        update_record: Callable[[str, Dict[str, Any], str], Dict[str, Any]] = update_property,
    ) -> None:
        self.config = config or ScoreAgentConfig()
        self._fetch_records = fetch_records
        self._update_record = update_record

    def score_all(self, limit: int | None = None) -> List[ScoreResult]:
        """Process all properties sequentially and return per-record results."""
        effective_limit = limit if limit is not None else self.config.max_records
        results: List[ScoreResult] = []
        for index, record in enumerate(self._iter_records(), start=1):
            if effective_limit is not None and index > effective_limit:
                break
            result = self._process_record(record)
            results.append(result)
        LOGGER.info("ScoreAgent completed %s records", len(results))
        return results

    def _iter_records(self) -> Iterable[Dict[str, Any]]:
        try:
            records = list(self._fetch_records(self.config.table_name))
        except TypeError:
            # Backwards compatibility for helper without table argument.
            records = list(self._fetch_records())  # type: ignore[arg-type]
        if not records:
            LOGGER.warning("No properties returned from Airtable table %s", self.config.table_name)
        return records

    def _process_record(self, record: Dict[str, Any]) -> ScoreResult:
        record_id = record.get("id") or ""
        fields: Dict[str, Any] = record.get("fields", {})
        if not record_id:
            LOGGER.error("Skipping record missing Airtable id: %s", record)
            return ScoreResult(record_id="", score=None, status="skipped", error="missing_record_id")

        try:
            if self._sold_within_24_months(fields):
                score = 0
                LOGGER.info("Property %s sold within 24 months; forcing score 0", record_id)
            else:
                prompt = self._build_prompt(fields)
                score = self._invoke_model(prompt)
            self._persist_score(record_id, score)
            message = f"score={score}"
            LOGGER.info("Updated Airtable record %s with %s", record_id, message)
            append_score_log(record_id=record_id, score=score, payload=fields, status="success")
            return ScoreResult(record_id=record_id, score=score, status="success")
        except Exception as exc:
            error_text = str(exc)
            LOGGER.exception("Failed to score record %s: %s", record_id, error_text)
            append_score_log(record_id=record_id, score=None, payload=fields, status="error", error=error_text)
            return ScoreResult(record_id=record_id, score=None, status="error", error=error_text)

    def _build_prompt(self, fields: Dict[str, Any]) -> str:
        property_data = self._format_fields(fields)
        return PROMPT_TEMPLATE.format(property_data=property_data)

    def _invoke_model(self, prompt: str) -> int:
        payload = {"model": self.config.model, "prompt": prompt, "stream": False}
        response = requests.post(
            self.config.ollama_url,
            json=payload,
            timeout=self.config.request_timeout,
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            text_response = data.get("response")
            if not text_response and "error" in data:
                raise RuntimeError(f"Ollama error: {data['error']}")
        else:
            raise RuntimeError("Unexpected Ollama response type")
        score = self._parse_score(text_response or "")
        return score

    def _parse_score(self, text: str) -> int:
        matches = re.findall(r"\d{1,3}", text)
        if not matches:
            raise ValueError(f"Unable to parse numeric score from: {text!r}")
        for value in matches:
            score = int(value)
            if 0 <= score <= 100:
                return score
        raise ValueError(f"No valid score (0-100) found in: {text!r}")

    def _persist_score(self, record_id: str, score: int) -> None:
        fields = {self.config.target_field: score}
        self._update_record(record_id, fields, self.config.table_name)

    def _format_fields(self, fields: Dict[str, Any]) -> str:
        ordered_lines: List[str] = []
        seen = set()
        for key in self.config.key_fields:
            if key in fields:
                ordered_lines.append(f"{key}: {self._stringify(fields[key])}")
                seen.add(key)
        for key in sorted(k for k in fields.keys() if k not in seen):
            value = fields[key]
            if value is not None and value != "":
                ordered_lines.append(f"{key}: {self._stringify(value)}")
        if not ordered_lines:
            return "No property fields provided."
        return "\n".join(ordered_lines)

    @staticmethod
    def _stringify(value: Any) -> str:
        if isinstance(value, (list, tuple)):
            return ", ".join(str(item) for item in value if item not in (None, ""))
        if isinstance(value, dict):
            return ", ".join(f"{k}: {v}" for k, v in value.items())
        return str(value)

    def _sold_within_24_months(self, fields: Dict[str, Any]) -> bool:
        sale_date = self._extract_sale_date(fields)
        if not sale_date:
            return False
        delta = datetime.utcnow() - sale_date
        return delta.days <= 730

    def _extract_sale_date(self, fields: Dict[str, Any]) -> Optional[datetime]:
        for key in self.config.sale_date_fields:
            raw_value = fields.get(key)
            if not raw_value:
                continue
            parsed = self._parse_date(raw_value)
            if parsed:
                return parsed
        return None

    @staticmethod
    def _parse_date(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if hasattr(value, "isoformat"):
            try:
                return datetime.fromisoformat(value.isoformat())
            except (TypeError, ValueError):
                return None
        if isinstance(value, str):
            formats = ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d")
            for fmt in formats:
                try:
                    return datetime.strptime(value[:10], fmt)
                except ValueError:
                    continue
        return None


def main(limit: int | None = None) -> List[ScoreResult]:
    """Entry point for batch scoring, suitable for FastAPI wiring."""
    agent = ScoreAgent()
    return agent.score_all(limit=limit)


__all__ = ["ScoreAgent", "ScoreAgentConfig", "ScoreResult", "main"]
