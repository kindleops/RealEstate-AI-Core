"""FastAPI routes that expose the agent layer."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from agents.comps_agent import CompsAgent
from agents.offer_agent import OfferAgent
from agents.property_intelligence_agent import PropertyIntelligenceAgent
from agents.score_agent import ScoreAgent
from agents.sms_agent import SMSAgent
from agents.trainer_agent import TrainerAgent
from logger import log_agent_interaction
from utils.model_selector import ModelSelector

router = APIRouter()

model_selector = ModelSelector()

AGENT_REGISTRY = {
    "sms_agent": SMSAgent(model_selector=model_selector),
    "offer_agent": OfferAgent(comps_agent=CompsAgent(model_selector=model_selector)),
    "comps_agent": CompsAgent(model_selector=model_selector),
    "score_agent": ScoreAgent(),
    "trainer_agent": TrainerAgent(),
    "property_intelligence_agent": PropertyIntelligenceAgent(),
}


def _dispatch_agent(agent_name: str, payload: dict) -> dict:
    agent = AGENT_REGISTRY.get(agent_name)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent {agent_name} not found")

    if isinstance(agent, SMSAgent):
        return agent.generate_reply(payload)
    if isinstance(agent, OfferAgent):
        return agent.calculate_offer(payload)
    if isinstance(agent, CompsAgent):
        return agent.generate_comps(payload)
    if isinstance(agent, ScoreAgent):
        return agent.score(payload)
    if isinstance(agent, TrainerAgent):
        return agent.analyze()
    if isinstance(agent, PropertyIntelligenceAgent):
        return agent.analyze(payload)

    raise HTTPException(status_code=400, detail=f"Agent {agent_name} has no handler")


@router.post("/run-agent/{agent_name}")
def run_agent(agent_name: str, payload: dict) -> dict:
    response = _dispatch_agent(agent_name, payload)
    log_agent_interaction(agent_name, payload, response)
    return {"agent": agent_name, "result": response}


@router.post("/ai/route")
def ai_route(request: dict) -> dict:
    agent_name = request.get("agent")
    payload = request.get("payload", {})
    preference = request.get("provider_preference")
    if not agent_name:
        raise HTTPException(status_code=400, detail="Missing agent in request")

    model_choice = model_selector.choose(preference=preference)
    response = _dispatch_agent(agent_name, payload)
    response.setdefault("model", model_choice.name)
    log_agent_interaction(agent_name, payload, response)
    return {
        "agent": agent_name,
        "model_choice": {
            "name": model_choice.name,
            "provider_type": model_choice.provider_type,
        },
        "result": response,
    }


__all__ = ["router"]
