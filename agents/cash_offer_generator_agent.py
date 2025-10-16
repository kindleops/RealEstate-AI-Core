"""Agent that provides cash offer ranges with basic safeguards."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from utils.config_loader import get_weights
from utils.helpers import clamp_score, safe_divide


router = APIRouter()


class CashOfferPayload(BaseModel):
    lead_id: Optional[str] = None
    arv: float = Field(..., gt=0, description="After repair value")
    estimated_repairs: float = Field(..., ge=0)
    wholesale_fee: float = Field(0, ge=0)
    confidence: float = Field(0.5, ge=0, le=1, description="Model confidence in the valuation")


class AgentResponse(BaseModel):
    score: float
    recommendation: str
    reasoning: str
    metadata: dict


def _generate_offer(payload: CashOfferPayload) -> AgentResponse:
    weights = get_weights("cash_offer")
    arv_discount = float(weights.get("arv_discount", 0.7))
    repair_buffer = float(weights.get("repair_buffer", 1.1))
    min_margin = float(weights.get("min_margin", 0.1))
    max_margin = float(weights.get("max_margin", 0.18))

    base_offer = payload.arv * arv_discount - payload.estimated_repairs * repair_buffer
    base_offer -= payload.wholesale_fee

    margin_high = max_margin + (0.05 if payload.confidence < 0.5 else 0.0)
    margin_low = min_margin

    high_offer = max(base_offer * (1 - margin_low), 0)
    low_offer = max(base_offer * (1 - margin_high), 0)

    if high_offer < low_offer:
        high_offer, low_offer = low_offer, high_offer

    spread = safe_divide(high_offer - low_offer, payload.arv, 0.0)
    score = clamp_score(100 - spread * 200)

    recommendation = "Anchor low range on first offer; move toward high range with strong motivation."
    reasoning = (
        f"ARV discounting at {arv_discount:.0%} with repair buffer {repair_buffer:.2f} "
        f"produces a {low_offer:,.0f}-{high_offer:,.0f} window."
    )

    metadata = {
        "lead_id": payload.lead_id,
        "offer_low": round(low_offer, 2),
        "offer_high": round(high_offer, 2),
        "spread": spread,
    }

    return AgentResponse(
        score=score,
        recommendation=recommendation,
        reasoning=reasoning,
        metadata=metadata,
    )


@router.post("/cash-offer", response_model=AgentResponse)
def cash_offer_handler(payload: CashOfferPayload) -> AgentResponse:
    """Endpoint that generates an initial cash offer range."""

    return _generate_offer(payload)
