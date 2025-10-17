"""Utility helpers shared across agent endpoints."""

from __future__ import annotations

from typing import Iterable, Optional


def clamp_score(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    """Clamp a numeric score between the provided bounds."""

    return max(minimum, min(maximum, value))


def safe_divide(numerator: float, denominator: float, fallback: float = 0.0) -> float:
    """Safely divide two numbers and return a fallback when the denominator is zero."""

    if denominator == 0:
        return fallback
    return numerator / denominator


def average(values: Iterable[float]) -> Optional[float]:
    """Return the arithmetic mean for an iterable of values."""

    total = 0.0
    count = 0
    for value in values:
        total += value
        count += 1
    if count == 0:
        return None
    return total / count


def motivation_to_scalar(level: Optional[str]) -> float:
    """Map human readable motivation levels to numeric scalars."""

    if not level:
        return 0.0
    normalized = level.strip().lower()
    mapping = {
        "low": 0.2,
        "medium": 0.5,
        "moderate": 0.5,
        "high": 0.8,
        "urgent": 1.0,
        "very high": 0.9,
    }
    return mapping.get(normalized, 0.4)
