"""Agent that estimates repair cost ranges for properties."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from utils.config_loader import get_weights
from utils.helpers import clamp_score


router = APIRouter()


class RepairItem(BaseModel):
    name: str
    cost_per_sqft_adjustment: Optional[float] = Field(
        None, description="Adjustment to base cost per square foot"
    )


class RepairPayload(BaseModel):
    property_id: Optional[str] = None
    square_footage: float = Field(..., gt=0)
    condition: str = Field(..., description="One of light, medium, or heavy")
    repair_items: List[RepairItem] = Field(default_factory=list)
    material_cost_index: Optional[float] = Field(
        None, ge=0, description="Multiplier to adjust for local material costs"
    )
    contingency: Optional[float] = Field(
        None, ge=0, description="Additional contingency percentage"
    )


class AgentResponse(BaseModel):
    score: float
    recommendation: str
    reasoning: str
    metadata: dict


def _estimate_repairs(payload: RepairPayload) -> AgentResponse:
    weights = get_weights("repair_cost")
    base_per_sqft = float(weights.get("base_per_sqft", 18))
    condition_adjustments = weights.get("condition_adjustments", {})
    contingency_default = float(weights.get("contingency_default", 0.1))

    condition_key = payload.condition.strip().lower()
    condition_multiplier = float(condition_adjustments.get(condition_key, 1.0))

    adjusted_cost = base_per_sqft * condition_multiplier
    for item in payload.repair_items:
        if item.cost_per_sqft_adjustment is not None:
            adjusted_cost += item.cost_per_sqft_adjustment

    if payload.material_cost_index is not None:
        adjusted_cost *= payload.material_cost_index

    contingency_rate = payload.contingency if payload.contingency is not None else contingency_default

    base_total = adjusted_cost * payload.square_footage
    contingency_amount = base_total * contingency_rate
    low_estimate = max(base_total - contingency_amount * 0.5, 0)
    high_estimate = base_total + contingency_amount

    variability = contingency_rate + len(payload.repair_items) * 0.02
    score = clamp_score(100 - variability * 100)

    recommendation = "Use high estimate for offers; confirm big ticket systems on inspection."
    reasoning = (
        f"Base cost {adjusted_cost:.2f} per sqft over {payload.square_footage:,.0f} sqft yields "
        f"{low_estimate:,.0f}-{high_estimate:,.0f} range."
    )

    metadata = {
        "property_id": payload.property_id,
        "low_estimate": round(low_estimate, 2),
        "high_estimate": round(high_estimate, 2),
        "contingency_rate": contingency_rate,
        "adjusted_cost_per_sqft": adjusted_cost,
    }

    return AgentResponse(
        score=score,
        recommendation=recommendation,
        reasoning=reasoning,
        metadata=metadata,
    )


@router.post("/repair-cost", response_model=AgentResponse)
def repair_cost_handler(payload: RepairPayload) -> AgentResponse:
    """Endpoint that estimates repair cost ranges for a property."""

    return _estimate_repairs(payload)
