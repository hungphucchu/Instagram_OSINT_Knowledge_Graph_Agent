"""Shared semantics for `CollectionRunConfig.max_items`."""

from __future__ import annotations


def clamp_fetch_count(total_available: int, max_items: int) -> int:
    """`max_items <= 0` means use all available items; otherwise cap at `max_items`."""
    if max_items <= 0:
        return total_available
    return min(max_items, total_available)
