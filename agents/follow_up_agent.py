"""Background agent that orchestrates follow-up cadences."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List

from data.airtable_client import AirtableClient
from data.logger import get_logger
from utils.prompt_templates import get_template
from utils.tone_modulator import ToneModulator


class FollowUpAgent:
    def __init__(self, airtable: AirtableClient | None = None) -> None:
        self.airtable = airtable or AirtableClient()
        self.logger = get_logger("follow_up_agent")
        self.tone_modulator = ToneModulator()

    def find_unresponsive_leads(
        self, *, days_since_last_contact: int = 3, limit: int = 25
    ) -> List[Dict[str, str]]:
        threshold = datetime.utcnow() - timedelta(days=days_since_last_contact)
        candidates: List[Dict[str, str]] = []
        for contact in self.airtable.fetch_contacts(limit=500):
            interactions = self.airtable.recent_interactions(contact.contact_id, limit=1)
            if not interactions:
                candidates.append(contact.__dict__)
                continue
            last_interaction = interactions[-1]
            timestamp = last_interaction["details"].get("timestamp")
            if timestamp and datetime.fromisoformat(timestamp.rstrip("Z")) >= threshold:
                continue
            candidates.append(contact.__dict__)
            if len(candidates) >= limit:
                break
        return candidates

    def craft_follow_up(self, contact: Dict[str, str], *, tone: str = "professional") -> Dict[str, str]:
        template = get_template("follow_up")
        message = (
            f"Just checking in about your property at {contact.get('property_address', 'the property')}. "
            "Would you be open to continuing the conversation this week?"
        )
        body = self.tone_modulator.modulate(message, tone)
        return {"channel": "sms", "body": f"{template}\n\n{body}"}

    def schedule_follow_ups(self, *, days_since_last_contact: int = 3) -> List[Dict[str, str]]:
        leads = self.find_unresponsive_leads(days_since_last_contact=days_since_last_contact)
        scheduled: List[Dict[str, str]] = []
        for lead in leads:
            outreach = self.craft_follow_up(lead)
            payload = {
                "contact_id": lead.get("contact_id"),
                "outreach": outreach,
            }
            self.logger.log_event("follow_up_scheduled", payload)
            scheduled.append(payload)
        return scheduled


__all__ = ["FollowUpAgent"]

