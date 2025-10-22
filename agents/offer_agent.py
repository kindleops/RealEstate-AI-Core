"""Agent responsible for generating cash or creative offers for properties."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

from agents.comps_agent import CompsAgent
from data.airtable_client import AirtableError, get_records, update_record
from data.logger import log_agent_event, log_batch_summary
from logger import get_logger

LOGGER = get_logger()


@dataclass
class OfferAgentConfig:
    default_margin: float = 0.7
    table_name: str = "Properties"
    motivation_field: str = "Motivation Score"
    arv_field: str = "ARV"
    repairs_field: str = "Estimated Repairs"
    offer_field: str = "Suggested Offer"
    offer_type_field: str = "Offer Type"
    motivation_threshold: int = 70
    ollama_url: str = "http://localhost:11434/api/generate"
    model_name: str = "mistral:7b"
    request_timeout: int = 90


@dataclass
class OfferAgentResult:
    record_id: str
    status: str
    offer: Optional[float] = None
    offer_type: Optional[str] = None
    error: Optional[str] = None


class OfferAgent:
    """Compute AI-assisted offer guidance for motivated sellers."""

    def __init__(self, config: OfferAgentConfig | None = None, comps_agent: Optional[CompsAgent] = None) -> None:
        self.config = config or OfferAgentConfig()
        self.comps_agent = comps_agent or CompsAgent()

    def calculate_offer(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        arv = payload.get("arv")
        repairs = float(payload.get("repairs", 0) or 0)
        margin = float(payload.get("margin", self.config.default_margin))

        comps_result = None
        if arv is None:
            LOGGER.info("ARV missing, invoking comps agent")
            comps_result = self.comps_agent.generate_comps(payload)
            arv = comps_result.get("arv")

        arv = float(arv or 0)
        offer_price = max((arv * margin) - repairs, 0)

        result: Dict[str, Any] = {
            "arv": arv,
            "repairs": repairs,
            "margin": margin,
            "offer_price": round(offer_price, 2),
            "arv_source": "comps_agent" if comps_result else "payload",
        }
        if comps_result:
            result["comps"] = comps_result.get("comps", [])
        return result

    def process_motivated_properties(self, limit: Optional[int] = None) -> List[OfferAgentResult]:
        filter_formula = f"{{{self.config.motivation_field}}} >= {self.config.motivation_threshold}"
        try:
            records = get_records(self.config.table_name, filter_formula=filter_formula)
        except AirtableError as exc:
            LOGGER.exception("Failed to fetch motivated properties: %s", exc)
            return []

        results: List[OfferAgentResult] = []
        for record in records:
            if limit is not None and len(results) >= limit:
                break
            results.append(self._process_record(record))

        success_count = sum(1 for item in results if item.status == "success")
        failure_count = sum(1 for item in results if item.status == "error")
        log_batch_summary("offer_agent", len(results), success_count, failure_count)
        LOGGER.info("OfferAgent processed %s records", len(results))
        return results

    def _process_record(self, record: Dict[str, Any]) -> OfferAgentResult:
        record_id = record.get("id", "")
        fields: Dict[str, Any] = record.get("fields", {})
        if not record_id:
            LOGGER.error("Skipping property without record id: %s", record)
            return OfferAgentResult(record_id="", status="error", error="missing_record_id")

        payload = self._build_payload(fields)
        try:
            offer_details = self._generate_offer(fields, payload)
            update_record(
                self.config.table_name,
                record_id,
                {
                    self.config.offer_field: offer_details["suggested_offer"],
                    self.config.offer_type_field: offer_details["offer_type"],
                },
            )
        except Exception as exc:
            error_text = str(exc)
            LOGGER.exception("Failed to compute offer for %s: %s", record_id, error_text)
            log_agent_event(
                "offer_agent",
                record_id,
                "error",
                payload=fields,
                result=payload,
                error=error_text,
            )
            return OfferAgentResult(record_id=record_id, status="error", error=error_text)

        log_agent_event(
            "offer_agent",
            record_id,
            "success",
            payload=fields,
            result=offer_details,
        )
        return OfferAgentResult(
            record_id=record_id,
            status="success",
            offer=offer_details["suggested_offer"],
            offer_type=offer_details["offer_type"],
        )

    def _build_payload(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "address": fields.get("Address"),
            "zip": fields.get("Zip"),
            "beds": fields.get("Beds"),
            "baths": fields.get("Baths"),
            "sqft": fields.get("Square Feet"),
            "arv": fields.get(self.config.arv_field),
            "repairs": fields.get(self.config.repairs_field),
            "motivation": fields.get(self.config.motivation_field),
        }

    def _generate_offer(self, fields: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        base_offer = self.calculate_offer(payload)
        prompt = (
            "You are a real estate acquisitions analyst. Recommend the best offer strategy for this property. "
            "Respond with JSON containing keys 'offer_type' (cash or creative) and 'suggested_offer' (number)."
        )
        property_lines = [f"{key}: {value}" for key, value in fields.items() if value not in (None, "")]
        prompt += "\n\nProperty Details:\n" + "\n".join(property_lines)
        prompt += (
            "\n\nBaseline analysis:\n"
            f"Calculated cash offer: {base_offer['offer_price']}\n"
            f"ARV used: {base_offer['arv']}\n"
            f"Repairs estimate: {base_offer['repairs']}"
        )

        try:
            response_text = self._invoke_model(prompt)
            data = json.loads(response_text)
            suggested_offer = float(data.get("suggested_offer", base_offer["offer_price"]))
            offer_type = str(data.get("offer_type", "cash")).lower()
        except (json.JSONDecodeError, ValueError, TypeError, RuntimeError) as exc:
            LOGGER.warning("Model response parsing failed; defaulting to baseline: %s", exc)
            suggested_offer = base_offer["offer_price"]
            offer_type = "cash"

        return {
            "suggested_offer": round(suggested_offer, 2),
            "offer_type": offer_type.title(),
            "baseline": base_offer,
        }

    def _invoke_model(self, prompt: str) -> str:
        payload = {"model": self.config.model_name, "prompt": prompt, "stream": False}
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


__all__ = ["OfferAgent", "OfferAgentConfig", "OfferAgentResult"]
