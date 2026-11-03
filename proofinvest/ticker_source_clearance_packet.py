"""P168: exact-input source/rights gap report for a first offline A/B/C packet.

Strictly local provenance checklist. It binds a *reviewed* packet to exactly
the caller-selected SEC, stock, index and A/C bytes, without leaking their
content or claiming copyright/usage permission, origin, publication time,
issuer identity, vendor entitlement or permission to submit publicly.
"""
from __future__ import annotations

from hashlib import sha256
from hmac import compare_digest
import json
from typing import Any

from .ticker_review_packet import inspect_review_packet_bytes
from .ticker_sec_financial_bridge import _LIMITS as SEC_LIMITS

_SCHEMA = "kuodra.offline-a-b-c-source-clearance.v1"
_STATUS = "SOURCE_BYTES_MATCHED_RIGHTS_AND_ORIGIN_NOT_VERIFIED"
_ROLES = (
    "ticker_map", "submissions", "companyfacts", "original_10k",
    "stock_daily", "nasdaq100_index_daily", "market_json", "industry_json",
)
_UNVERIFIED = (
    "PUBLISHER_SOURCE_ORIGINAL_AUTHENTICATION",
    "PROVIDER_ACCOUNT_AND_PREMIUM_NDX_ENTITLEMENT",
    "SOURCE_PUBLICATION_AND_ACQUISITION_TIMESTAMPS",
    "MARKET_DATA_DISPLAY_AND_DERIVATIVE_RIGHTS",
    "SEC_OR_PROVIDER_REDISTRIBUTION_RIGHTS",
    "PEER_SAMPLE_REPRESENTATIVENESS_IF_REPORTED",
)
_MAX = 9216


def _canonical(obj: Any) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _matching(raw: Any, digest: Any) -> bool:
    return (
        type(raw) is bytes and len(raw) > 0 and type(digest) is str
        and len(digest) == 64 and
        compare_digest(sha256(raw).hexdigest(), digest)
    )


