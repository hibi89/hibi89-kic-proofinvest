"""Bounded in-session archive for independently verified, redacted reports.

Only caller-prevalidated JSON bytes and SHA256 fingerprints are accepted.
No raw SEC/vendor response, API key, file path or persistent storage is used.
This cache is *not* an authority on SEC provenance or legal data rights.
"""
from __future__ import annotations

import re
from typing import Any

HISTORY_KEY = "kuodra_p156_linked_report_history"
LATEST_KEY = "kuodra_p153_linked_report_cache"
MAX_ENTRIES = 16
MAX_BYTES = 16384
_SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)


def _valid(entry: Any) -> bool:
    return (type(entry) is dict
            and set(entry) == {"fingerprint", "data"}
            and type(entry["fingerprint"]) is str
            and _SHA.fullmatch(entry["fingerprint"]) is not None
            and type(entry["data"]) is bytes
            and 0 < len(entry["data"]) <= MAX_BYTES)


def _history(state: Any) -> list[dict[str, Any]] | None:
    try:
        history = state.get(HISTORY_KEY, [])
        if (type(history) is not list or len(history) > MAX_ENTRIES
                or any(not _valid(entry) for entry in history)
                or len({entry["fingerprint"] for entry in history}) != len(history)):
            return None
        return history
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def keep_linked_report(state: Any, fingerprint: Any, data: Any) -> bool:
    """Keep up to 16 redacted JSON receipts, replacing same-input versions.

    The calling UI MUST independently replay source and market maths and call
    linked_evidence_json_bytes before invoking this store. Source validation
    happens AGAIN at display time; a session cache alone cannot prove it.
    """
    entry = {"fingerprint": fingerprint, "data": data}
    if state is None or not _valid(entry):
        return False
    try:
        history = _history(state)
        if history is None:
            # Fail closed for corrupt history, but allow a new verified report
            # to start a fresh bounded archive.
            state.pop(HISTORY_KEY, None)
            history = []
        history = [item for item in history
                   if item["fingerprint"] != fingerprint]
        history.append(entry)
        state[HISTORY_KEY] = history[-MAX_ENTRIES:]
        state[LATEST_KEY] = entry
        return True
    except (AttributeError, KeyError, TypeError, ValueError):
        return False


def find_linked_report(state: Any, fingerprint: Any) -> dict[str, Any] | None:
    """Find only the exact upload-bound record; NEVER return a loose match."""
    if (state is None or type(fingerprint) is not str
            or _SHA.fullmatch(fingerprint) is None):
        return None
    history = _history(state)
    if history is None:
        try:
            state.pop(HISTORY_KEY, None)
        except (AttributeError, TypeError):
            pass
        return None
    return next((entry for entry in reversed(history)
                 if entry["fingerprint"] == fingerprint), None)


def discard_linked_report(state: Any, fingerprint: Any) -> None:
    """Revoke one corrupted receipt, leaving other valid inputs unaffected."""
    if state is None:
        return
    try:
        latest = state.get(LATEST_KEY)
        if type(latest) is not dict or latest.get("fingerprint") == fingerprint:
            state.pop(LATEST_KEY, None)
        history = _history(state)
        if history is None:
            state.pop(HISTORY_KEY, None)
        else:
            state[HISTORY_KEY] = [
                entry for entry in history if entry["fingerprint"] != fingerprint
            ]
    except (AttributeError, TypeError, KeyError):
        return


def clear_linked_reports(state: Any) -> None:
    """Explicit rights-off and invalid-approval boundary: remove all exports."""
    if state is None:
        return
    try:
        state.pop(LATEST_KEY, None)
        state.pop(HISTORY_KEY, None)
    except (AttributeError, TypeError):
        pass
