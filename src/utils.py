from __future__ import annotations

import re
import unicodedata


def parse_duration_to_seconds(value: str) -> int | None:
    if not value:
        return None
    parts = [p for p in value.strip().split(":") if p.isdigit()]
    if len(parts) == 2:
        minutes, seconds = map(int, parts)
        return minutes * 60 + seconds
    if len(parts) == 3:
        hours, minutes, seconds = map(int, parts)
        return hours * 3600 + minutes * 60 + seconds
    return int(parts[0]) if len(parts) == 1 else None


def parse_view_count(value: str) -> int | None:
    if not value:
        return None
    normalized = value.strip().replace(",", "").lower()
    multiplier = 1
    if normalized.endswith("k"):
        multiplier = 1_000
        normalized = normalized[:-1]
    elif normalized.endswith("m"):
        multiplier = 1_000_000
        normalized = normalized[:-1]
    elif normalized.endswith("b"):
        multiplier = 1_000_000_000
        normalized = normalized[:-1]
    try:
        return int(float(normalized) * multiplier)
    except ValueError:
        return None


def normalize_text(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value)
    ascii_text = folded.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", ascii_text)
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def split_terms(value: str | None) -> list[str]:
    if not value:
        return []
    return [term for term in normalize_text(value).split(" ") if term]
