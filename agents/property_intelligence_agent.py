"""Agent that infers motivation and urgency from raw property data."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from logger import get_logger

LOGGER = get_logger()


@dataclass
class PropertyIntelligenceConfig:
    urgency_threshold_days: int = 30
    high_equity_threshold: float = 50.0
    distress_keywords: tuple[str, ...] = (
        "divorce",
        "relocation",
        "behind on payments",
        "inheritance",
        "code violation",
    )


class PropertyIntelligenceAgent:
    """Lightweight NLP heuristics for property motivation analysis."""

    def __init__(self, config: PropertyIntelligenceConfig | None = None) -> None:
        self.config = config or PropertyIntelligenceConfig()

    def analyze(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        notes = (payload.get("notes") or "").lower()
        tags: List[str] = []
        if payload.get("vacant"):
            tags.append("vacant")
        if payload.get("tax_delinquent"):
            tags.append("tax_delinquent")
        for keyword in self.config.distress_keywords:
            if keyword in notes:
                tags.append(keyword.replace(" ", "_"))

        equity = self._to_float(payload.get("equity_percentage"))
        urgency_days = self._to_float(payload.get("days_until_deadline"))
        urgency = "low"
        if urgency_days is not None and urgency_days <= self.config.urgency_threshold_days:
            urgency = "high"
        elif urgency_days is not None and urgency_days <= self.config.urgency_threshold_days * 2:
            urgency = "medium"

        motivation = "medium"
        if equity is not None and equity >= self.config.high_equity_threshold:
            motivation = "high"
        if "vacant" in tags and urgency == "high":
            motivation = "high"
        if not tags and urgency == "low":
            motivation = "low"

        pain_points = self._extract_pain_points(notes, payload)

        return {
            "motivation": motivation,
            "urgency": urgency,
            "tags": tags,
            "pain_points": pain_points,
        }

    def _extract_pain_points(self, notes: str, payload: Dict[str, Any]) -> List[str]:
        pain_points: List[str] = []
        if "repair" in notes or payload.get("needs_repairs"):
            pain_points.append("repairs")
        if "tenant" in notes or payload.get("tenant_issues"):
            pain_points.append("tenant_issues")
        if "behind" in notes or payload.get("mortgage_late"):
            pain_points.append("arrears")
        if not pain_points:
            pain_points.append("unclear")
        return pain_points

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


__all__ = ["PropertyIntelligenceAgent", "PropertyIntelligenceConfig"]
