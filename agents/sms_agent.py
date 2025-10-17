"""Inbound SMS agent that generates human-friendly replies."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from logger import get_logger
from utils.model_selector import ModelChoice, ModelSelector

LOGGER = get_logger()


@dataclass
class SMSAgentConfig:
    opt_out_keywords: tuple[str, ...] = ("stop", "unsubscribe", "remove", "opt out")
    gratitude_keywords: tuple[str, ...] = ("thanks", "thank you", "appreciate")
    anger_keywords: tuple[str, ...] = ("angry", "mad", "upset", "annoyed")


class SMSAgent:
    """Generate AI-powered SMS replies with tone detection and opt-out handling."""

    def __init__(self, model_selector: ModelSelector | None = None, config: SMSAgentConfig | None = None) -> None:
        self.model_selector = model_selector or ModelSelector()
        self.config = config or SMSAgentConfig()

    def detect_tone(self, text: str) -> str:
        lowered = text.lower()
        if any(word in lowered for word in self.config.anger_keywords):
            return "frustrated"
        if any(word in lowered for word in self.config.gratitude_keywords):
            return "grateful"
        if "?" in text:
            return "curious"
        if any(exclaim in text for exclaim in ("!", "!!")):
            return "excited"
        return "neutral"

    def should_opt_out(self, text: str) -> bool:
        lowered = text.lower()
        return any(keyword in lowered for keyword in self.config.opt_out_keywords)

    def generate_reply(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        message = payload.get("text", "").strip()
        if not message:
            return {
                "reply": "Hi there! Could you please share a bit more so I can help?",
                "model": None,
                "tone": "neutral",
                "opt_out": False,
            }

        tone = self.detect_tone(message)
        if self.should_opt_out(message):
            reply = "I understand. You've been opted out and won't receive more messages."
            return {"reply": reply, "model": None, "tone": tone, "opt_out": True}

        selected_model = self._choose_model()
        prompt = self._build_prompt(message, tone, payload)
        reply = self._call_model(prompt, selected_model)
        return {"reply": reply, "model": selected_model.name, "tone": tone, "opt_out": False}

    def _choose_model(self) -> ModelChoice:
        choice = self.model_selector.choose(preference="local")
        if choice.name != "phi3:mini":
            LOGGER.debug("Initial model choice: %s", choice)
        if choice.name == "phi3:mini":
            return choice
        # prefer phi3:mini first, then fallback to mistral-7b
        return ModelChoice(name="phi3:mini", provider_type="local")

    def _call_model(self, prompt: str, model_choice: ModelChoice) -> str:
        # Placeholder for integration with actual LLM service.
        try:
            return self._simulate_model_response(prompt, model_choice)
        except Exception as exc:  # pragma: no cover - defensive fallback
            LOGGER.exception("Model %s failed: %s", model_choice.name, exc)
            fallback_choice = ModelChoice(name="mistral-7b", provider_type="local")
            return self._simulate_model_response(prompt, fallback_choice)

    @staticmethod
    def _build_prompt(message: str, tone: str, payload: Dict[str, Any]) -> str:
        name = payload.get("sender_name") or payload.get("from") or "there"
        return (
            "You are a friendly real-estate SMS assistant."
            " Keep responses under 45 words and sound human."
            f" The inbound tone feels {tone}."
            f" Sender name: {name}."
            f" Message: {message}"
        )

    @staticmethod
    def _simulate_model_response(prompt: str, model_choice: ModelChoice) -> str:
        # Simple heuristic: echo a friendly acknowledgement.
        tone_fragment = "appreciate" if "grateful" in prompt else "hear"
        return (
            "Thanks for reaching out! I "
            f"{tone_fragment} what you shared and I'm here to help with your property questions."
        )


__all__ = ["SMSAgent", "SMSAgentConfig"]
