"""Reproducible synthetic-only SEC→Guard judge evidence ZIP.

Six bounded files and a SHA256 manifest, all re-generated from existing
three-scenario offline code. Not a real SEC filing, DAKER submission, or
authenticated agent. ZIP is never extracted to user paths.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

from proofinvest.local_sec_guard_ui import (
    export_synthetic_guard_json,
    export_synthetic_guard_markdown,
    run_synthetic_guard_case,
)

SCHEMA = "proofinvest.synthetic-sec-guard-judge-pack.v1"
MANIFEST = "SYNTHETIC_JUDGE_MANIFEST.json"
CASES = ("matched", "conflict", "script")
MAX_FILE_BYTES = 65536
MAX_ZIP_BYTES = 250000
_EXPECTED_GUARDS = {"matched": "HOLD", "conflict": "REJECT", "script": "HOLD"}


def _json_bytes(value: object) -> bytes:
    return (json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ) + "\n").encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _entry(name: str) -> zipfile.ZipInfo:
    entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    # Stored (uncompressed) ZIP has fixed bytes across zlib/platform versions.
    entry.compress_type = zipfile.ZIP_STORED
    entry.create_system = 3
    entry.external_attr = 0o100644 << 16
    return entry


def build_bytes() -> bytes:
    """Generate exactly 3 validated offline traces, 2 formats each."""
    payload: dict[str, bytes] = {}
    for case in CASES:
        result = run_synthetic_guard_case(case)
        if (result["guard"]["decision"] != _EXPECTED_GUARDS[case]
                or result["audit_chain_valid"] is not True
                or result["limits"]["official_contest_submission"] is not False
                or result["limits"]["external_source_authenticated"] is not False
                or result["limits"]["trade_executed"] is not False):
            raise ValueError("UNSAFE_SYNTHETIC_JUDGE_CASE")
        json_name = case + ".json"
        md_name = case + ".md"
        payload[json_name] = export_synthetic_guard_json(result)
        payload[md_name] = export_synthetic_guard_markdown(result)
    if any(not data or len(data) > MAX_FILE_BYTES for data in payload.values()):
        raise ValueError("SYNTHETIC_JUDGE_FILE_NOT_BOUNDED")
    manifest = {
        "schema": SCHEMA,
        "evidence_class": "SYNTHETIC_ONLY_UNVERIFIED",
        "real_sec_authenticated": False,
        "real_agent_executed": False,
        "trade_executed": False,
        "official_kic_submission": False,
        "file_list": {
            name: {"sha256": _sha(data), "bytes": len(data)}
            for name, data in sorted(payload.items())
        },
        "cases": [
            {"name": case, "guard": _EXPECTED_GUARDS[case]}
            for case in CASES
        ],
    }
    payload[MANIFEST] = _json_bytes(manifest)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        for name in sorted(payload):
            archive.writestr(_entry(name), payload[name])
    packed = out.getvalue()
    if len(packed) > MAX_ZIP_BYTES:
        raise ValueError("SYNTHETIC_JUDGE_ZIP_TOO_LARGE")
    return packed


def verify_bytes(archive: bytes) -> dict:
    """Reject altered bytes, zip bombs, extra paths and stale claims."""
    if type(archive) is not bytes or not 0 < len(archive) <= MAX_ZIP_BYTES:
        raise ValueError("INVALID_SYNTHETIC_JUDGE_ARCHIVE")
    expected = build_bytes()
    if archive != expected:
        raise ValueError("SYNTHETIC_JUDGE_ARCHIVE_MISMATCH")
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        manifest = json.loads(z.read(MANIFEST).decode("utf-8"))
        names = set(z.namelist())
        if (names != set(manifest["file_list"]) | {MANIFEST}
                or manifest["schema"] != SCHEMA
                or manifest["evidence_class"] != "SYNTHETIC_ONLY_UNVERIFIED"
                or any(manifest[key] is not False for key in (
                    "real_sec_authenticated", "real_agent_executed",
                    "trade_executed", "official_kic_submission",
                ))):
            raise ValueError("SYNTHETIC_JUDGE_MANIFEST_INVALID")
        for name, expected_info in manifest["file_list"].items():
            data = z.read(name)
            if expected_info != {"sha256": _sha(data), "bytes": len(data)}:
                raise ValueError("SYNTHETIC_JUDGE_CHECKSUM_MISMATCH")
    return {
        "schema": SCHEMA,
        "status": "SYNTHETIC_JUDGE_PACK_VERIFIED",
        "cases": len(CASES),
        "files": len(manifest["file_list"]),
        "synthetic_only": True,
        "external_source_authenticated": False,
        "official_submission": False,
        "sha256": _sha(archive),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Synthetic SEC→Guard judge ZIP, never real SEC/DAKER evidence"
    )
    parser.add_argument("action", choices=("build", "verify"))
    parser.add_argument("archive", type=Path)
    args = parser.parse_args(argv)
    if args.action == "build":
        # x+b guarantees no replacement of preexisting user archives.
        with args.archive.open("xb") as stream:
            stream.write(build_bytes())
    with args.archive.open("rb") as stream:
        data = stream.read(MAX_ZIP_BYTES + 1)
    print(json.dumps(verify_bytes(data), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
