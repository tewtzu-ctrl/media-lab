"""Shared checks for caller-supplied arguments.

Every recipe validates the same shapes, so the rules and the wording live in
one place rather than being restated per module.
"""

from __future__ import annotations

from collections.abc import Sequence

from .errors import ValidationError


def check_range(value: float, low: float, high: float, label: str) -> float:
    """Confirm a number sits within an inclusive range."""
    if not low <= value <= high:
        raise ValidationError(f"{label} must be between {low} and {high}, got {value}")
    return value


def check_choice(value: str, allowed: Sequence[str], label: str) -> str:
    """Confirm a string is one of a fixed set."""
    if value not in allowed:
        raise ValidationError(f"{label} must be one of {', '.join(allowed)}, got {value!r}")
    return value
