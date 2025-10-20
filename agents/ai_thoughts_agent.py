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

"""Agent for logging reflective thoughts from AI agents."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class AIThoughtsAgent:
    """Utility agent that records reflective thoughts from other agents.

    The agent persists thoughts to a JSON log file so that the broader system
    can review the reasoning history across tasks.
    """

    def __init__(self, log_path: Optional[Path] = None) -> None:
        """Initialize the logger with the path to the log file.

        Args:
            log_path: Optional custom path to the log file. When omitted the
                log file is created in the same directory as this module.
        """
        if log_path is None:
            log_path = Path(__file__).resolve().parent / "thoughts_log.json"

        self.log_path = log_path
        self._ensure_log_file()

    def _ensure_log_file(self) -> None:
        """Ensure the log file exists and is initialized with a JSON array."""
        if self.log_path.exists():
            return

        try:
            self.log_path.write_text("[]\n", encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(
                f"Unable to create log file at {self.log_path!s}: {exc}"
            ) from exc

    def _read_log(self) -> List[Dict[str, Any]]:
        """Read log entries, falling back to an empty list on parse errors."""
        try:
            content = self.log_path.read_text(encoding="utf-8").strip()
            if not content:
                return []
            data = json.loads(content)
            if isinstance(data, list):
                return data
            # If the JSON is not a list, treat it as corrupt and reset.
        except (json.JSONDecodeError, OSError) as exc:
            print(
                f"Warning: Failed to read thoughts log ({exc}). Resetting log file."
            )
        return []

    def _write_log(self, entries: List[Dict[str, Any]]) -> None:
        """Persist log entries to disk."""
        try:
            serialized = json.dumps(entries, indent=2, ensure_ascii=False)
            self.log_path.write_text(serialized + "\n", encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(
                f"Unable to write to log file at {self.log_path!s}: {exc}"
            ) from exc

    def log_thought(
        self,
        agent_name: str,
        task_summary: str,
        result_summary: str,
        next_step: str,
    ) -> Dict[str, Any]:
        """Record a reflective thought from an agent.

        Args:
            agent_name: Name of the agent producing the reflection.
            task_summary: Summary describing the completed task.
            result_summary: Description of the outcome of the task.
            next_step: Suggested next action for continued progress.

        Returns:
            The dictionary representing the persisted log entry.
        """
        if not all([agent_name, task_summary, result_summary, next_step]):
            raise ValueError("All log fields must be provided and non-empty.")

        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "agent_name": agent_name,
            "task_summary": task_summary,
            "result_summary": result_summary,
            "next_step": next_step,
        }

        entries = self._read_log()
        entries.append(entry)
        self._write_log(entries)

        print(json.dumps(entry, indent=2, ensure_ascii=False))
        return entry


__all__ = ["AIThoughtsAgent"]
