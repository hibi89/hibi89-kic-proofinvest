"""Explicit, no-overwrite local evidence ZIP: three raw SEC-shaped responses + receipt.

Never fetches, uploads or certifies source origin. Stored transport metadata is
self-reported data; even a valid SHA-256 is not SEC/filing authentication.
Only the operator-selected local path is written, exclusively after opt-in.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import zipfile
from typing import Any, Mapping

from disclosure_lightning.core import MAX_JSON_BYTES
from disclosure_lightning.originals import MAX_FILING_BYTES
from proofinvest.local_sec_packet import _json_object

_MAX_ZIP_BYTES = MAX_JSON_BYTES * 2 + MAX_FILING_BYTES + 100_000
_NAMES = ("manifest.json", "submissions.json", "companyfacts.json", "original_filing.bin")
_PARTS = (("submissions", "submissions.json", MAX_JSON_BYTES),
          ("companyfacts", "companyfacts.json", MAX_JSON_BYTES),
          ("original_filing", "original_filing.bin", MAX_FILING_BYTES))


def _receipt_ok(receipt: Any, raws: Mapping[str, bytes] | None = None) -> bool:
    if type(receipt) is not dict:
        return False
    required = {
        "schema": "proofinvest.sec-3source-explicit-transport.v1",
        "status": "three_sec_https_responses_captured_unverified",
        "http_requests_attempted": 3,
        "live_sec_http_called": True,
        "source_authenticated": False,
        "financial_facts_authenticated": False,
        "source_rights_verified": False,
        "official_contest_submission": False,
    }
    if any(type(receipt.get(k)) is not type(v) or receipt.get(k) != v for k, v in required.items()):
        return False
    id_cik, acc = receipt.get("issuer_cik"), receipt.get("accession")
    if (not isinstance(id_cik, str) or len(id_cik) != 10 or
            not id_cik.isascii() or not id_cik.isdecimal() or int(id_cik) == 0 or
            not isinstance(acc, str) or len(acc) != 20 or not acc.startswith(id_cik+"-")):
        return False
    urls = receipt.get("source_uris")
    digests = receipt.get("raw_response_sha256")
    if not isinstance(urls, dict) or not isinstance(digests, dict):
        return False
    expect_urls = {
        "submissions": f"https://data.sec.gov/submissions/CIK{id_cik}.json",
        "companyfacts": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{id_cik}.json",
    }
    for k,v in expect_urls.items():
        if urls.get(k) != v:
            return False
    origin = f"https://www.sec.gov/Archives/edgar/data/{int(id_cik)}/{acc.replace('-','')}/"
    original_uri = urls.get("original_filing")
    if (not isinstance(original_uri, str) or not original_uri.startswith(origin)
            or len(original_uri) <= len(origin) or len(original_uri) > len(origin)+200):
        return False
    for key, file, limit in _PARTS:
        if key not in digests or not isinstance(digests[key], str):
            return False
        s = digests[key]
        if len(s) != 64 or any(c not in "0123456789abcdef" for c in s):
            return False
        if raws is not None:
            raw = raws.get(key)
            if type(raw) is not bytes or not 0 < len(raw) <= limit:
                return False
            if hashlib.sha256(raw).hexdigest() != s:
                return False
    return True


def preflight_local_bundle_path(path: Path) -> None:
    p = Path(path)
    if p.suffix.lower() != ".zip":
        raise ValueError("BUNDLE_ZIP_EXTENSION_REQUIRED")
    if p.exists() or p.is_symlink():
        raise FileExistsError("LOCAL_BUNDLE_ALREADY_EXISTS")
    if not p.parent.is_dir() or p.parent.is_symlink():
        raise ValueError("LOCAL_BUNDLE_PARENT_INVALID")


def save_local_capture_bundle(
    path: Path, *, receipt: dict[str, Any], submissions: bytes,
    companyfacts: bytes, original_filing: bytes,
) -> None:
    """Stage/fsync a bounded ZIP; atomic hardlink publishes only absent target."""
    raws = {"submissions": submissions, "companyfacts": companyfacts,
            "original_filing": original_filing}
    if not _receipt_ok(receipt, raws):
        raise ValueError("UNTRUSTED_BUNDLE_RECEIPT_OR_DIGEST_MISMATCH")
    preflight_local_bundle_path(path)
    manifest = {
        "schema": "proofinvest.sec-capture-local-bundle.v1",
        "receipt_self_reported": receipt,
        "files": {key: {"entry": name, "size": len(raws[key]),
                         "sha256": hashlib.sha256(raws[key]).hexdigest()}
                  for key,name,_ in _PARTS},
        "notice": ("SEC-shaped transport receipt and local SHA256 only; "
                   "NOT authenticated source, rights, fiscal accuracy or historical availability."),
    }
    payload = json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(payload) > 20_000:
        raise ValueError("BUNDLE_MANIFEST_TOO_LARGE")
    tmp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w+b", dir=path.parent, prefix=f".{path.stem}.",
            suffix=".part", delete=False,
        ) as handle:
            tmp = Path(handle.name)
            with zipfile.ZipFile(handle, mode="w", compression=zipfile.ZIP_STORED,
                                 allowZip64=False) as archive:
                for name, raw in [("manifest.json", payload)] + [
                    (name, raws[key]) for key,name,_ in _PARTS
                ]:
                    metadata = zipfile.ZipInfo(name, date_time=(1980,1,1,0,0,0))
                    metadata.compress_type = zipfile.ZIP_STORED
                    archive.writestr(metadata, raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(tmp, path)  # Cannot replace an existing file, including symlinks.
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def verify_local_capture_bundle(path: Path) -> dict[str, Any]:
    """Offline integrity-only reread; never upgrades the self-reported origin."""
    unavailable = {
        "schema": "proofinvest.sec-capture-bundle-offline-check.v1",
        "status": "unavailable",
        "reason_code": "LOCAL_BUNDLE_NOT_VERIFIABLE",
        "local_bytes_and_manifest_match": False,
        "sec_origin_authenticated": False,
        "source_rights_verified": False,
        "financial_values_authenticated": False,
        "http_performed_by_this_check": False,
        "official_contest_submission": False,
    }
    p = Path(path)
    if p.is_symlink():
        return unavailable
    try:
        descriptor = os.open(p, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as file:
            meta = os.fstat(file.fileno())
            if not stat.S_ISREG(meta.st_mode) or not 0 < meta.st_size <= _MAX_ZIP_BYTES:
                return unavailable
            with zipfile.ZipFile(file, mode="r") as bundle:
                entries = bundle.infolist()
                if (len(entries) != len(_NAMES)
                        or set(x.filename for x in entries) != set(_NAMES)
                        or any(x.is_dir() or x.compress_type != zipfile.ZIP_STORED
                               or x.file_size != x.compress_size for x in entries)):
                    return unavailable
                limits = dict((name,limit) for _,name,limit in _PARTS)
                limits["manifest.json"] = 20_000
                if any(not 0 < x.file_size <= limits[x.filename] for x in entries):
                    return unavailable
                manifest = _json_object(bundle.read("manifest.json"), limit=20_000)
                if manifest.get("schema") != "proofinvest.sec-capture-local-bundle.v1":
                    return unavailable
                sections = manifest.get("files")
                if not isinstance(sections, dict) or set(sections) != set(k for k,_,_ in _PARTS):
                    return unavailable
                raws = {}
                for key, name, limit in _PARTS:
                    raw = bundle.read(name)
                    expected = sections[key]
                    if (not isinstance(expected, dict)
                            or expected.get("entry") != name
                            or type(expected.get("size")) is not int
                            or expected["size"] != len(raw)
                            or expected.get("sha256") != hashlib.sha256(raw).hexdigest()):
                        return unavailable
                    raws[key] = raw
                receipt = manifest.get("receipt_self_reported")
                if not _receipt_ok(receipt, raws):
                    return unavailable
                return {
                    **unavailable,
                    "status": "bundle_integrity_pass_origin_unverified",
                    "reason_code": "LOCAL_DIGESTS_MATCH_NOT_SEC_AUTHENTICATION",
                    "local_bytes_and_manifest_match": True,
                    "issuer_cik": receipt["issuer_cik"],
                    "accession": receipt["accession"],
                    "sha256": {key: sections[key]["sha256"] for key,_,_ in _PARTS},
                }
    except (OSError, ValueError, KeyError, TypeError, UnicodeDecodeError,
            zipfile.BadZipFile, RuntimeError, OverflowError):
        return unavailable
