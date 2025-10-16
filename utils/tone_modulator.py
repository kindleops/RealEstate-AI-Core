"""Utilities for modulating the tone of outbound communications."""

from __future__ import annotations

from typing import Dict


class ToneModulator:
    """Apply simple tone adjustments to text snippets."""

    TONE_PREFIXES: Dict[str, str] = {
        "casual": "Hey there!",
        "urgent": "Important update:",
        "professional": "Good afternoon,",
        "friendly": "Hi friend!",
    }

    def modulate(self, message: str, tone: str) -> str:
        tone = tone.lower()
        prefix = self.TONE_PREFIXES.get(tone)
        if prefix:
            return f"{prefix} {message}"
        return message


__all__ = ["ToneModulator"]

