"""Bounded per-session duplicate protection for explicitly approved market calls.

This local state ledger is not durable billing proof or a cross-session lock.
It never stores provider keys, HTTP response bodies or caller source files.
"""
from __future__ import annotations

import re
from typing import Any

_HISTORY_KEY = "kuodra_p155_pair_attempt_history"
_LEGACY_KEY = "kuodra_p141_pair_attempt"
_MAX_HISTORY = 64
_SHA256 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)


def register_premium_pair_attempt(state: Any, fingerprint: Any) -> str:
    """Record a distinct request BEFORE calling any paid provider.

    Returns NEW, DUPLICATE, or INVALID. In a real Streamlit session the
    ledger preserves the latest 64 distinct source fingerprints. A fresh
    session has no history; no claim of cross-session billing deduplication.
    """
    if type(fingerprint) is not str or _SHA256.fullmatch(fingerprint) is None:
        return "INVALID"
    if state is None:
        return "NEW"  # Preserve simple Streamlit-compatible test doubles.
    try:
        history = state.get(_HISTORY_KEY, [])
        if (type(history) is not list or len(history) > _MAX_HISTORY
                or any(type(item) is not str or _SHA256.fullmatch(item) is None
                       for item in history)
                or len(history) != len(set(history))):
            return "INVALID"  # Do not issue a paid request with corrupt state.
        if fingerprint in history or state.get(_LEGACY_KEY) == fingerprint:
            return "DUPLICATE"
        # The old single-attempt marker is retained for pre-P155 sessions.
        state[_HISTORY_KEY] = history[-(_MAX_HISTORY - 1):] + [fingerprint]
        state[_LEGACY_KEY] = fingerprint
        return "NEW"
    except (AttributeError, KeyError, TypeError, ValueError):
        return "INVALID"
