"""Voice agent orchestrating Whisper transcription and TTS."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from data.logger import get_logger
from utils.prompt_templates import get_template


class VoiceAgent:
    """Handle inbound audio transcription and outbound offer calls."""

    def __init__(self) -> None:
        self.logger = get_logger("voice_agent")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.tts_provider = os.getenv("VOICE_PROVIDER", "elevenlabs")

    def transcribe(self, audio_path: Path) -> str:
        if not self.openai_api_key:
            text = f"[transcription unavailable for {audio_path}]"
            self.logger.log_event("transcription_skipped", {"path": str(audio_path)})
            return text
        # Production code would call OpenAI Whisper API here.
        text = f"Simulated transcription for {audio_path.name}"
        self.logger.log_event("transcription", {"path": str(audio_path), "text": text})
        return text

    def synthesise(self, script: str, *, voice_id: Optional[str] = None) -> Path:
        voice_id = voice_id or "default"
        output_path = Path("data/voice_outputs") / f"{voice_id}.txt"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(script, encoding="utf-8")
        self.logger.log_event("tts_generated", {"voice": voice_id, "path": str(output_path)})
        return output_path

    def drop_offer_call(self, contact: dict, offer_details: dict) -> Path:
        script = self._build_offer_script(contact, offer_details)
        recording_path = self.synthesise(script, voice_id=contact.get("voice_id"))
        self.logger.log_event(
            "offer_call_generated",
            {"contact_id": contact.get("contact_id"), "recording": str(recording_path)},
        )
        return recording_path

    def _build_offer_script(self, contact: dict, offer_details: dict) -> str:
        template = get_template("voice_agent")
        return (
            f"{template}\n\n"
            f"Hi {contact.get('name', 'there')}, this is {offer_details.get('agent_name', 'your acquisitions partner')}. "
            f"I'm excited to share an offer of ${offer_details.get('amount', 'N/A')} for your property at "
            f"{contact.get('property_address', 'your property')}."
        )


__all__ = ["VoiceAgent"]