def build_source_clearance_packet(
    *, packet: Any, sources: Any, stock_raw: Any, index_raw: Any,
    market_json: bytes | None = None, industry_json: bytes | None = None,
) -> bytes:
    """Return redacted, canonical, sha-linked clearance *gap* receipt.

    This method never grants access. It does not attest when or from whom
    inputs were acquired. All source bytes must match the reviewed packet.
    """
    if (type(packet) is not bytes or type(sources) is not dict
            or set(sources) != set(SEC_LIMITS)
            or any(type(sources[k]) is not bytes
                   or not 0 < len(sources[k]) <= SEC_LIMITS[k]
                   for k in SEC_LIMITS)
            or type(stock_raw) is not bytes or not 0 < len(stock_raw) <= 262144
            or type(index_raw) is not bytes or not 0 < len(index_raw) <= 8388608
            or (market_json is not None
                and (type(market_json) is not bytes
                     or not 0 < len(market_json) <= 131072))
            or (industry_json is not None
                and (type(industry_json) is not bytes
                     or not 0 < len(industry_json) <= 65536))):
        raise ValueError("SOURCE_CLEARANCE_ORIGINALS_INVALID")
    checked = inspect_review_packet_bytes(packet)
    if checked["status"] != "LOCAL_PACKET_INTERNAL_INTEGRITY_PASS_UNVERIFIED":
        raise ValueError("SOURCE_CLEARANCE_PACKET_INVALID")
    packet_data = json.loads(packet.decode("utf-8"))
    linked = packet_data["linked_evidence"]
    by_role = {
        **{role: (sources[role], linked["four_source_sha256"][role])
           for role in SEC_LIMITS},
        "stock_daily": (stock_raw, linked["premium_engine_a"]["stock_response_sha256"]),
        "nasdaq100_index_daily": (
            index_raw, linked["premium_engine_a"]["index_response_sha256"],
        ),
        "market_json": (market_json, linked["local_engine_a"]["input_sha256"]),
        "industry_json": (industry_json, linked["engine_c"]["input_sha256"]),
    }
    cards = []
    for role in _ROLES:
        raw, digest = by_role[role]
        if (raw is None) != (digest is None):
            raise ValueError("SOURCE_CLEARANCE_MISSING_OPTIONAL_BYTES")
        if raw is not None and not _matching(raw, digest):
            raise ValueError("SOURCE_CLEARANCE_EXACT_BYTES_MISMATCH")
        cards.append({
            "role": role, "sha256": digest,
            "bytes": len(raw) if raw is not None else 0,
            "input_state": ("EXACT_LOCAL_BYTES_MATCHED"
                            if raw is not None else "OPTIONAL_SOURCE_NOT_BOUND"),
            "publisher_origin_authenticated": False,
            "acquisition_timestamp_verified": False,
            "source_use_rights_verified": False,
            "external_display_rights_verified": False,
            "redistribution_rights_verified": False,
        })
    # Unlike a SHA, neither an 'Alpha Vantage-shaped' JSON response nor a
    # caller's claim proves original FRED/Nasdaq/Alpha Vantage provenance.
    # Do not silently promote index rights due to local arithmetic PASS.
    issuer = linked["issuer"]
    p = linked["premium_engine_a"]
    obj = {
        "schema": _SCHEMA, "status": _STATUS,
        "packet_sha256": sha256(packet).hexdigest(),
        "linked_evidence_sha256": linked["evidence_sha256"],
        "issuer": {
            "ticker": issuer["ticker"], "cik": issuer["cik"],
            "accession": issuer["accession"],
            "filing_date": issuer["filing_date"], "as_of": issuer["as_of"],
        },
        "market_window": {
            "benchmark": "NASDAQ_100", "index_symbol": "NDX",
            "return_basis": "PRICE_ONLY_CLOSE",
            "first_date": p["matched_period_start"],
            "last_date": p["matched_period_end"],
            "matched_sessions": p["matched_observation_count"],
            "origin_or_market_vintage_proven": False,
        },
        "files": cards,
        "unresolved_clearances": list(_UNVERIFIED),
        "guard_policy_preview": "HOLD",
        "replay_scope": "EXACT_LOCAL_SOURCE_BYTES_NOT_PUBLISHER_ATTESTATION",
        "network_requests": 0, "paid_requests": 0,
        "source_authenticated": False,
        "source_rights_verified": False,
        "external_sharing_allowed": False,
        "commercial_reuse_allowed": False,
        "contest_submission_approved": False,
        "trade_executed": False,
        "notice": (
            "원본 해시 일치·오프라인 산술 재검산은 발행기관 진위, 자료 취득 시점, "
            "Nasdaq-100 및 공급자의 라이선스·유료 권한·재배포 권한을 입증하지 않습니다."
        ),
    }
    obj["receipt_sha256"] = sha256(_canonical(obj)).hexdigest()
    result = _canonical(obj)
    if len(result) > _MAX:
        raise ValueError("SOURCE_CLEARANCE_RECEIPT_TOO_LARGE")
    return result


