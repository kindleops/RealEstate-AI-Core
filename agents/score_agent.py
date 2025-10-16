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
