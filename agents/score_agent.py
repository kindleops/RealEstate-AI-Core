"""Agent that scores Airtable property records using a local Ollama model."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence

import requests

from data.airtable_client import AirtableError, get_records, update_record
from data.airtable_schema import PROPERTIES_TABLE
from data.logger import append_score_log, log_batch_summary
from logger import get_logger

LOGGER = get_logger()

PROMPT_TEMPLATE = (
    "You are an AI analyst for a wholesale real estate company.\n"
    "Evaluate the following property based on its potential motivation and distress level for a quick cash sale.\n\n"
    "Analyze:\n"
    "- Property details (year built, beds, baths, sqft, type, location)\n"
    "- Ownership and situation (vacant, absentee, inherited, tax delinquent, preforeclosure)\n"
    "- Market context (recent sales, price trends, demand in ZIP)\n"
    "- Visible distress indicators (repairs needed, liens, age of home, long ownership)\n"
    "- Online listings and sale history from Zillow, Realtor, Propwire, and general market knowledge\n\n"
    "Scoring rules:\n"
    "1. If sold within the last 24 months → score = 0\n"
    "2. Otherwise, assign a score 1–100 (90–100 = very motivated, 70–89 = likely motivated, 40–69 = mild, 1–39 = low)\n"
    "Return only the numeric score, nothing else.\n\n"
    "Property data:\n"
    "{property_data}\n"
)


_KEY_FIELD_KEYS: Sequence[str] = (
    "ADDRESS",
    "CITY",
    "STATE",
    "ZIP",
    "YEAR_BUILT",
    "BEDS",
    "BATHS",
    "SQUARE_FEET",
    "LOT_SIZE",
    "PROPERTY_TYPE",
    "VACANCY",
    "OWNER_TYPE",
    "OWNERSHIP_LENGTH",
    "PREFORECLOSURE",
    "TAX_DELINQUENT",
    "LIENS",
    "AUCTION_DATE",
    "LAST_SOLD_DATE",
    "LAST_SALE_PRICE",
    "ESTIMATED_REPAIRS",
    "ARV",
)

_SALE_DATE_FIELD_KEYS: Sequence[str] = ("LAST_SOLD_DATE", "LAST_SALE_DATE")


@dataclass(slots=True)
class ScoreAgentConfig:
    """Runtime options for the score agent."""

    table_name: str = PROPERTIES_TABLE.name()
    target_field: str = PROPERTIES_TABLE.field_name("MOTIVATION_SCORE")
    model: str = "mistral:7b"
    ollama_url: str = "http://localhost:11434/api/generate"
    request_timeout: int = 120
    key_fields: Sequence[str] = tuple(PROPERTIES_TABLE.field_name(key) for key in _KEY_FIELD_KEYS)
    sale_date_fields: Sequence[str] = tuple(PROPERTIES_TABLE.field_name(key) for key in _SALE_DATE_FIELD_KEYS)
    max_records: Optional[int] = None


@dataclass(slots=True)
class ScoreResult:
    """Outcome of processing a single Airtable record."""

    record_id: str
    score: Optional[int]
    status: str
    error: Optional[str] = None


class ScoreAgent:
    """Fetch property records, score them with an LLM, and persist results."""

    def __init__(
        self,
        config: ScoreAgentConfig | None = None,
        fetch_records: Callable[..., List[Dict[str, Any]]] = get_records,
        persist_record: Callable[[str, str, Dict[str, Any]], Dict[str, Any]] = update_record,
    ) -> None:
        self.config = config or ScoreAgentConfig()
        self._fetch_records = fetch_records
        self._persist = persist_record

    def score_all(self, limit: int | None = None) -> List[ScoreResult]:
        """Process properties sequentially and return per-record results."""
        effective_limit = limit if limit is not None else self.config.max_records
        results: List[ScoreResult] = []
        for index, record in enumerate(self._iter_records(), start=1):
            if effective_limit is not None and index > effective_limit:
                break
            results.append(self._process_record(record))

        success_count = sum(1 for result in results if result.status == "success")
        failure_count = sum(1 for result in results if result.status == "error")
        log_batch_summary("score_agent", len(results), success_count, failure_count)
        LOGGER.info("ScoreAgent processed %s properties", len(results))
        return results

    def _iter_records(self) -> List[Dict[str, Any]]:
        motivation_field = self.config.target_field
        filter_formula = f"OR({motivation_field} = '', {motivation_field} = BLANK())"
        try:
            records = self._fetch_records(
                self.config.table_name,
                filter_formula=filter_formula,
            )
        except AirtableError as exc:
            LOGGER.exception("Failed to retrieve properties needing scores: %s", exc)
            return []
        if not records:
            LOGGER.info("No properties require motivation scoring at this time")
        return records

    def _process_record(self, record: Dict[str, Any]) -> ScoreResult:
        record_id = record.get("id") or ""
        fields: Dict[str, Any] = record.get("fields", {})
        if not record_id:
            LOGGER.error("Skipping record missing Airtable id: %s", record)
            return ScoreResult(record_id="", score=None, status="error", error="missing_record_id")

        try:
            if self._sold_within_24_months(fields):
                score = 0
                LOGGER.info("Property %s sold within 24 months; assigning score 0", record_id)
            else:
                prompt = self._build_prompt(fields)
                score = self._invoke_model(prompt)
            self._persist_score(record_id, score)
            append_score_log(record_id=record_id, score=score, payload=fields, status="success")
            return ScoreResult(record_id=record_id, score=score, status="success")
        except Exception as exc:
            error_text = str(exc)
            LOGGER.exception("Failed to score record %s: %s", record_id, error_text)
            append_score_log(record_id=record_id, score=None, payload=fields, status="error", error=error_text)
            return ScoreResult(record_id=record_id, score=None, status="error", error=error_text)

    def _build_prompt(self, fields: Dict[str, Any]) -> str:
        property_data = self._format_fields(fields)
        return PROMPT_TEMPLATE.format(property_data=property_data)

    def _invoke_model(self, prompt: str) -> int:
        payload = {"model": self.config.model, "prompt": prompt, "stream": False}
        response = requests.post(
            self.config.ollama_url,
            json=payload,
            timeout=self.config.request_timeout,
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            text_response = data.get("response")
            if not text_response and "error" in data:
                raise RuntimeError(f"Ollama error: {data['error']}")
        else:
            raise RuntimeError("Unexpected Ollama response type")
        return self._parse_score((text_response or "").strip())

    def _parse_score(self, text: str) -> int:
        matches = re.findall(r"\d{1,3}", text)
        if not matches:
            raise ValueError(f"Unable to parse numeric score from: {text!r}")
        for value in matches:
            score = int(value)
            if 0 <= score <= 100:
                return score
        raise ValueError(f"No valid score (0-100) found in: {text!r}")

    def _persist_score(self, record_id: str, score: int) -> None:
        fields = {self.config.target_field: score}
        self._persist(self.config.table_name, record_id, fields)
        LOGGER.info("Updated %s with score %s", record_id, score)

    def _format_fields(self, fields: Dict[str, Any]) -> str:
        ordered_lines: List[str] = []
        seen = set()
        for key in self.config.key_fields:
            if key in fields:
                ordered_lines.append(f"{key}: {self._stringify(fields[key])}")
                seen.add(key)
        for key in sorted(k for k in fields.keys() if k not in seen):
            value = fields[key]
            if value not in (None, ""):
                ordered_lines.append(f"{key}: {self._stringify(value)}")
        return "\n".join(ordered_lines) if ordered_lines else "No property fields provided."

    @staticmethod
    def _stringify(value: Any) -> str:
        if isinstance(value, (list, tuple)):
            return ", ".join(str(item) for item in value if item not in (None, ""))
        if isinstance(value, dict):
            return ", ".join(f"{k}: {v}" for k, v in value.items())
        return str(value)

    def _sold_within_24_months(self, fields: Dict[str, Any]) -> bool:
        sale_date = self._extract_sale_date(fields)
        if not sale_date:
            return False
        delta = datetime.utcnow() - sale_date
        return delta.days <= 730

    def _extract_sale_date(self, fields: Dict[str, Any]) -> Optional[datetime]:
        for key in self.config.sale_date_fields:
            raw_value = fields.get(key)
            if not raw_value:
                continue
            parsed = self._parse_date(raw_value)
            if parsed:
                return parsed
        return None

    @staticmethod
    def _parse_date(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            formats = ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d")
            for fmt in formats:
                try:
                    return datetime.strptime(value[:10], fmt)
                except ValueError:
                    continue
        if hasattr(value, "isoformat"):
            try:
                return datetime.fromisoformat(value.isoformat())
            except (TypeError, ValueError):
                return None
        return None


def main(limit: int | None = None) -> List[ScoreResult]:
    """Entry point for batch scoring, suitable for FastAPI wiring."""

    agent = ScoreAgent()
    return agent.score_all(limit=limit)


__all__ = ["ScoreAgent", "ScoreAgentConfig", "ScoreResult", "main"]
