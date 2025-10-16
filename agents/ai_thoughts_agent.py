"""Meta-agent that analyses the highest scoring leads."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Dict, Iterable, List

from data.logger import StructuredLogger, get_logger
from utils.prompt_templates import get_template


class AIThoughtsAgent:
    """Aggregate reasoning over the system's top performing leads."""

    def __init__(self, logger: StructuredLogger | None = None) -> None:
        self.logger = logger or get_logger("ai_thoughts")

    def review_top_leads(self, leads: Iterable[Dict[str, object]], limit: int = 50) -> Dict[str, object]:
        sorted_leads = sorted(leads, key=lambda lead: lead.get("score", 0), reverse=True)
        top = sorted_leads[:limit]
        summary = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "total_reviewed": len(top),
            "dominant_traits": self._dominant_traits(top),
            "false_positives": self._false_positives(top),
            "analysis": self._generate_analysis_text(top),
        }
        self.logger.log_event("daily_thoughts", summary)
        return summary

    def _dominant_traits(self, leads: List[Dict[str, object]]) -> List[str]:
        counter = Counter()
        for lead in leads:
            for trait in lead.get("traits", []) or []:
                counter[trait] += 1
        return [trait for trait, _ in counter.most_common(5)]

    def _false_positives(self, leads: List[Dict[str, object]]) -> List[str]:
        return [
            lead.get("contact_id", "unknown")
            for lead in leads
            if lead.get("score", 0) >= 80 and lead.get("status") == "dead"
        ]

    def _generate_analysis_text(self, leads: List[Dict[str, object]]) -> str:
        template = get_template("ai_thoughts")
        stats = {
            "avg_score": round(
                sum(float(lead.get("score", 0)) for lead in leads) / max(len(leads), 1), 2
            ),
            "high_intent_ratio": round(
                sum(1 for lead in leads if lead.get("intent") == "high") / max(len(leads), 1),
                2,
            ),
        }
        return (
            f"{template}\n\n"
            f"Average score: {stats['avg_score']}\n"
            f"High intent ratio: {stats['high_intent_ratio']}"
        )


__all__ = ["AIThoughtsAgent"]