def inspect_source_clearance_packet(raw: Any, *, review_packet: Any) -> dict[str, Any]:
    """Check a downloaded report belongs to the exact downloaded A/B/C packet.

    A clean result still leaves all external-source grants unresolved.
    """
    if type(raw) is not bytes or not 0 < len(raw) <= _MAX:
        raise ValueError("CLEARANCE_RECEIPT_SIZE_INVALID")
    checked = inspect_review_packet_bytes(review_packet)
    def no_duplicates(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise ValueError("CLEARANCE_RECEIPT_DUPLICATE")
            result[k] = v
        return result
    try:
        obj = json.loads(raw.decode("utf-8"),
                         object_pairs_hook=no_duplicates,
                         parse_constant=lambda _: (_ for _ in ()).throw(
                             ValueError("CLEARANCE_NONFINITE")))
        digest = obj.pop("receipt_sha256", None)
        if (type(digest) is not str or len(digest) != 64
                or not compare_digest(sha256(_canonical(obj)).hexdigest(), digest)):
            raise ValueError("CLEARANCE_RECEIPT_SHA_INVALID")
        obj["receipt_sha256"] = digest
        if raw != _canonical(obj):
            raise ValueError("CLEARANCE_RECEIPT_NONCANONICAL")
        packet_data = json.loads(review_packet.decode("utf-8"))
        linked = packet_data["linked_evidence"]
        issuer = linked["issuer"]
        p = linked["premium_engine_a"]
        expected_digests = {
            **linked["four_source_sha256"],
            "stock_daily": p["stock_response_sha256"],
            "nasdaq100_index_daily": p["index_response_sha256"],
            "market_json": linked["local_engine_a"]["input_sha256"],
            "industry_json": linked["engine_c"]["input_sha256"],
        }
        expected_issuer = {key: issuer[key] for key in (
            "ticker", "cik", "accession", "filing_date", "as_of",
        )}
        expected_window = {
            "benchmark": "NASDAQ_100", "index_symbol": "NDX",
            "return_basis": "PRICE_ONLY_CLOSE",
            "first_date": p["matched_period_start"],
            "last_date": p["matched_period_end"],
            "matched_sessions": p["matched_observation_count"],
            "origin_or_market_vintage_proven": False,
        }
        if (set(obj) != {
                    "schema", "status", "packet_sha256",
                    "linked_evidence_sha256", "issuer", "market_window",
                    "files", "unresolved_clearances", "guard_policy_preview",
                    "replay_scope", "network_requests", "paid_requests",
                    "source_authenticated", "source_rights_verified",
                    "external_sharing_allowed", "commercial_reuse_allowed",
                    "contest_submission_approved", "trade_executed",
                    "notice", "receipt_sha256",
                }
                or obj.get("schema") != _SCHEMA or obj.get("status") != _STATUS
                or obj.get("packet_sha256") != sha256(review_packet).hexdigest()
                or obj.get("linked_evidence_sha256") != checked["linked_evidence_sha256"]
                or obj.get("replay_scope") !=
                    "EXACT_LOCAL_SOURCE_BYTES_NOT_PUBLISHER_ATTESTATION"
                or obj.get("issuer") != expected_issuer
                or obj.get("market_window") != expected_window
                or obj.get("guard_policy_preview") != "HOLD"
                or obj.get("unresolved_clearances") != list(_UNVERIFIED)
                or any(obj.get(k) is not False for k in (
                    "source_authenticated", "source_rights_verified",
                    "external_sharing_allowed", "commercial_reuse_allowed",
                    "contest_submission_approved", "trade_executed"))
                or obj.get("network_requests") != 0
                or obj.get("paid_requests") != 0
                or type(obj.get("files")) is not list
                or [x.get("role") for x in obj["files"]] != list(_ROLES)
                or any(
                    x.get("sha256") != expected_digests[x["role"]]
                    or type(x.get("bytes")) is not int
                    or (
                        x["bytes"] > 0 and x["input_state"] != "EXACT_LOCAL_BYTES_MATCHED"
                    )
                    or (
                        x["bytes"] == 0 and (
                            x["sha256"] is not None
                            or x["input_state"] != "OPTIONAL_SOURCE_NOT_BOUND"
                        )
                    )
                    or x["bytes"] < 0
                    for x in obj["files"]
                )
                or any(
                    type(x) is not dict or set(x) != {
                        "role", "sha256", "bytes", "input_state",
                        "publisher_origin_authenticated",
                        "acquisition_timestamp_verified",
                        "source_use_rights_verified",
                        "external_display_rights_verified",
                        "redistribution_rights_verified",
                    } or any(x.get(flag) is not False for flag in (
                        "publisher_origin_authenticated",
                        "acquisition_timestamp_verified",
                        "source_use_rights_verified",
                        "external_display_rights_verified",
                        "redistribution_rights_verified",
                    ))
                    for x in obj["files"])):
            raise ValueError("CLEARANCE_RECEIPT_TRUST_CONTRACT_INVALID")
        return {
            "schema": "kuodra.offline-source-clearance-check.v1",
            "status": "MATCHED_REPORT_EXTERNAL_CLEARANCES_STILL_PENDING",
            "packet_sha256": obj["packet_sha256"],
            "receipt_sha256": digest,
            "source_rights_verified": False,
            "external_sharing_allowed": False,
        }
    except (ValueError, TypeError, KeyError, AttributeError,
            UnicodeError, RecursionError, json.JSONDecodeError) as exc:
        raise ValueError("SOURCE_CLEARANCE_RECEIPT_INVALID") from exc
