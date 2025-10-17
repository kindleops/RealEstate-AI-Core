"""Centralised prompt templates for conversational agents."""

from __future__ import annotations

from typing import Dict


PROMPT_TEMPLATES: Dict[str, str] = {
    "market_trends": (
        "You are a real estate analyst. Summarise the hottest ZIP codes "
        "based on month-over-month appreciation, supply levels, and buyer "
        "demand signals."
    ),
    "ai_thoughts": (
        "You are the meta-analyst for the acquisitions team. Review the "
        "highest scoring leads and explain why they scored well, any false "
        "positives, and emerging persona traits."
    ),
    "voice_agent": (
        "You are a confident acquisitions specialist calling a motivated "
        "seller. Deliver the offer clearly and highlight how seamless the "
        "closing process will be."
    ),
    "rvm": (
        "Draft a concise, friendly voicemail from an acquisitions agent. "
        "Reference the seller's property and invite them to a quick call."
    ),
    "follow_up": (
        "Compose a follow-up outreach touching on the last conversation, "
        "reconfirming interest, and providing a next step."
    ),
    "learning_loop": (
        "Compare closed deals versus dead leads. Identify scoring weights "
        "that should be increased or decreased based on performance."
    ),
}


def get_template(key: str) -> str:
    """Retrieve a prompt template by key."""

    try:
        return PROMPT_TEMPLATES[key]
    except KeyError as exc:  # pragma: no cover - defensive branch
        raise KeyError(f"Unknown prompt template '{key}'.") from exc


__all__ = ["get_template", "PROMPT_TEMPLATES"]

