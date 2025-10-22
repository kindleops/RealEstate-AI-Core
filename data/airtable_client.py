"""Universal Airtable REST client shared across agents."""
from __future__ import annotations

import os
import time
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote

import requests

from config.env import load_env
from logger import get_logger

LOGGER = get_logger()

load_env()

API_KEY = os.getenv("AIRTABLE_API_KEY")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
API_BASE_URL = "https://api.airtable.com/v0"

MAX_RETRIES = 5
BACKOFF_SECONDS = 2.0
PAGE_SIZE = 100


class AirtableError(RuntimeError):
    """Raised when the Airtable API returns an error response."""


class AirtableAuthenticationError(AirtableError):
    """Raised when Airtable credentials are missing or invalid."""


def _headers() -> Dict[str, str]:
    if not API_KEY or not BASE_ID:
        raise AirtableAuthenticationError(
            "AIRTABLE_API_KEY and AIRTABLE_BASE_ID must be set in the environment."
        )
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }


def _url(table_name: str, suffix: str = "") -> str:
    encoded = quote(table_name, safe="")
    if suffix:
        return f"{API_BASE_URL}/{BASE_ID}/{encoded}/{suffix}"
    return f"{API_BASE_URL}/{BASE_ID}/{encoded}"


def _request(
    method: str,
    table_name: str,
    record_id: str | None = None,
    *,
    params: Optional[Dict[str, Any]] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    url = _url(table_name, record_id) if record_id else _url(table_name)
    headers = _headers()
    attempt = 0
    while attempt < MAX_RETRIES:
        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                params=params,
                json=payload,
                timeout=30,
            )
        except requests.RequestException as exc:
            attempt += 1
            LOGGER.warning("Airtable request error (%s attempt %s/%s): %s", method, attempt, MAX_RETRIES, exc)
            time.sleep(BACKOFF_SECONDS * attempt)
            continue

        if response.status_code == 429:
            retry_after = float(response.headers.get("Retry-After", BACKOFF_SECONDS))
            LOGGER.info("Airtable rate limit hit; sleeping for %.1fs", retry_after)
            time.sleep(retry_after)
            attempt += 1
            continue

        if 500 <= response.status_code < 600:
            attempt += 1
            LOGGER.warning(
                "Airtable server error %s on %s attempt %s/%s",
                response.status_code,
                method,
                attempt,
                MAX_RETRIES,
            )
            time.sleep(BACKOFF_SECONDS * attempt)
            continue

        if 200 <= response.status_code < 300:
            return response.json()

        raise AirtableError(
            f"Airtable responded with {response.status_code}: {response.text}"
        )

    raise AirtableError("Exceeded retry budget for Airtable request")


def get_records(
    table_name: str,
    view: str | None = None,
    filter_formula: str | None = None,
    fields: Optional[Iterable[str]] = None,
    page_size: int = PAGE_SIZE,
) -> List[Dict[str, Any]]:
    """Retrieve all records from a table with optional view or filter."""
    params: Dict[str, Any] = {"pageSize": page_size}
    if view:
        params["view"] = view
    if filter_formula:
        params["filterByFormula"] = filter_formula
    if fields:
        params["fields[]"] = list(fields)

    records: List[Dict[str, Any]] = []
    offset: Optional[str] = None

    while True:
        loop_params = params.copy()
        if offset:
            loop_params["offset"] = offset
        response = _request("GET", table_name, params=loop_params)
        records.extend(response.get("records", []))
        offset = response.get("offset")
        if not offset:
            break
    LOGGER.info("Fetched %s records from Airtable table %s", len(records), table_name)
    return records


def update_record(table_name: str, record_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    """Update a single record in Airtable."""
    payload = {"fields": fields}
    response = _request("PATCH", table_name, record_id, payload=payload)
    LOGGER.info("Updated Airtable record %s.%s", table_name, record_id)
    return response


def create_record(table_name: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new Airtable record."""
    payload = {"fields": fields}
    response = _request("POST", table_name, payload=payload)
    LOGGER.info("Created Airtable record in %s", table_name)
    return response


def batch_update(table_name: str, updates: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Batch update records with chunking to respect Airtable limits."""
    results: List[Dict[str, Any]] = []
    chunk: List[Dict[str, Any]] = []
    for update in updates:
        chunk.append(update)
        if len(chunk) == 10:
            results.extend(_dispatch_batch(table_name, chunk))
            chunk = []
    if chunk:
        results.extend(_dispatch_batch(table_name, chunk))
    LOGGER.info("Batch updated %s records in %s", len(results), table_name)
    return results


def _dispatch_batch(table_name: str, chunk: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    payload = {"records": chunk}
    response = _request("PATCH", table_name, payload=payload)
    return response.get("records", [])


__all__ = ["get_records", "update_record", "create_record", "batch_update", "AirtableError", "AirtableAuthenticationError"]
