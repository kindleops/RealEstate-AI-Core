"""Agent that rates the quality of skiptrace data."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from utils.config_loader import get_weights
from utils.helpers import clamp_score, safe_divide


router = APIRouter()


class SkiptracePayload(BaseModel):
    list_id: Optional[str] = None
    total_numbers: int = Field(..., ge=0)
    bad_numbers: int = Field(0, ge=0)
    email_bounces: int = Field(0, ge=0)
    response_rate: Optional[float] = Field(None, ge=0, le=1)


class AgentResponse(BaseModel):
    score: float
    recommendation: str
    reasoning: str
    metadata: dict


def _assess_quality(payload: SkiptracePayload) -> AgentResponse:
    weights = get_weights("skiptrace_quality")
    max_score = float(weights.get("max_score", 100))
    bad_phone_penalty = float(weights.get("bad_phone_penalty", 20))
    bounce_penalty = float(weights.get("bounce_penalty", 12))
    response_bonus = float(weights.get("response_bonus", 15))

    base_score = max_score

    bad_ratio = safe_divide(payload.bad_numbers, payload.total_numbers, 0.0)
    bounce_ratio = safe_divide(payload.email_bounces, payload.total_numbers, 0.0)

    base_score -= bad_ratio * bad_phone_penalty * 100
    base_score -= bounce_ratio * bounce_penalty * 100

    if payload.response_rate is not None:
        base_score += payload.response_rate * response_bonus * 100

    score = clamp_score(base_score, maximum=max_score)

    if score >= 80:
        recommendation = "Proceed with campaigns; data quality is strong."
    elif score >= 60:
        recommendation = "Run light cleaning to remove flagged numbers."
    else:
        recommendation = "Trigger re-skiptrace workflow before major outreach."

    reasoning = (
        f"Bad number ratio {bad_ratio:.2f} and bounce ratio {bounce_ratio:.2f} "
        f"lead to score {score:.1f}."
    )

    metadata = {
        "list_id": payload.list_id,
        "bad_ratio": bad_ratio,
        "bounce_ratio": bounce_ratio,
        "response_rate": payload.response_rate,
    }

    return AgentResponse(
        score=score,
        recommendation=recommendation,
        reasoning=reasoning,
        metadata=metadata,
    )


@router.post("/skiptrace-quality", response_model=AgentResponse)
def skiptrace_quality_handler(payload: SkiptracePayload) -> AgentResponse:
    """Endpoint that scores the quality of skiptrace results."""

    return _assess_quality(payload)
