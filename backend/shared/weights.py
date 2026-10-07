"""Validate confidence values before they become Neo4j relationship weights."""

import math


def normalize_weight(value):
    """Accept numeric JSON values/strings, but never invent a confidence score."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("confidence must be a finite number between 0 and 1")
    try:
        weight = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError("confidence must be a finite number between 0 and 1") from exc
    if not math.isfinite(weight) or not 0.0 <= weight <= 1.0:
        raise ValueError("confidence must be a finite number between 0 and 1")
    return weight


def normalize_suggestions(items, default):
    """Copy and validate the whole batch before any graph writes can start."""
    return [dict(item, confidence=normalize_weight(item.get("confidence", default)))
            for item in items]


def normalize_entities(entities):
    return {kind: normalize_suggestions(items, 0.5 if kind == "concepts" else 1.0)
            for kind, items in entities.items()}
