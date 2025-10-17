"""Agent responsible for calculating property offers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from logger import get_logger
from agents.comps_agent import CompsAgent

LOGGER = get_logger()


@dataclass
class OfferAgentConfig:
    default_margin: float = 0.7  # 70% discount multiplier when margin missing


class OfferAgent:
    """Compute an offer price based on ARV, repairs, and desired margin."""

    def __init__(self, config: OfferAgentConfig | None = None, comps_agent: Optional[CompsAgent] = None) -> None:
        self.config = config or OfferAgentConfig()
        self.comps_agent = comps_agent or CompsAgent()

    def calculate_offer(self, payload: Dict[str, object]) -> Dict[str, Any]:
        arv = payload.get("arv")
        repairs = float(payload.get("repairs", 0) or 0)
        margin = payload.get("margin")
        if margin is None:
            margin = self.config.default_margin

        if arv is None:
            LOGGER.info("ARV missing, invoking comps agent")
            comps_result = self.comps_agent.generate_comps(payload)
            arv = comps_result.get("arv")
        else:
            comps_result = None

        arv = float(arv or 0)
        margin = float(margin)
        # Formula: Offer = (ARV * Margin) - Repairs
        offer_price = max((arv * margin) - repairs, 0)

        result = {
            "arv": arv,
            "repairs": repairs,
            "margin": margin,
            "offer_price": round(offer_price, 2),
        }
        if comps_result:
            result["comps"] = comps_result.get("comps", [])
            result["arv_source"] = "comps_agent"
        else:
            result["arv_source"] = "payload"
        return result


__all__ = ["OfferAgent", "OfferAgentConfig"]
