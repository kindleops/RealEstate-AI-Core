"""Agent that determines property vacancy likelihood."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from utils.config_loader import get_weights
from utils.helpers import clamp_score


router = APIRouter()


class VacancyPayload(BaseModel):
    property_id: Optional[str] = None
    usps_vacancy_code: Optional[str] = Field(
        None, description="Raw USPS vacancy code from API response"
    )
    third_party_signals: List[str] = Field(
        default_factory=list, description="Signals from third-party vacancy checks"
    )
    utility_inactive: bool = Field(False, description="Whether utilities are reported as inactive")
    last_seen_occupied_days: Optional[int] = Field(None, ge=0)


class AgentResponse(BaseModel):
    score: float
    recommendation: str
    reasoning: str
    metadata: dict


def _compute_vacancy_score(payload: VacancyPayload) -> AgentResponse:
    weights = get_weights("vacancy")
    usps_weight = float(weights.get("usps_weight", 0.5))
    third_party_weight = float(weights.get("third_party_weight", 0.35))
    days_empty_weight = float(weights.get("days_empty_weight", 0.15))
    vacant_threshold = float(weights.get("vacant_threshold", 60))

    usps_score = 0.0
    if payload.usps_vacancy_code:
        code = payload.usps_vacancy_code.lower()
        if code in {"vacant", "nixie", "no-stat"}:
            usps_score = 100.0
        elif code == "inactive":
            usps_score = 70.0
        else:
            usps_score = 30.0

    third_party_score = min(len(payload.third_party_signals) * 20.0, 100.0)
    if payload.utility_inactive:
        third_party_score = max(third_party_score, 80.0)

    days_score = 0.0
    if payload.last_seen_occupied_days is not None:
        days_score = min(payload.last_seen_occupied_days, 365) / 365 * 100

    composite = (
        (usps_score * usps_weight)
        + (third_party_score * third_party_weight)
        + (days_score * days_empty_weight)
    )
    score = clamp_score(composite)

    if score >= vacant_threshold:
        recommendation = "Classify as likely vacant and prioritize for outreach."
    elif score >= vacant_threshold * 0.6:
        recommendation = "Schedule secondary verification call or drive-by."
    else:
        recommendation = "Mark as occupied; revisit if new vacancy signals appear."

    reasoning = (
        f"USPS score {usps_score:.1f}, third-party score {third_party_score:.1f}, "
        f"and days empty score {days_score:.1f} combined into {score:.1f}."
    )

    metadata = {
        "property_id": payload.property_id,
        "usps_score": usps_score,
        "third_party_score": third_party_score,
        "days_score": days_score,
    }

    return AgentResponse(
        score=score,
        recommendation=recommendation,
        reasoning=reasoning,
        metadata=metadata,
    )


@router.post("/vacancy-check", response_model=AgentResponse)
def vacancy_check_handler(payload: VacancyPayload) -> AgentResponse:
    """Endpoint that cross-checks vacancy indicators."""

    return _compute_vacancy_score(payload)
