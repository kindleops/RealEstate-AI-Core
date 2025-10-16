"""Utilities for selecting the appropriate model for a given task."""

from __future__ import annotations

from typing import Any, Mapping, Optional

DEFAULT_MODEL_MAP = {
    "sms": "phi3",
    "comps": "mistral",
}

FALLBACK_MODEL = "gpt-4o"
DEFAULT_MAX_INPUT_LENGTH = 4000


def _resolve_task_type(task: Optional[Any]) -> Optional[str]:
    """Extract the task type from dictionaries or objects.

    The selector is intentionally forgiving so tests and runtime code can
    provide a light-weight ``task`` representation (``dict`` or an object with
    a ``type`` attribute).
    """

    if task is None:
        return None

    if isinstance(task, Mapping):
        raw_type = task.get("type")
        return str(raw_type) if raw_type is not None else None

    task_type = getattr(task, "type", None)
    return str(task_type) if task_type is not None else None


def select_model(
    task: Optional[Any],
    input_text: str,
    *,
    max_input_length: int = DEFAULT_MAX_INPUT_LENGTH,
) -> str:
    """Return the best model identifier for the supplied task.

    Args:
        task: A mapping or lightweight object describing the task. The
            selector expects a ``type`` key/attribute.
        input_text: Raw text that will be sent to the model.
        max_input_length: Maximum number of characters allowed before falling
            back to :data:`FALLBACK_MODEL`.

    Returns:
        The identifier of the model that should process the request.
    """

    if len(input_text or "") > max_input_length:
        return FALLBACK_MODEL

    task_type = _resolve_task_type(task)
    if not task_type:
        return FALLBACK_MODEL

    return DEFAULT_MODEL_MAP.get(task_type.lower(), FALLBACK_MODEL)


__all__ = ["select_model", "DEFAULT_MODEL_MAP", "FALLBACK_MODEL", "DEFAULT_MAX_INPUT_LENGTH"]
