"""Explicit, local-only snapshot storage for bundled synthetic ProofInvest data.

Saving is opt-in; loading never invokes calculation, a network adapter, or
Streamlit. A SHA-256 is a corruption check, NOT source authenticity or
authorization. Never store real issuer records or credentials through this API.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .offline_view import _FIXTURE, load_synthetic_snapshot

_FILE_NAME = "synthetic_snapshot_v1.json"
_FORMAT = "proofinvest.synthetic_snapshot.v1"
_REPO_ROOT = Path(__file__).resolve().parents[1]


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _cache_path(directory: Path) -> Path:
    path = Path(directory).expanduser()
    if not path.is_dir() or path.is_symlink():
        raise ValueError("Explicit cache directory must exist and must not be a symlink")
    resolved = path.resolve()
    if resolved == _REPO_ROOT or _REPO_ROOT in resolved.parents:
        raise ValueError("Refusing to save a snapshot inside the public source repository")
    return resolved / _FILE_NAME


def _fixture_digest() -> str:
    return hashlib.sha256(_FIXTURE.read_bytes()).hexdigest()


def _validate_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {
        "mode", "source_kind", "year", "authenticated_external_source",
        "live_api_called", "financial_rows", "checks", "risk",
    }:
        raise ValueError("Unexpected stored view schema")
    if (
        payload.get("mode") != "OFFLINE_SYNTHETIC_READ_ONLY"
        or payload.get("source_kind") != "SYNTHETIC_FIXTURE"
        or type(payload.get("year")) is not int
        or payload["year"] != 2024
        or payload.get("authenticated_external_source") is not False
        or payload.get("live_api_called") is not False
        or not isinstance(payload.get("financial_rows"), list)
        or not payload["financial_rows"]
        or not isinstance(payload.get("checks"), list)
        or len(payload["checks"]) != 1
        or not isinstance(payload.get("risk"), dict)
        or payload["risk"].get("실제 원문 인증") != "아니오"
        or payload["checks"][0].get("실제 원문 인증") != "아니오"
        or any(
            not isinstance(row, dict)
            or set(row) != {"계정", "범위", "당기 금액 (KRW)", "전기 금액 (KRW)"}
            or row["범위"] not in ("CFS", "OFS")
            for row in payload["financial_rows"]
        )
    ):
        raise ValueError("Stored view is not a synthetic, unverified demo")
    return payload


def read_synthetic_snapshot(directory: Path) -> dict[str, Any]:
    """Return checked stored data without recomputing; fail closed on changes."""
    target = _cache_path(directory)
    if target.is_symlink():
        raise ValueError("Snapshot cannot be a symlink")
    try:
        envelope = json.loads(target.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Snapshot missing or corrupt; not recomputed") from exc
    if not isinstance(envelope, dict) or set(envelope) != {
        "format", "fixture_sha256", "payload_sha256", "payload"
    } or envelope["format"] != _FORMAT:
        raise ValueError("Unsupported snapshot envelope")
    if envelope["fixture_sha256"] != _fixture_digest():
        raise ValueError("Bundled fixture changed; stale snapshot rejected")
    payload = envelope["payload"]
    if hashlib.sha256(_canonical(payload)).hexdigest() != envelope["payload_sha256"]:
        raise ValueError("Snapshot checksum mismatch")
    return _validate_payload(payload)


def save_synthetic_snapshot(directory: Path) -> str:
    """Explicit create-only save; repeated saves reuse without recalculation.

    Caller must create a private directory outside this public repository.
    Invalid or stale existing data is rejected, never silently overwritten.
    """
    target = _cache_path(directory)
    if target.exists() or target.is_symlink():
        read_synthetic_snapshot(directory)
        return "REUSED_NO_RECALCULATION"
    before = _fixture_digest()
    payload = _validate_payload(load_synthetic_snapshot())
    after = _fixture_digest()
    if before != after:
        raise ValueError("Bundled fixture changed during snapshot calculation")
    envelope = {
        "format": _FORMAT,
        "fixture_sha256": after,
        "payload_sha256": hashlib.sha256(_canonical(payload)).hexdigest(),
        "payload": payload,
    }
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(target, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(_canonical(envelope) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return "CREATED"


def main() -> None:
    parser = argparse.ArgumentParser(description="Local synthetic-only create/read snapshot (no API)")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--save", action="store_true", help="Explicitly save once, or reuse")
    action.add_argument("--read", action="store_true", help="Load already saved; never recalculate")
    args = parser.parse_args()
    directory = Path.home() / ".proofinvest-synthetic-cache"
    if args.save:
        directory.mkdir(mode=0o700, exist_ok=True)
        state = save_synthetic_snapshot(directory)
    else:
        state = "READ_NO_RECALCULATION"
    view = read_synthetic_snapshot(directory)
    print(json.dumps({
        "status": state,
        "mode": view["mode"],
        "source_kind": view["source_kind"],
        "authenticated_external_source": False,
        "risk_display_pct": view["risk"]["표시 비율"],
        "year": view["year"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
