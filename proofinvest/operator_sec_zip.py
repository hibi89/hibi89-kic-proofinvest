"""Strict in-memory intake for an operator-assembled SEC-shaped 3-source ZIP.

Distinct from sec_capture_bundle (which records actual attempted HTTP).
ZIP validation proves local SHA and claimed issuer metadata ONLY, never an
HTTP transfer, SEC provider authenticity, license, point-in-time vintage,
filing truth, audit retention, or contest submission. No extraction to disk.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any
import zipfile

from disclosure_lightning.core import MAX_JSON_BYTES
from disclosure_lightning.originals import MAX_FILING_BYTES
from .local_sec_packet import _MAX_FILE_BYTES, _json_object, _read_regular_local

_SCHEMA = "kuodra.operator-three-sec-source-zip.v1"
_PARTS = (
    ("submissions", "submissions.json", MAX_JSON_BYTES),
    ("companyfacts", "companyfacts.json", _MAX_FILE_BYTES),
    ("original_filing", "original_filing.bin", MAX_FILING_BYTES),
)
_NAMES = frozenset({"manifest.json", *(name for _, name, _ in _PARTS)})
_MAX_ZIP_BYTES = sum(limit for _, _, limit in _PARTS) + 32_768
_CIK = re.compile(r"[0-9]{10}\Z", re.ASCII)
_ACC = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}\Z", re.ASCII)
_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:Z|\+00:00)\Z",
    re.ASCII,
)
_SHA = re.compile(r"[a-f0-9]{64}\Z", re.ASCII)


def _claims_valid(claims: Any) -> bool:
    if type(claims) is not dict or set(claims) != {
        "issuer_cik", "accession", "as_of", "collected_at",
    }:
        return False
    cik, accession = claims["issuer_cik"], claims["accession"]
    day, stamp = claims["as_of"], claims["collected_at"]
    if (type(cik) is not str or not _CIK.fullmatch(cik)
            or cik == "0000000000" or type(accession) is not str
            or not _ACC.fullmatch(accession)
            or type(day) is not str or type(stamp) is not str
            or not _TIMESTAMP.fullmatch(stamp)):
        return False
    try:
        parsed_day = date.fromisoformat(day)
        when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        return (parsed_day.isoformat() == day
                and when.utcoffset() is not None
                and when.utcoffset().total_seconds() == 0
                and when.astimezone(timezone.utc).date() == parsed_day)
    except (ValueError, TypeError, OverflowError):
        return False


def _input_identity(raws: dict[str, bytes], cik: str) -> bool:
    """Basic same-issuer consistency only; never assert original affiliation."""
    try:
        for key, limit in (("submissions", MAX_JSON_BYTES),
                           ("companyfacts", _MAX_FILE_BYTES)):
            data = _json_object(raws[key], limit=limit)
            identity = data.get("cik")
            if (type(identity) not in (int, str) or type(identity) is bool
                    or not str(identity).isascii()
                    or not str(identity).isdecimal()
                    or not 0 < int(identity) < 10**10
                    or str(int(identity)).zfill(10) != cik):
                return False
        return True
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return False


def _manifest_for(raws: dict[str, bytes], claims: dict[str, str]) -> dict:
    return {
        "schema": _SCHEMA,
        "operator_claims": dict(claims),
        "entries": {
            key: {
                "name": name, "size": len(raws[key]),
                "sha256": sha256(raws[key]).hexdigest(),
            }
            for key, name, _ in _PARTS
        },
        "origin_authenticated": False,
        "source_rights_verified": False,
        "transport_http_performed": False,
        "official_submission": False,
        "note": "Self-assembled offline source ZIP: SHA is NOT SEC issuer authentication.",
    }


def _serialized_manifest(manifest: dict) -> bytes:
    return json.dumps(
        manifest, sort_keys=True, ensure_ascii=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("ascii")


def make_operator_sec_zip_bytes(
    *, submissions: bytes, companyfacts: bytes, original_filing: bytes,
    issuer_cik: str, accession: str, as_of: str, collected_at: str,
) -> bytes:
    """Create exact-format ZIP in memory; never saves any original by itself."""
    claims = {
        "issuer_cik": issuer_cik, "accession": accession,
        "as_of": as_of, "collected_at": collected_at,
    }
    raws = {
        "submissions": submissions, "companyfacts": companyfacts,
        "original_filing": original_filing,
    }
    if (not _claims_valid(claims)
            or any(type(raws[key]) is not bytes or not 0 < len(raws[key]) <= limit
                   for key, _, limit in _PARTS)
            or not _input_identity(raws, issuer_cik)):
        raise ValueError("OPERATOR_ZIP_BAD_METADATA_OR_INPUTS")
    manifest = _serialized_manifest(_manifest_for(raws, claims))
    if len(manifest) > 4_096:
        raise ValueError("OPERATOR_ZIP_MANIFEST_TOO_LONG")
    with BytesIO() as output:
        with zipfile.ZipFile(
            output, "w", compression=zipfile.ZIP_STORED, allowZip64=False,
        ) as archive:
            for name, raw in (
                ("manifest.json", manifest),
                *((name, raws[key]) for key, name, _ in _PARTS),
            ):
                entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_STORED
                entry.external_attr = (stat.S_IFREG | 0o600) << 16
                archive.writestr(entry, raw)
        packed = output.getvalue()
    if len(packed) > _MAX_ZIP_BYTES:
        raise ValueError("OPERATOR_ZIP_SIZE_EXCEEDED")
    return packed


def read_operator_sec_zip_bytes(blob: bytes) -> tuple[dict[str, bytes], dict]:
    """Read a four-entry stored ZIP, with exact manifest, names, size and SHA.

    No ZipFile.extract, filesystem writes, decompression, scripts or HTML
    evaluation. Per-item limits are checked BEFORE archive.read.
    """
    if (type(blob) is not bytes or not 0 < len(blob) <= _MAX_ZIP_BYTES
            or not blob.startswith(b"PK\x03\x04")):
        raise ValueError("OPERATOR_ZIP_BAD_ARCHIVE_SIZE")
    try:
        with zipfile.ZipFile(BytesIO(blob), "r", allowZip64=False) as archive:
            entries = archive.infolist()
            limits = {name: cap for _, name, cap in _PARTS}
            limits["manifest.json"] = 4_096
            if (archive.comment
                    or len(entries) != len(_NAMES)
                    or {entry.filename for entry in entries} != _NAMES
                    or any(
                        (entry.is_dir()
                         or entry.compress_type != zipfile.ZIP_STORED
                         or entry.file_size != entry.compress_size
                         or not 0 < entry.file_size <= limits[entry.filename]
                         or entry.flag_bits & 0x1
                         or entry.extra
                         or (entry.external_attr >> 16) & stat.S_IFMT(
                             entry.external_attr >> 16
                         ) == stat.S_IFLNK)
                        for entry in entries
                    )):
                raise ValueError("OPERATOR_ZIP_UNSAFE_ENTRY")
            manifest = _json_object(archive.read("manifest.json"), limit=4_096)
            if (set(manifest) != {
                "schema", "operator_claims", "entries",
                "origin_authenticated", "source_rights_verified",
                "transport_http_performed", "official_submission", "note",
            } or manifest["schema"] != _SCHEMA
                    or any(manifest[key] is not False for key in (
                        "origin_authenticated", "source_rights_verified",
                        "transport_http_performed", "official_submission",
                    ))
                    or not _claims_valid(manifest.get("operator_claims"))
                    or type(manifest.get("entries")) is not dict
                    or set(manifest["entries"]) != {p[0] for p in _PARTS}
                    or type(manifest["note"]) is not str
                    or len(manifest["note"]) > 180):
                raise ValueError("OPERATOR_ZIP_BAD_MANIFEST")
            raws = {}
            for key, name, limit in _PARTS:
                expected = manifest["entries"][key]
                if (type(expected) is not dict
                        or set(expected) != {"name", "size", "sha256"}
                        or expected["name"] != name
                        or type(expected["size"]) is not int
                        or not 0 < expected["size"] <= limit
                        or type(expected["sha256"]) is not str
                        or not _SHA.fullmatch(expected["sha256"])):
                    raise ValueError("OPERATOR_ZIP_INVALID_ENTRY_MANIFEST")
                raw = archive.read(name)
                if (len(raw) != expected["size"]
                        or sha256(raw).hexdigest() != expected["sha256"]):
                    raise ValueError("OPERATOR_ZIP_SHA_OR_SIZE_CONFLICT")
                raws[key] = raw
            if not _input_identity(raws, manifest["operator_claims"]["issuer_cik"]):
                raise ValueError("OPERATOR_ZIP_ISSUER_MISMATCH")
            return raws, manifest["operator_claims"]
    except (
        zipfile.BadZipFile, RuntimeError, EOFError, OverflowError, OSError,
        UnicodeError, KeyError, TypeError, RecursionError,
    ) as exc:
        raise ValueError("OPERATOR_ZIP_MALFORMED_OR_UNSAFE") from exc


def inspect_operator_sec_zip_bytes(blob: bytes) -> dict[str, Any]:
    """Metadata only. Never include uploaded source bytes or HTML snippets."""
    raws, claims = read_operator_sec_zip_bytes(blob)
    return {
        "schema": "kuodra.operator-sec-zip-check.v1",
        "status": "local_zip_digest_and_issuer_match_origin_unverified",
        "operator_claims": dict(claims),
        "source_sha256": {key: sha256(raw).hexdigest() for key, raw in raws.items()},
        "archive_sha256": sha256(blob).hexdigest(),
        "sec_origin_authenticated": False,
        "source_rights_verified": False,
        "transport_http_performed": False,
        "audit_written": False,
        "official_submission": False,
    }


def read_operator_sec_zip_file(path: Path) -> tuple[dict[str, bytes], dict]:
    """Symlinks/non-regular files rejected by the existing bounded reader."""
    return read_operator_sec_zip_bytes(
        _read_regular_local(path, _MAX_ZIP_BYTES)
    )


def save_new_operator_sec_zip(path: Path, *, sources: dict[str, bytes],
                              claims: dict[str, str]) -> str:
    """Explicit opt-in only. Atomically publish one absent local ZIP, no overwrite."""
    if not isinstance(path, Path) or path.suffix.lower() != ".zip":
        raise ValueError("OPERATOR_ZIP_OUTPUT_PATH_INVALID")
    if path.exists() or path.is_symlink():
        raise FileExistsError("OPERATOR_ZIP_OUTPUT_ALREADY_EXISTS")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise ValueError("OPERATOR_ZIP_OUTPUT_PARENT_INVALID")
    raw = make_operator_sec_zip_bytes(**sources, **claims)
    staged = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w+b", dir=path.parent, prefix=".kuodra-operator-",
            suffix=".part", delete=False,
        ) as out:
            staged = Path(out.name)
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        os.link(staged, path)
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)
    return sha256(raw).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline only; manually obtained files, NEVER SEC provider auth."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    pack = sub.add_parser("pack", help="Explicitly save one NEW ZIP, no overwrite")
    for option in ("submissions", "companyfacts", "original-filing"):
        pack.add_argument("--" + option, type=Path, required=True)
    for option in ("issuer-cik", "accession", "as-of", "collected-at"):
        pack.add_argument("--" + option, required=True)
    pack.add_argument("--output", type=Path, required=True)
    check = sub.add_parser("inspect", help="Read-only safe metadata report")
    check.add_argument("--zip", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.cmd == "pack":
            source = {
                key: _read_regular_local(path, limit)
                for (key, _, limit), path in zip(_PARTS, (
                    args.submissions, args.companyfacts, args.original_filing,
                ))
            }
            identity = {
                "issuer_cik": args.issuer_cik, "accession": args.accession,
                "as_of": args.as_of, "collected_at": args.collected_at,
            }
            digest = save_new_operator_sec_zip(
                args.output, sources=source, claims=identity,
            )
            response = {
                "status": "operator_zip_created_origin_unverified",
                "output_sha256": digest,
                "source_authenticated": False, "official_submission": False,
            }
        else:
            packed = _read_regular_local(args.zip, _MAX_ZIP_BYTES)
            response = inspect_operator_sec_zip_bytes(packed)
    except (ValueError, FileExistsError, OSError, KeyError, TypeError):
        response = {
            "status": "blocked", "reason_code": "OPERATOR_ZIP_INPUT_OR_OUTPUT_INVALID",
            "source_authenticated": False, "official_submission": False,
        }
    print(json.dumps(response, ensure_ascii=True, sort_keys=True))
    return 2 if response["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
