from __future__ import annotations

from typing import Any


def match_device(
    devices: list[dict[str, Any]],
    identifier: str | int,
    id_keys: tuple[str, ...] = ("device_id", "id"),
    name_keys: tuple[str, ...] = ("name", "room"),
) -> dict[str, Any] | None:
    """
    Find a device dictionary by exact ID, exact name, or fuzzy substring match.
    """
    query = str(identifier).strip().lower()
    if not query:
        return None

    # 1. Exact ID match
    for dev in devices:
        for k in id_keys:
            if k in dev and str(dev[k]).strip().lower() == query:
                return dev

    # 2. Exact name match
    for dev in devices:
        for k in name_keys:
            if k in dev and str(dev[k]).strip().lower() == query:
                return dev

    # 3. Substring match on name or room
    for dev in devices:
        for k in name_keys:
            if k in dev and query in str(dev[k]).strip().lower():
                return dev

    # 4. Token overlap fallback (e.g., "living room tv" -> "Living Room Smart TV")
    query_tokens = set(query.replace("_", " ").split())
    best_match: dict[str, Any] | None = None
    best_score = 0
    for dev in devices:
        haystack = " ".join(str(dev.get(k, "")).lower() for k in (*id_keys, *name_keys))
        hay_tokens = set(haystack.replace("_", " ").split())
        overlap = len(query_tokens & hay_tokens)
        if overlap > best_score and overlap >= max(1, len(query_tokens) - 1):
            best_score = overlap
            best_match = dev

    return best_match