"""Agent that evaluates creative finance fit for a lead."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from utils.config_loader import get_weights
from utils.helpers import clamp_score, motivation_to_scalar, safe_divide


router = APIRouter()


class CreativeFinancePayload(BaseModel):
    lead_id: Optional[str] = None
    asking_price: float = Field(..., ge=0)
    arv: float = Field(..., gt=0, description="After repair value")
    seller_mortgage_balance: Optional[float] = Field(None, ge=0)
    monthly_payment_capacity: Optional[float] = Field(None, ge=0)
    market_rent: Optional[float] = Field(None, ge=0)
    desired_timeline_days: Optional[int] = Field(None, ge=0)
    motivation_level: Optional[str] = None


class AgentResponse(BaseModel):
    score: float
    recommendation: str
    reasoning: str
    metadata: dict


def _evaluate_creative_fit(payload: CreativeFinancePayload) -> AgentResponse:
    weights = get_weights("creative_finance")
    equity_weight = float(weights.get("equity_weight", 35))
    motivation_weight = float(weights.get("motivation_weight", 30))
    cashflow_weight = float(weights.get("cashflow_weight", 20))
    timeline_weight = float(weights.get("timeline_weight", 15))

    equity = 0.0
    if payload.seller_mortgage_balance is not None:
        equity = 1 - safe_divide(payload.seller_mortgage_balance, payload.arv, 1.0)
        equity = max(0.0, equity)

    motivation_score = motivation_to_scalar(payload.motivation_level)

    cashflow_ratio = 0.0
    if payload.market_rent and payload.monthly_payment_capacity:
        cashflow_ratio = safe_divide(
            payload.market_rent - payload.monthly_payment_capacity,
            payload.market_rent,
            0.0,
        )

    timeline_score = 0.5
    if payload.desired_timeline_days is not None:
        if payload.desired_timeline_days <= 30:
            timeline_score = 1.0
        elif payload.desired_timeline_days <= 60:
            timeline_score = 0.8
        elif payload.desired_timeline_days <= 90:
            timeline_score = 0.6
        else:
            timeline_score = 0.3

    raw_score = (
        equity * 100 * (equity_weight / 100)
        + motivation_score * 100 * (motivation_weight / 100)
        + cashflow_ratio * 100 * (cashflow_weight / 100)
        + timeline_score * 100 * (timeline_weight / 100)
    )

    score = clamp_score(raw_score)

    if score >= 75:
        recommendation = "Present seller finance and subject-to structures."
    elif score >= 55:
        recommendation = "Explore hybrid terms and gather payoff statements."
    else:
        recommendation = "Default to cash offer flow; limited creative upside."

    reasoning = (
        f"Equity {equity:.2f}, motivation {motivation_score:.2f}, cashflow {cashflow_ratio:.2f} "
        f"yield score {score:.1f}."
    )

    metadata = {
        "lead_id": payload.lead_id,
        "equity": equity,
        "motivation": motivation_score,
        "cashflow_ratio": cashflow_ratio,
        "timeline_score": timeline_score,
    }

    return AgentResponse(
        score=score,
        recommendation=recommendation,
        reasoning=reasoning,
        metadata=metadata,
    )


@router.post("/creative-finance", response_model=AgentResponse)
def creative_finance_handler(payload: CreativeFinancePayload) -> AgentResponse:
    """Endpoint that evaluates creative finance suitability."""

    return _evaluate_creative_fit(payload)
