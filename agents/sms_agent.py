"""Inbound SMS agent that generates human-friendly replies."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

from data.airtable_client import AirtableError, get_records, update_record
from data.airtable_schema import CONVERSATIONS_TABLE, ConversationStatus
from data.logger import log_agent_event, log_batch_summary
from logger import get_logger
from utils.model_selector import ModelChoice, ModelSelector

LOGGER = get_logger()


@dataclass
class SMSAgentConfig:
    opt_out_keywords: tuple[str, ...] = ("stop", "unsubscribe", "remove", "opt out")
    gratitude_keywords: tuple[str, ...] = ("thanks", "thank you", "appreciate")
    anger_keywords: tuple[str, ...] = ("angry", "mad", "upset", "annoyed")
    table_name: str = CONVERSATIONS_TABLE.name()
    incoming_field: str = CONVERSATIONS_TABLE.field_name("MESSAGE")
    outgoing_field: str = CONVERSATIONS_TABLE.field_name("LAST_MESSAGE")
    contact_field: str = CONVERSATIONS_TABLE.field_name("CONTACT_NAME")
    status_field: str = CONVERSATIONS_TABLE.field_name("STATUS")
    ready_status: str = ConversationStatus.READY.value
    completed_status: str = ConversationStatus.RESPONDED.value
    opt_out_status: str = ConversationStatus.OPT_OUT.value
    model_name: str = "mistral:7b"
    ollama_url: str = "http://localhost:11434/api/generate"
    request_timeout: int = 60


@dataclass
class SMSAgentResult:
    record_id: str
    status: str
    reply: Optional[str] = None
    error: Optional[str] = None


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

    def run_ready_conversations(self, limit: Optional[int] = None) -> List[SMSAgentResult]:
        filter_formula = f"{{{self.config.status_field}}} = '{self.config.ready_status}'"
        try:
            records = get_records(self.config.table_name, filter_formula=filter_formula)
        except AirtableError as exc:
            LOGGER.exception("Failed to fetch ready conversations: %s", exc)
            return []

        results: List[SMSAgentResult] = []
        for record in records:
            if limit is not None and len(results) >= limit:
                break
            results.append(self._process_record(record))

        successes = sum(1 for result in results if result.status == "success")
        failures = sum(1 for result in results if result.status == "error")
        log_batch_summary("sms_agent", len(results), successes, failures)
        LOGGER.info("SMSAgent processed %s conversations", len(results))
        return results

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

    def _process_record(self, record: Dict[str, Any]) -> SMSAgentResult:
        record_id = record.get("id", "")
        fields: Dict[str, Any] = record.get("fields", {})
        if not record_id:
            LOGGER.error("Encountered conversation without record id: %s", record)
            return SMSAgentResult(record_id="", status="error", error="missing_record_id")

        incoming_message = str(fields.get(self.config.incoming_field, "")).strip()
        contact_name = fields.get(self.config.contact_field) or fields.get("Name")
        payload = {"text": incoming_message, "sender_name": contact_name}

        if not incoming_message:
            LOGGER.info("Record %s has no incoming message; skipping", record_id)
            log_agent_event(
                "sms_agent",
                record_id,
                "skipped",
                payload=fields,
                result={"reason": "missing_incoming_message"},
            )
            return SMSAgentResult(record_id=record_id, status="skipped")

        reply_payload = self.generate_reply(payload)
        reply_text = reply_payload.get("reply")
        status_value = (
            self.config.completed_status if not reply_payload.get("opt_out") else self.config.opt_out_status
        )

        try:
            update_record(
                self.config.table_name,
                record_id,
                {
                    self.config.outgoing_field: reply_text,
                    self.config.status_field: status_value,
                },
            )
        except AirtableError as exc:
            error_text = str(exc)
            LOGGER.exception("Failed to update conversation %s: %s", record_id, error_text)
            log_agent_event(
                "sms_agent",
                record_id,
                "error",
                payload=fields,
                result=reply_payload,
                error=error_text,
            )
            return SMSAgentResult(record_id=record_id, status="error", error=error_text)

        log_agent_event(
            "sms_agent",
            record_id,
            "success",
            payload=fields,
            result={"reply": reply_text, "status": status_value},
        )
        return SMSAgentResult(record_id=record_id, status="success", reply=reply_text)

    def _choose_model(self) -> ModelChoice:
        try:
            choice = self.model_selector.choose(preference="local")
        except Exception:  # pragma: no cover - defensive logging
            LOGGER.exception("Model selector failed; defaulting to mistral")
            return ModelChoice(name=self.config.model_name, provider_type="local")
        if choice.provider_type != "local":
            return ModelChoice(name=self.config.model_name, provider_type="local")
        return ModelChoice(name=self.config.model_name, provider_type="local")

    def _call_model(self, prompt: str, model_choice: ModelChoice) -> str:
        if model_choice.provider_type == "local":
            return self._invoke_local_model(prompt, model_choice.name)
        LOGGER.warning("Unsupported provider %s; falling back to local model", model_choice.provider_type)
        return self._invoke_local_model(prompt, self.config.model_name)

    def _invoke_local_model(self, prompt: str, model_name: str) -> str:
        payload = {"model": model_name, "prompt": prompt, "stream": False}
        response = requests.post(
            self.config.ollama_url,
            json=payload,
            timeout=self.config.request_timeout,
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and data.get("response"):
            return data["response"].strip()
        raise RuntimeError(f"Unexpected Ollama response: {data}")

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
    def _simulate_model_response(prompt: str, model_choice: ModelChoice) -> str:  # pragma: no cover - legacy fallback
        tone_fragment = "appreciate" if "grateful" in prompt else "hear"
        return (
            "Thanks for reaching out! I "
            f"{tone_fragment} what you shared and I'm here to help with your property questions."
        )


__all__ = ["SMSAgent", "SMSAgentConfig"]
