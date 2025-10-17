"""Agent responsible for flagging properties with potential tax liens."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from utils.config_loader import get_weights
from utils.helpers import clamp_score


router = APIRouter()


class TaxLienRecord(BaseModel):
    amount: float = Field(..., ge=0, description="Outstanding lien amount")
    status: str = Field("active", description="Lien status from data provider")
    years_delinquent: Optional[int] = Field(
        None, ge=0, description="Number of years the tax bill has been delinquent"
    )


class TaxLienPayload(BaseModel):
    property_id: Optional[str] = None
    county: Optional[str] = None
    owner_occupied: Optional[bool] = None
    liens: List[TaxLienRecord] = Field(default_factory=list)


class AgentResponse(BaseModel):
    score: float
    recommendation: str
    reasoning: str
    metadata: dict


def _evaluate_liens(payload: TaxLienPayload) -> AgentResponse:
    weights = get_weights("tax_lien")
    severity_weight = float(weights.get("severity_weight", 0.015))
    status_multipliers = weights.get("status_multipliers", {})
    flag_threshold = float(weights.get("flag_threshold", 35))

    severity = 0.0
    for lien in payload.liens:
        multiplier = float(status_multipliers.get(lien.status.lower(), 1.0))
        years_multiplier = 1 + ((lien.years_delinquent or 0) * 0.1)
        severity += lien.amount * multiplier * years_multiplier

    score = clamp_score(severity * severity_weight)

    if score >= flag_threshold:
        recommendation = "Flag for attorney review and verify payoff requirements."
    elif score >= flag_threshold * 0.6:
        recommendation = "Collect payoff statement before drafting offer."
    else:
        recommendation = "No immediate lien escalation required; monitor in due diligence."

    reasoning = (
        f"Evaluated {len(payload.liens)} liens with weighted severity leading to a score of "
        f"{score:.1f}."
    )

    metadata = {
        "property_id": payload.property_id,
        "total_liens": len(payload.liens),
        "owner_occupied": payload.owner_occupied,
        "raw_severity": severity,
    }

    return AgentResponse(
        score=score,
        recommendation=recommendation,
        reasoning=reasoning,
        metadata=metadata,
    )


@router.post("/tax-lien", response_model=AgentResponse)
def tax_lien_handler(payload: TaxLienPayload) -> AgentResponse:
    """Endpoint that scores lien risk for a property."""

    return _evaluate_liens(payload)
