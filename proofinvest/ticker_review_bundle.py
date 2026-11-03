"""P171: deterministic one-file, offline A/B/C human-review evidence bundle.

ZIP contains ONLY previously checked redacted JSON receipts, a static HTML
review brief and a content-hash manifest. It contains no original SEC filings,
raw stock/NDX observations, credentials, active content or source rights grant.
Check with inspect_review_bundle_bytes *before* any file use or extraction.
"""
from __future__ import annotations

from hashlib import sha256
from hmac import compare_digest
from io import BytesIO
import json
import zipfile
from typing import Any

from .ticker_review_packet import inspect_review_packet_bytes
from .ticker_reviewer_html import render_reviewer_html

_NAME = "kuodra.offline-a-b-c-review-bundle.v1"
_MANIFEST = "manifest.json"
_PACKET = "review-packet.json"
_RIGHTS = "source-rights-GAPS.json"
_HTML = "single-ticker-review.html"
_CSV = "market-csv-lineage.json"
_BASE = (_PACKET, _RIGHTS, _HTML)
_WITH_CSV = (_PACKET, _RIGHTS, _HTML, _CSV)
_MAX_BYTES = 150_000


def _canonical(obj: Any) -> bytes:
    return (json.dumps(
        obj, ensure_ascii=False, allow_nan=False,
        sort_keys=True, separators=(",", ":"),
    ) + "\n").encode("utf-8")


def _entries(*, review_packet: bytes, rights_gap_report: bytes,
             csv_lineage: bytes | None) -> dict[str, bytes]:
    # All original source inputs are intentionally absent.
    expected_html = render_reviewer_html(
        review_packet=review_packet, rights_gap_report=rights_gap_report,
        csv_lineage=csv_lineage,
    )
    docs = {_PACKET: review_packet, _RIGHTS: rights_gap_report,
            _HTML: expected_html}
    if csv_lineage is not None:
        docs[_CSV] = csv_lineage
    return docs


def build_review_bundle_bytes(
    *, review_packet: bytes, rights_gap_report: bytes,
    csv_lineage: bytes | None = None,
) -> bytes:
    """Build fully reproducible ZIP without acquiring/altering source bytes."""
    docs = _entries(
        review_packet=review_packet, rights_gap_report=rights_gap_report,
        csv_lineage=csv_lineage,
    )
    inspected = inspect_review_packet_bytes(review_packet)
    manifest = {
        "schema": _NAME,
        "status": "LOCAL_REVIEW_ONLY_ORIGIN_AND_RIGHTS_UNVERIFIED",
        "ticker": inspected["ticker"],
        "review_packet_sha256": sha256(review_packet).hexdigest(),
        "files": {name: {"sha256": sha256(raw).hexdigest(), "bytes": len(raw)}
                  for name, raw in docs.items()},
        "source_authenticated": False,
        "source_rights_verified": False,
        "external_sharing_allowed": False,
        "contest_submission_approved": False,
        "guard_policy_preview": "HOLD",
        "trade_executed": False,
        "network_requests": 0,
    }
    manifest["manifest_sha256"] = sha256(_canonical(manifest)).hexdigest()
    docs[_MANIFEST] = _canonical(manifest)
    fileobj = BytesIO()
    with zipfile.ZipFile(fileobj, mode="w", allowZip64=False) as archive:
        for name in sorted(docs):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, docs[name])
    raw = fileobj.getvalue()
    if len(raw) > _MAX_BYTES:
        raise ValueError("REVIEW_BUNDLE_SIZE_INVALID")
    return raw


