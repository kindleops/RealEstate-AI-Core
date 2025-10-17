"""Simplified Airtable client used by the automation agents.

The real platform integrates with Airtable's REST API.  For the purposes of
this codebase we provide a light-weight local persistence layer that mimics
the behaviour of the remote API.  Data is stored in ``data/airtable.json`` and
is safe to use in offline development environments and unit tests.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional


DEFAULT_DB_PATH = Path("data/airtable.json")


@dataclass
class Contact:
    """Representation of a single lead/contact entry."""

    contact_id: str
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    zipcode: Optional[str] = None
    status: str = "new"
    score: Optional[float] = None
    metadata: Dict[str, str] = field(default_factory=dict)


class AirtableClient:
    """Tiny persistence layer to emulate Airtable operations."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.db_path.exists():
            self._write({"contacts": [], "interactions": []})

    # ------------------------------------------------------------------
    # Internal helpers
    def _read(self) -> Dict[str, List[Dict[str, str]]]:
        with self.db_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def _write(self, payload: Dict[str, List[Dict[str, str]]]) -> None:
        with self.db_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # Public API
    def upsert_contact(self, contact: Contact) -> None:
        payload = self._read()
        contacts = payload.setdefault("contacts", [])
        for idx, record in enumerate(contacts):
            if record["contact_id"] == contact.contact_id:
                contacts[idx] = contact.__dict__
                self._write(payload)
                return
        contacts.append(contact.__dict__)
        self._write(payload)

    def fetch_contacts(
        self, *, statuses: Optional[Iterable[str]] = None, limit: Optional[int] = None
    ) -> List[Contact]:
        payload = self._read()
        contacts = [Contact(**record) for record in payload.get("contacts", [])]
        if statuses:
            statuses = {status.lower() for status in statuses}
            contacts = [c for c in contacts if c.status.lower() in statuses]
        if limit is not None:
            contacts = contacts[:limit]
        return contacts

    def log_interaction(
        self, contact_id: str, interaction_type: str, details: Dict[str, str]
    ) -> None:
        payload = self._read()
        interactions = payload.setdefault("interactions", [])
        details = details.copy()
        details.setdefault("timestamp", datetime.utcnow().isoformat() + "Z")
        interactions.append(
            {
                "contact_id": contact_id,
                "type": interaction_type,
                "details": details,
            }
        )
        self._write(payload)

    def recent_interactions(self, contact_id: str, limit: int = 10) -> List[Dict[str, str]]:
        payload = self._read()
        interactions = [
            interaction
            for interaction in payload.get("interactions", [])
            if interaction["contact_id"] == contact_id
        ]
        return interactions[-limit:]


__all__ = ["AirtableClient", "Contact"]

"""Wrapper around pyairtable for property data access."""
from __future__ import annotations

import os
from typing import Any, Dict, Iterable, Optional

from logger import get_logger

LOGGER = get_logger()

try:
    from pyairtable import Table
except ImportError:  # pragma: no cover - optional dependency
    Table = None  # type: ignore


def _get_table(table_name: str) -> Optional["Table"]:
    api_key = os.getenv("AIRTABLE_API_KEY")
    base_id = os.getenv("AIRTABLE_BASE_ID")
    if not Table or not api_key or not base_id:
        LOGGER.warning("pyairtable not configured; returning None for table %s", table_name)
        return None
    return Table(api_key, base_id, table_name)


def get_properties(table_name: str = "Properties") -> Iterable[Dict[str, Any]]:
    table = _get_table(table_name)
    if not table:
        return []
    return table.all()


def update_property(record_id: str, fields: Dict[str, Any], table_name: str = "Properties") -> Dict[str, Any]:
    table = _get_table(table_name)
    if not table:
        LOGGER.warning("Cannot update property %s; pyairtable unavailable", record_id)
        return {"id": record_id, "fields": fields}
    return table.update(record_id, fields)


def append_log(agent: str, input_payload: Dict[str, Any], output_payload: Dict[str, Any], table_name: str = "Agent Logs") -> Dict[str, Any]:
    table = _get_table(table_name)
    record = {
        "Agent": agent,
        "Input": str(input_payload),
        "Output": str(output_payload),
    }
    if not table:
        LOGGER.warning("pyairtable unavailable; returning log stub")
        record["status"] = "stub"
        return record
    return table.create(record)


__all__ = ["get_properties", "update_property", "append_log"]
