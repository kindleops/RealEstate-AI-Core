"""FastAPI routes that expose batch agent operations."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException

from agents.offer_agent import OfferAgent, OfferAgentResult
from agents.score_agent import ScoreAgent, ScoreResult
from agents.sms_agent import SMSAgent, SMSAgentResult
from agents.trainer_agent import TrainerAgent

router = APIRouter()


@router.post("/ai/run-agent/{agent_name}")
def run_agent(agent_name: str, payload: Optional[Dict[str, Any]] = Body(default=None)) -> Dict[str, Any]:
    """Execute a named agent and return a processing summary."""

    agent_key = agent_name.lower()
    limit = None
    if payload:
        limit = payload.get("limit")
        if limit is not None:
            try:
                limit = int(limit)
            except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
                raise HTTPException(status_code=400, detail="limit must be an integer") from exc

    if agent_key in {"score", "score_agent"}:
        return _run_score_agent(limit)
    if agent_key in {"sms", "sms_agent"}:
        return _run_sms_agent(limit)
    if agent_key in {"offer", "offer_agent"}:
        return _run_offer_agent(limit)
    if agent_key in {"trainer", "trainer_agent"}:
        return _run_trainer_agent()

    raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' is not registered")


@router.post("/run-agent/{agent_name}")
def run_agent_legacy(agent_name: str, payload: Optional[Dict[str, Any]] = Body(default=None)) -> Dict[str, Any]:
    """Backward-compatible route that proxies to /ai/run-agent."""

    return run_agent(agent_name, payload)


def _run_score_agent(limit: Optional[int]) -> Dict[str, Any]:
    agent = ScoreAgent()
    results: List[ScoreResult] = agent.score_all(limit=limit)
    summary = _summarize_results(results)
    summary["details"] = [
        {"record_id": result.record_id, "score": result.score, "status": result.status}
        for result in results
    ]
    summary["agent"] = "score"
    return summary


def _run_sms_agent(limit: Optional[int]) -> Dict[str, Any]:
    agent = SMSAgent()
    results: List[SMSAgentResult] = agent.run_ready_conversations(limit=limit)
    summary = _summarize_results(results)
    summary["agent"] = "sms"
    return summary


def _run_offer_agent(limit: Optional[int]) -> Dict[str, Any]:
    agent = OfferAgent()
    results: List[OfferAgentResult] = agent.process_motivated_properties(limit=limit)
    summary = _summarize_results(results)
    summary["agent"] = "offer"
    return summary


def _run_trainer_agent() -> Dict[str, Any]:
    agent = TrainerAgent()
    summary = agent.analyze()
    summary["agent"] = "trainer"
    summary.setdefault("processed", 0)
    summary.setdefault("success", summary.get("processed", 0))
    summary.setdefault("failed", 0)
    return summary


def _summarize_results(results: List[Any]) -> Dict[str, Any]:
    processed = len(results)
    success = sum(1 for result in results if getattr(result, "status", "") == "success")
    failed = sum(1 for result in results if getattr(result, "status", "") == "error")
    return {
        "processed": processed,
        "success": success,
        "failed": failed,
    }


__all__ = ["router"]
