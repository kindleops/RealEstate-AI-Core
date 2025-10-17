"""Meta agent that analyzes outcomes and tunes configuration."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

from logger import LOG_DIR, get_logger
from agents.score_agent import ScoreAgent
from utils.model_selector import ModelSelector

LOGGER = get_logger()

LOG_FILE = LOG_DIR / "agent_runs.jsonl"
CAMPAIGN_FILE = Path("data/campaigns.json")


@dataclass
class TrainerAgentConfig:
    min_samples: int = 5


class TrainerAgent:
    """Review agent logs and campaign results to produce training insights."""

    def __init__(self, config: TrainerAgentConfig | None = None) -> None:
        self.config = config or TrainerAgentConfig()
        self.score_agent = ScoreAgent()
        self.model_selector = ModelSelector()

    def _read_jsonl(self, path: Path) -> Iterable[Dict[str, Any]]:
        if not path.exists():
            return []
        records: List[Dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    LOGGER.warning("Skipping malformed log line: %s", line[:80])
        return records

    def _read_campaigns(self) -> List[Dict[str, Any]]:
        if not CAMPAIGN_FILE.exists():
            return []
        with CAMPAIGN_FILE.open("r", encoding="utf-8") as fh:
            try:
                return json.load(fh)
            except json.JSONDecodeError:
                LOGGER.exception("Failed to parse campaign file")
                return []

    def analyze(self) -> Dict[str, Any]:
        logs = list(self._read_jsonl(LOG_FILE))
        campaigns = self._read_campaigns()
        summary: Dict[str, Any] = {
            "log_count": len(logs),
            "campaign_count": len(campaigns),
            "opt_outs": 0,
            "closes": 0,
            "agent_stats": defaultdict(int),
            "model_stats": defaultdict(int),
        }

        for record in logs:
            agent = record.get("agent")
            summary["agent_stats"][agent] += 1
            output = record.get("output", {})
            if output.get("opt_out"):
                summary["opt_outs"] += 1
            if output.get("status") == "closed":
                summary["closes"] += 1
            model = output.get("model") or record.get("model")
            if model:
                summary["model_stats"][model] += 1

        accuracy = self._compute_accuracy(campaigns)
        summary["accuracy"] = accuracy
        summary["agent_stats"] = dict(summary["agent_stats"])
        summary["model_stats"] = dict(summary["model_stats"])

        best_agent = max(summary["agent_stats"], key=summary["agent_stats"].get, default=None)
        best_model = max(summary["model_stats"], key=summary["model_stats"].get, default=None)
        summary.update({"best_agent": best_agent, "best_model": best_model})

        if logs and len(logs) >= self.config.min_samples:
            self._rebalance_weights(summary)
            self._rebalance_models(summary)

        return summary

    def _compute_accuracy(self, campaigns: Iterable[Dict[str, Any]]) -> float:
        total = 0
        hits = 0
        for campaign in campaigns:
            total += 1
            if campaign.get("outcome") == "closed":
                hits += 1
        if total == 0:
            return 0.0
        return round((hits / total) * 100, 2)

    def _rebalance_weights(self, summary: Dict[str, Any]) -> None:
        opt_out_rate = summary["opt_outs"] / max(summary["log_count"], 1)
        weights = self.score_agent.weights
        fields = weights.setdefault("fields", {})
        if opt_out_rate > 0.2:
            LOGGER.info("High opt-out rate detected, increasing empathy weight")
            fields["recent_communication"] = fields.get("recent_communication", {
                "thresholds": [{"max_days": 7, "score": 15}]
            })
        self.score_agent.update_weights(weights)

    def _rebalance_models(self, summary: Dict[str, Any]) -> None:
        model_counts = summary.get("model_stats", {})
        if not model_counts:
            return
        counter = Counter(model_counts)
        most_common_model, _ = counter.most_common(1)[0]
        total_runs = sum(counter.values())
        if total_runs == 0:
            return
        ratio = counter[most_common_model] / total_runs
        if ratio < 0.5:
            return
        LOGGER.info("Adjusting routing to favor model %s", most_common_model)
        if "phi3" in most_common_model:
            self.model_selector.update_routing(local_ratio=0.7, cloud_ratio=0.3)
        else:
            self.model_selector.update_routing(local_ratio=0.4, cloud_ratio=0.6)


__all__ = ["TrainerAgent", "TrainerAgentConfig"]