def inspect_review_bundle_bytes(raw: bytes) -> dict[str, Any]:
    """Validate strict file roster, hashes, content and regenerated HTML.

    Does not extract ZIP members to disk, execute scripts or make network calls.
    """
    if type(raw) is not bytes or not 0 < len(raw) <= _MAX_BYTES:
        raise ValueError("REVIEW_BUNDLE_BYTES_INVALID")
    try:
        with zipfile.ZipFile(BytesIO(raw), mode="r", allowZip64=False) as archive:
            infos = archive.infolist()
            names = [x.filename for x in infos]
            allowed = (set(_BASE) | {_MANIFEST}, set(_WITH_CSV) | {_MANIFEST})
            if (len(names) not in (4, 5)
                    or len(names) != len(set(names))
                    or set(names) not in allowed
                    or names != sorted(names)
                    or archive.comment
                    or sum(x.file_size for x in infos) > _MAX_BYTES
                    or any(
                        x.comment
                        or (x.external_attr >> 16) & 0o170000 == 0o120000
                        or x.is_dir()
                        x.compress_type != zipfile.ZIP_STORED
                        or x.flag_bits & 0x1
                        or x.file_size <= 0
                        or x.file_size > _MAX_BYTES
                        or x.compress_size != x.file_size
                        or x.extra
                        or x.filename.startswith("/")
                        or "/" in x.filename
                        or "\\" in x.filename
                        for x in infos
                    )):
                raise ValueError("REVIEW_BUNDLE_MEMBER_CONTRACT_INVALID")
            docs = {x.filename: archive.read(x) for x in infos}
        manifest_raw = docs.pop(_MANIFEST)
        if not 0 < len(manifest_raw) <= 4096:
            raise ValueError("REVIEW_BUNDLE_MANIFEST_SIZE_INVALID")

        def reject_duplicates(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("REVIEW_BUNDLE_JSON_DUPLICATE")
                result[key] = value
            return result
        m = json.loads(
            manifest_raw.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda x: (_ for _ in ()).throw(
                ValueError("REVIEW_BUNDLE_NONFINITE")),
        )
        if type(m) is not dict:
            raise ValueError("REVIEW_BUNDLE_MANIFEST_INVALID")
        checksum = m.pop("manifest_sha256", None)
        if (type(checksum) is not str
                or not compare_digest(sha256(_canonical(m)).hexdigest(), checksum)):
            raise ValueError("REVIEW_BUNDLE_CHECKSUM_INVALID")
        m["manifest_sha256"] = checksum
        if (manifest_raw != _canonical(m)
                or set(m) != {
                    "schema", "status", "ticker", "review_packet_sha256",
                    "files", "source_authenticated", "source_rights_verified",
                    "external_sharing_allowed", "contest_submission_approved",
                    "guard_policy_preview", "trade_executed",
                    "network_requests", "manifest_sha256",
                }
                or m["schema"] != _NAME
                or m["status"] != "LOCAL_REVIEW_ONLY_ORIGIN_AND_RIGHTS_UNVERIFIED"
                or type(m["files"]) is not dict
                or set(m["files"]) != set(docs)
                or m["guard_policy_preview"] != "HOLD"
                or m["network_requests"] != 0
                or any(m[key] is not False for key in (
                    "source_authenticated", "source_rights_verified",
                    "external_sharing_allowed", "contest_submission_approved",
                    "trade_executed",
                ))):
            raise ValueError("REVIEW_BUNDLE_MANIFEST_CONTRACT_INVALID")
        for name, data in docs.items():
            spec = m["files"][name]
            if (type(spec) is not dict or set(spec) != {"sha256", "bytes"}
                    or type(spec["bytes"]) is not int
                    or spec["bytes"] != len(data)
                    or type(spec["sha256"]) is not str
                    or not compare_digest(spec["sha256"], sha256(data).hexdigest())):
                raise ValueError("REVIEW_BUNDLE_HASH_MISMATCH")
        packet = docs[_PACKET]
        packet_check = inspect_review_packet_bytes(packet)
        if (m["ticker"] != packet_check["ticker"]
                or m["review_packet_sha256"] != sha256(packet).hexdigest()):
            raise ValueError("REVIEW_BUNDLE_ISSUER_OR_PACKET_INVALID")
        regenerated_html = _entries(
            review_packet=packet, rights_gap_report=docs[_RIGHTS],
            csv_lineage=docs.get(_CSV),
        )[_HTML]
        if not compare_digest(regenerated_html, docs[_HTML]):
            raise ValueError("REVIEW_BUNDLE_HTML_MISMATCH")
        return {
            "schema": "kuodra.offline-a-b-c-review-bundle-check.v1",
            "status": "INTERNAL_CONTENT_VERIFIED_ORIGIN_RIGHTS_PENDING",
            "ticker": packet_check["ticker"],
            "review_packet_sha256": m["review_packet_sha256"],
            "manifest_sha256": checksum,
            "files_verified": len(docs),
            "source_authenticated": False,
            "source_rights_verified": False,
            "external_sharing_allowed": False,
            "contest_submission_approved": False,
            "guard_policy_preview": "HOLD",
            "trade_executed": False,
            "network_requests": 0,
        }
    except (OSError, ValueError, KeyError, TypeError,
            UnicodeError, RecursionError, RuntimeError, zipfile.BadZipFile,
            EOFError, NotImplementedError) as exc:
        raise ValueError("REVIEW_BUNDLE_INVALID") from exc
