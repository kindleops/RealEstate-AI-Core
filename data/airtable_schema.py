"""Central Airtable schema definitions and helpers."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, Tuple


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


@dataclass(frozen=True)
class FieldDefinition:
    """Represents an Airtable column with optional env overrides."""

    default: str
    env_vars: Tuple[str, ...] = field(default_factory=tuple)
    options: Tuple[str, ...] = field(default_factory=tuple)
    fallbacks: Tuple[str, ...] = field(default_factory=tuple)

    def resolve(self) -> str:
        """Return the active field name (env override → default)."""
        for env_var in self.env_vars:
            override = _clean(os.getenv(env_var))
            if override:
                return override
        return self.default

    def candidates(self) -> Tuple[str, ...]:
        """Return all candidate names for tolerant lookups."""
        primary_and_fallbacks = (self.resolve(),) + self.fallbacks
        seen: set[str] = set()
        ordered: list[str] = []
        for name in primary_and_fallbacks:
            if not name or name in seen:
                continue
            ordered.append(name)
            seen.add(name)
        return tuple(ordered)


@dataclass(frozen=True)
class TableDefinition:
    """Airtable table metadata with helper accessors."""

    default: str
    env_vars: Tuple[str, ...] = field(default_factory=tuple)
    fields: Dict[str, FieldDefinition] = field(default_factory=dict)

    def name(self) -> str:
        """Resolve the table name (env override → default)."""
        for env_var in self.env_vars:
            override = _clean(os.getenv(env_var))
            if override:
                return override
        return self.default

    def field_name(self, key: str) -> str:
        return self.fields[key].resolve()

    def field_names(self) -> Dict[str, str]:
        return {key: field.resolve() for key, field in self.fields.items()}

    def field_candidates(self) -> Dict[str, Tuple[str, ...]]:
        return {key: field.candidates() for key, field in self.fields.items()}


# ---------------------------------------------------------------------------
# Enumerations / constants
# ---------------------------------------------------------------------------


class ConversationStatus(str, Enum):
    READY = "Ready"
    RESPONDED = "Responded"
    OPT_OUT = "Opt Out"
    FAILED = "Failed"


class ConversationDirection(str, Enum):
    INBOUND = "Inbound"
    OUTBOUND = "Outbound"


class PropertyDealStatus(str, Enum):
    NEW = "New"
    ACTIVE = "Active"
    UNDER_CONTRACT = "Under Contract"
    CLOSED = "Closed"
    SOLD = "Sold"
    DEAD = "Dead"


# ---------------------------------------------------------------------------
# Table definitions used across agents
# ---------------------------------------------------------------------------


PROPERTIES_TABLE = TableDefinition(
    default="Properties",
    env_vars=("PROPERTIES_TABLE",),
    fields={
        "PRIMARY": FieldDefinition(default="Property ID", env_vars=("PROPERTY_PRIMARY_FIELD",), fallbacks=("Property ID", "Record ID")),
        "ADDRESS": FieldDefinition(default="Address", env_vars=("PROPERTY_ADDRESS_FIELD",), fallbacks=("Property Address",)),
        "CITY": FieldDefinition(default="City", env_vars=("PROPERTY_CITY_FIELD",)),
        "STATE": FieldDefinition(default="State", env_vars=("PROPERTY_STATE_FIELD",)),
        "ZIP": FieldDefinition(default="Zip", env_vars=("PROPERTY_ZIP_FIELD",), fallbacks=("Zip Code",)),
        "YEAR_BUILT": FieldDefinition(default="Year Built", env_vars=("PROPERTY_YEAR_BUILT_FIELD",)),
        "BEDS": FieldDefinition(default="Beds", env_vars=("PROPERTY_BEDS_FIELD",)),
        "BATHS": FieldDefinition(default="Baths", env_vars=("PROPERTY_BATHS_FIELD",)),
        "SQUARE_FEET": FieldDefinition(default="Square Feet", env_vars=("PROPERTY_SQFT_FIELD",), fallbacks=("Sqft", "Square Footage")),
        "LOT_SIZE": FieldDefinition(default="Lot Size", env_vars=("PROPERTY_LOT_SIZE_FIELD",)),
        "PROPERTY_TYPE": FieldDefinition(default="Property Type", env_vars=("PROPERTY_TYPE_FIELD",)),
        "VACANCY": FieldDefinition(default="Vacancy", env_vars=("PROPERTY_VACANCY_FIELD",), fallbacks=("Vacant",)),
        "OWNER_TYPE": FieldDefinition(default="Owner Type", env_vars=("PROPERTY_OWNER_TYPE_FIELD",)),
        "OWNERSHIP_LENGTH": FieldDefinition(default="Ownership Length", env_vars=("PROPERTY_OWNERSHIP_LENGTH_FIELD",)),
        "PREFORECLOSURE": FieldDefinition(default="Preforeclosure", env_vars=("PROPERTY_PREFORECLOSURE_FIELD",)),
        "TAX_DELINQUENT": FieldDefinition(default="Tax Delinquent", env_vars=("PROPERTY_TAX_DELINQUENT_FIELD",)),
        "LIENS": FieldDefinition(default="Liens", env_vars=("PROPERTY_LIENS_FIELD",)),
        "AUCTION_DATE": FieldDefinition(default="Auction Date", env_vars=("PROPERTY_AUCTION_DATE_FIELD",)),
        "LAST_SOLD_DATE": FieldDefinition(default="Last Sold Date", env_vars=("PROPERTY_LAST_SOLD_DATE_FIELD",)),
        "LAST_SALE_DATE": FieldDefinition(default="Last Sale Date", env_vars=("PROPERTY_LAST_SALE_DATE_FIELD",), fallbacks=("Last Sale Date",)),
        "LAST_SALE_PRICE": FieldDefinition(default="Last Sale Price", env_vars=("PROPERTY_LAST_SALE_PRICE_FIELD",)),
        "MOTIVATION_SCORE": FieldDefinition(default="Motivation Score", env_vars=("PROPERTY_MOTIVATION_FIELD",)),
        "ESTIMATED_REPAIRS": FieldDefinition(default="Estimated Repairs", env_vars=("PROPERTY_REPAIRS_FIELD",)),
        "ARV": FieldDefinition(default="ARV", env_vars=("PROPERTY_ARV_FIELD",), fallbacks=("After Repair Value",)),
        "SUGGESTED_OFFER": FieldDefinition(default="Suggested Offer", env_vars=("PROPERTY_SUGGESTED_OFFER_FIELD",)),
        "OFFER_TYPE": FieldDefinition(default="Offer Type", env_vars=("PROPERTY_OFFER_TYPE_FIELD",)),
        "DEAL_STATUS": FieldDefinition(
            default="Deal Status",
            env_vars=("PROPERTY_DEAL_STATUS_FIELD",),
            options=tuple(status.value for status in PropertyDealStatus),
        ),
    },
)


CONVERSATIONS_TABLE = TableDefinition(
    default="Conversations",
    env_vars=("CONVERSATIONS_TABLE",),
    fields={
        "PRIMARY": FieldDefinition(default="Conversation ID", env_vars=("CONVERSATION_PRIMARY_FIELD",)),
        "CONTACT_NAME": FieldDefinition(default="Contact Name", env_vars=("CONVERSATION_CONTACT_NAME_FIELD",)),
        "SELLER_PHONE": FieldDefinition(default="Seller Phone Number", env_vars=("CONVERSATION_SELLER_PHONE_FIELD",), fallbacks=("From", "Seller Phone")),
        "TEXTGRID_PHONE": FieldDefinition(default="TextGrid Phone Number", env_vars=("CONVERSATION_TEXTGRID_PHONE_FIELD",), fallbacks=("To", "TextGrid Number")),
        "MESSAGE": FieldDefinition(default="Message", env_vars=("CONVERSATION_MESSAGE_FIELD",), fallbacks=("Incoming Message", "Body")),
        "LAST_MESSAGE": FieldDefinition(default="Last Message", env_vars=("CONVERSATION_LAST_MESSAGE_FIELD",)),
        "STATUS": FieldDefinition(
            default="Status",
            env_vars=("CONVERSATION_STATUS_FIELD",),
            options=tuple(status.value for status in ConversationStatus),
            fallbacks=("Delivery Status",),
        ),
        "DIRECTION": FieldDefinition(
            default="Direction",
            env_vars=("CONVERSATION_DIRECTION_FIELD",),
            options=tuple(direction.value for direction in ConversationDirection),
            fallbacks=("Last Direction",),
        ),
    },
)


MODEL_LOGS_TABLE = TableDefinition(
    default="Model Logs",
    env_vars=("MODEL_LOGS_TABLE",),
    fields={
        "AGENT": FieldDefinition(default="Agent", env_vars=("MODEL_LOG_AGENT_FIELD",)),
        "SUMMARY": FieldDefinition(default="Summary", env_vars=("MODEL_LOG_SUMMARY_FIELD",)),
        "BEFORE": FieldDefinition(default="Before", env_vars=("MODEL_LOG_BEFORE_FIELD",)),
        "AFTER": FieldDefinition(default="After", env_vars=("MODEL_LOG_AFTER_FIELD",)),
    },
)


# Convenience helpers -------------------------------------------------------


def properties_field_map() -> Dict[str, str]:
    return PROPERTIES_TABLE.field_names()


def conversations_field_map() -> Dict[str, str]:
    return CONVERSATIONS_TABLE.field_names()


def model_logs_field_map() -> Dict[str, str]:
    return MODEL_LOGS_TABLE.field_names()


__all__ = [
    "FieldDefinition",
    "TableDefinition",
    "ConversationStatus",
    "ConversationDirection",
    "PropertyDealStatus",
    "PROPERTIES_TABLE",
    "CONVERSATIONS_TABLE",
    "MODEL_LOGS_TABLE",
    "properties_field_map",
    "conversations_field_map",
    "model_logs_field_map",
]
