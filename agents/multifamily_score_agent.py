"""Agent that scores multifamily acquisitions based on financial metrics."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from utils.config_loader import get_weights
from utils.helpers import average, clamp_score, safe_divide


router = APIRouter()


class MultifamilyPayload(BaseModel):
    property_id: Optional[str] = None
    noi: float = Field(..., ge=0, description="Net operating income")
    purchase_price: float = Field(..., gt=0)
    cap_rate: Optional[float] = Field(None, ge=0)
    market_cap_rate: Optional[float] = Field(None, ge=0)
    comparable_cap_rates: List[float] = Field(default_factory=list)
    occupancy_rate: Optional[float] = Field(None, ge=0, le=1)


class AgentResponse(BaseModel):
    score: float
    recommendation: str
    reasoning: str
    metadata: dict


def _score_multifamily(payload: MultifamilyPayload) -> AgentResponse:
    weights = get_weights("multifamily")
    noi_weight = float(weights.get("noi_weight", 40))
    cap_weight = float(weights.get("cap_rate_weight", 35))
    comps_weight = float(weights.get("comps_weight", 25))
    max_score = float(weights.get("max_score", 100))

    noi_yield = safe_divide(payload.noi, payload.purchase_price) * 100

    cap_rate = payload.cap_rate or noi_yield
    market_cap = payload.market_cap_rate or cap_rate
    cap_delta = cap_rate - market_cap

    comps_average = average(payload.comparable_cap_rates) or market_cap
    comps_delta = cap_rate - comps_average

    occupancy_bonus = 0.0
    if payload.occupancy_rate is not None:
        occupancy_bonus = (payload.occupancy_rate - 0.9) * 50

    raw_score = (
        noi_yield * (noi_weight / 100)
        + cap_delta * 100 * (cap_weight / 100)
        + comps_delta * 100 * (comps_weight / 100)
        + occupancy_bonus
    )

    score = clamp_score(raw_score, maximum=max_score)

    if score >= 80:
        recommendation = "Advance to underwriting; numbers support acquisition."
    elif score >= 60:
        recommendation = "Gather more comps and stress test financing assumptions."
    else:
        recommendation = "Deprioritize; financial metrics trail market expectations."

    reasoning = (
        f"NOI yield of {noi_yield:.2f}% and cap delta of {cap_delta:.2f}% result in a "
        f"score of {score:.1f}."
    )

    metadata = {
        "property_id": payload.property_id,
        "noi_yield": noi_yield,
        "cap_rate": cap_rate,
        "market_cap_rate": market_cap,
        "comps_average": comps_average,
        "occupancy_bonus": occupancy_bonus,
    }

    return AgentResponse(
        score=score,
        recommendation=recommendation,
        reasoning=reasoning,
        metadata=metadata,
    )


@router.post("/multifamily-score", response_model=AgentResponse)
def multifamily_score_handler(payload: MultifamilyPayload) -> AgentResponse:
    """Endpoint that scores multifamily properties for acquisition."""

    return _score_multifamily(payload)
