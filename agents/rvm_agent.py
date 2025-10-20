"""Ringless voicemail automation agent."""

from __future__ import annotations

from typing import Dict

from data.airtable_client import AirtableClient
from data.logger import get_logger
from utils.prompt_templates import get_template
from utils.tone_modulator import ToneModulator


class RVMAgent:
    def __init__(self, airtable: AirtableClient | None = None) -> None:
        self.airtable = airtable or AirtableClient()
        self.logger = get_logger("rvm_agent")
        self.tone_modulator = ToneModulator()

    def generate_script(self, contact: Dict[str, str], *, tone: str = "friendly") -> str:
        template = get_template("rvm")
        body = (
            f"Hi {contact.get('name', 'there')}, this is Alex from Core Acquisitions. "
            f"I was reviewing your property at {contact.get('property_address', 'your property')} and "
            "wanted to share a quick offer update."
        )
        return self.tone_modulator.modulate(f"{template}\n\n{body}", tone)

    def drop_voicemail(self, contact_id: str, *, tone: str = "friendly") -> Dict[str, str]:
        contact = next(
            (c.__dict__ for c in self.airtable.fetch_contacts() if c.contact_id == contact_id),
            None,
        )
        if not contact:
            raise ValueError(f"Contact {contact_id} not found")
        script = self.generate_script(contact, tone=tone)
        self.airtable.log_interaction(contact_id, "rvm", {"script": script})
        self.logger.log_event(
            "rvm_drop", {"contact_id": contact_id, "tone": tone, "script": script}
        )
        return {"contact_id": contact_id, "script": script}


__all__ = ["RVMAgent"]

