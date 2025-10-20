"""Agent that evaluates inbound leads from Airtable records."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from utils.config_loader import get_weights
from utils.helpers import clamp_score, motivation_to_scalar


router = APIRouter()


class InboundLeadPayload(BaseModel):
    """Expected structure for inbound lead payloads."""

    lead_id: Optional[str] = Field(None, description="Unique identifier for the Airtable record")
    contact_attempts: int = Field(0, ge=0)
    responded: bool = Field(False, description="Whether the lead has responded to any outreach")
    last_contact_days: int = Field(0, ge=0, description="Days since the last successful contact attempt")
    urgency_signals: List[str] = Field(default_factory=list, description="Signals that indicate urgency")
    motivation_level: Optional[str] = Field(None, description="Human readable motivation level from the CRM")
    motivation_signals: List[str] = Field(default_factory=list, description="Specific indicators of motivation")
    equity_estimate: Optional[float] = Field(None, ge=0, description="Estimated equity percentage (0-1)")


class AgentResponse(BaseModel):
    score: float
    recommendation: str
    reasoning: str
    metadata: dict


def _score_lead(payload: InboundLeadPayload) -> AgentResponse:
    weights = get_weights("inbound_leads")
    base_score = float(weights.get("base_score", 50))
    urgency_weight = float(weights.get("urgency_weight", 5))
    motivation_weight = float(weights.get("motivation_weight", 4))
    response_bonus = float(weights.get("response_bonus", 10))
    stale_penalty = float(weights.get("stale_penalty", 1.0))

    urgency_score = len(payload.urgency_signals) * urgency_weight
    motivation_score = (
        len(payload.motivation_signals) * motivation_weight
        + motivation_to_scalar(payload.motivation_level) * motivation_weight * 2
    )

    recency_penalty = min(payload.last_contact_days * stale_penalty, base_score)

    score = base_score + urgency_score + motivation_score - recency_penalty
    if payload.responded:
        score += response_bonus
    if payload.contact_attempts > 3 and not payload.responded:
        score -= response_bonus / 2

    if payload.equity_estimate is not None:
        score += payload.equity_estimate * 10

    final_score = clamp_score(score)

    if final_score >= 80:
        recommendation = "Prioritize immediate outbound call with senior closer."
    elif final_score >= 60:
        recommendation = "Follow up within 24 hours and keep in warm nurture sequence."
    else:
        recommendation = "Route to nurture automation and monitor for new signals."

    reasoning = (
        f"Lead urgency signals ({len(payload.urgency_signals)}) and motivation inputs "
        f"produce a score of {final_score:.1f}. "
        "Recent contact attempts and response history were also factored."
    )

    metadata = {
        "lead_id": payload.lead_id,
        "urgency_score": urgency_score,
        "motivation_score": motivation_score,
        "recency_penalty": recency_penalty,
    }

    return AgentResponse(
        score=final_score,
        recommendation=recommendation,
        reasoning=reasoning,
        metadata=metadata,
    )


@router.post("/inbound-leads", response_model=AgentResponse)
def inbound_leads_handler(payload: InboundLeadPayload) -> AgentResponse:
    """FastAPI handler that processes inbound lead scoring requests."""

    return _score_lead(payload)
