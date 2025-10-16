"""Entry point for the Real Estate AI Core service."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Dict

from fastapi import FastAPI, HTTPException

from utils import model_selector
from utils.logger import log_interaction

LOGGER = log_interaction


@dataclass
class AgentPayload:
    agent: str
    input: str


class SimpleAgent:
    """Minimal agent implementation used for testing and prototyping."""

    def __init__(self, key: str):
        self.key = key
        self.display_name = f"{key} agent"

    def run(self, input_text: str) -> Dict[str, str]:
        model = model_selector.select_model({"type": self.key}, input_text)
        response_text = f"{self.display_name} response to: {input_text}"

        if LOGGER is not None:
            LOGGER(self.key, input_text, response_text)

        return {"agent": self.key, "model": model, "response": response_text}


def load_models() -> Dict[str, Dict[str, str]]:
    """Return a simple registry of available models."""

    models: Dict[str, Dict[str, str]] = {
        model_name: {"name": model_name}
        for model_name in model_selector.DEFAULT_MODEL_MAP.values()
    }
    models[model_selector.FALLBACK_MODEL] = {
        "name": model_selector.FALLBACK_MODEL,
        "fallback": "true",
    }
    return models


def load_agents() -> Dict[str, SimpleAgent]:
    """Instantiate lightweight agents for each supported task type."""

    return {task_type: SimpleAgent(task_type) for task_type in model_selector.DEFAULT_MODEL_MAP}


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(title="Real Estate AI Core", version="0.1.0")
    app.state = SimpleNamespace(models=load_models(), agents=load_agents())

    @app.get("/ping")
    def ping() -> Dict[str, str]:
        return {"status": "ok"}

    @app.post("/agents/run")
    def run_agent(payload: AgentPayload) -> Dict[str, str]:
        agents = app.state.agents
        agent = agents.get(payload.agent)
        if agent is None:
            raise HTTPException(status_code=404, detail="Agent not found")

        return agent.run(payload.input)

    return app


app = create_app()


__all__ = [
    "app",
    "create_app",
    "load_agents",
    "load_models",
    "LOGGER",
    "SimpleAgent",
    "AgentPayload",
]
