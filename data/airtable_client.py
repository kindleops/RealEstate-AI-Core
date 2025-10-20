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


def _get_table(table_name: str) -> Optional[Any]:
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
