"""Build and verify a public, synthetic-only offline demo recovery artifact.

The explicit allowlist prevents accidental export of private PDF/PPTX,
secrets, personal records or mutable local caches. This archive proves
reproducibility, not DAKER submission or actual filing authentication.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "proofinvest.synthetic-demo-recovery.v1"
MANIFEST = "SYNTHETIC_DEMO_MANIFEST.json"
SOURCES = (
    "README.md",
    "requirements-ui.txt",
    "streamlit_app.py",
    "fixtures/synthetic_annual.json",
    "proofinvest/__init__.py",
    "proofinvest/__main__.py",
    "proofinvest/dart_adapter.py",
    "proofinvest/engine.py",
    "proofinvest/evidence_scenarios.py",
    "proofinvest/offline_view.py",
    "proofinvest/peers.py",
    "proofinvest/research.py",
    "proofinvest/risk.py",
    "proofinvest/snapshot_store.py",
)
MAX_BYTES = 2_000_000
MAX_TOTAL_BYTES = 5_000_000


def _json(data: object) -> bytes:
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def _entry(name: str, data: bytes) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def build_bytes() -> bytes:
    payload: dict[str, bytes] = {}
    for rel in SOURCES:
        path = ROOT / rel
        if path.is_symlink() or not path.is_file():
            raise ValueError("Missing or symlinked allowlisted file: " + rel)
        data = path.read_bytes()
        if len(data) > MAX_BYTES:
            raise ValueError("Oversize source file: " + rel)
        payload[rel] = data
    if sum(map(len, payload.values())) > MAX_TOTAL_BYTES:
        raise ValueError("Synthetic bundle exceeds maximum size")
    manifest = {
        "schema": SCHEMA,
        "purpose": "offline_synthetic_code_recovery_only",
        "source_kind": "SYNTHETIC_FIXTURE",
        "officially_submitted": False,
        "authenticated_external_source": False,
        "live_api_called": False,
        "files": {key: {"sha256": _sha(value), "bytes": len(value)} for key, value in sorted(payload.items())},
    }
    payload[MANIFEST] = _json(manifest)
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w") as dest:
        for name in sorted(payload):
            dest.writestr(_entry(name, payload[name]), payload[name])
    return memory.getvalue()


def read_verified(archive: Path) -> dict[str, bytes]:
    """Verify every path/entry/hash before extracting any bytes."""
    with zipfile.ZipFile(archive) as z:
        info = z.infolist()
        expected = sorted((*SOURCES, MANIFEST))
        if sorted(item.filename for item in info) != expected:
            raise ValueError("Bundle contains missing, duplicate, or unapproved paths")
        if any(
            item.is_dir()
            or item.flag_bits & 1
            or item.file_size > MAX_BYTES
            or (item.external_attr >> 16) & 0o170000 != 0o100000
            for item in info
        ):
            raise ValueError("Bundle has invalid entry type, encrypted content, or oversize file")
        if sum(item.file_size for item in info) > MAX_TOTAL_BYTES:
            raise ValueError("Bundle is too large")
        content = {item.filename: z.read(item) for item in info}
    record = json.loads(content.pop(MANIFEST).decode("utf-8"))
    if not isinstance(record, dict) or set(record) != {
        "schema", "purpose", "source_kind", "officially_submitted",
        "authenticated_external_source", "live_api_called", "files",
    }:
        raise ValueError("Invalid recovery manifest schema")
    if (
        record["schema"] != SCHEMA
        or record["purpose"] != "offline_synthetic_code_recovery_only"
        or record["source_kind"] != "SYNTHETIC_FIXTURE"
        or record["officially_submitted"] is not False
        or record["authenticated_external_source"] is not False
        or record["live_api_called"] is not False
        or not isinstance(record["files"], dict)
        or set(record["files"]) != set(SOURCES)
    ):
        raise ValueError("Recovery manifest does not identify a synthetic-only demo")
    for name, data in content.items():
        if record["files"][name] != {"sha256": _sha(data), "bytes": len(data)}:
            raise ValueError("Recovery content checksum mismatch: " + name)
    return content


def extract_verified(archive: Path, target: Path) -> None:
    files = read_verified(archive)
    if target.exists() or target.is_symlink():
        raise ValueError("Recovery destination must not exist; no overwrite allowed")
    # Target is explicitly supplied; nested paths exclusively from the fixed allowlist.
    target.mkdir()
    try:
        for rel, data in files.items():
            destination = target / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
    except BaseException:
        # Leave partially extracted result clearly incomplete for inspection.
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Public synthetic-only demo archive utility")
    subs = parser.add_subparsers(dest="command", required=True)
    for cmd in ("build", "verify", "extract"):
        sub = subs.add_parser(cmd)
        sub.add_argument("archive", type=Path)
        if cmd == "extract":
            sub.add_argument("destination", type=Path)
    args = parser.parse_args()
    if args.command == "build":
        if args.archive.exists() or args.archive.is_symlink():
            raise ValueError("Archive already exists; refusing to overwrite")
        args.archive.parent.mkdir(parents=True, exist_ok=True)
        args.archive.write_bytes(build_bytes())
        print("CREATED_PUBLIC_SYNTHETIC_ARCHIVE")
    elif args.command == "verify":
        payload = read_verified(args.archive)
        print("VERIFIED_PUBLIC_SYNTHETIC_ARCHIVE", len(payload))
    else:
        extract_verified(args.archive, args.destination)
        print("EXTRACTED_VERIFIED_SYNTHETIC_ARCHIVE")


if __name__ == "__main__":
    main()
