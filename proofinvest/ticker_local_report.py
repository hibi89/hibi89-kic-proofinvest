"""P117: bounded offline evidence report for caller-supplied SEC-shaped bytes.

A digest binds this report to declared local SHA values, not to SEC publisher
authenticity or source redistribution rights. Never persist or include originals.
"""
from __future__ import annotations

from hashlib import sha256
from hmac import compare_digest
import argparse
import json
from pathlib import Path


def make_local_report(receipt: dict, revenue: dict, original: dict,
                      supplementary: dict) -> dict:
    if (type(receipt) is not dict or type(revenue) is not dict
            or type(original) is not dict or type(supplementary) is not dict):
        raise ValueError("LOCAL_REPORT_INPUT_INVALID")
    if (receipt.get("schema") != "kuodra.local-sec-source-receipt.v1"
            or receipt.get("status") != "local_four_sources_unverified"
            or receipt.get("source_kind") != "CALLER_SUPPLIED_LOCAL_UNAUTHENTICATED"
            or receipt.get("network_requests") != 0
            or receipt.get("http_requests_attempted") != 0
            or receipt.get("live_sec_http_called") is not False
            or receipt.get("source_authenticated") is not False
            or receipt.get("source_rights_verified") is not False
            or receipt.get("trade_executed") is not False
            or type(receipt.get("source_sha256")) is not dict
            or set(receipt["source_sha256"]) != {
                "ticker_map", "submissions", "companyfacts", "original_10k"
            }
            or any(type(d) is not str or len(d) != 64
                   or any(c not in "0123456789abcdef" for c in d)
                   for d in receipt["source_sha256"].values())):
        raise ValueError("LOCAL_RECEIPT_TRUST_INVALID")
    if (revenue.get("status") != "REVENUE_CALCULATED_UNVERIFIED"
            or revenue.get("input_mode") != "LOCAL_UPLOAD_UNAUTHENTICATED"
            or revenue.get("issuer_cik") != receipt.get("cik")
            or revenue.get("ticker") != receipt.get("ticker")
            or revenue.get("accession") != receipt.get("selected_10k_accession")
            or revenue.get("companyfacts_sha256") != receipt["source_sha256"]["companyfacts"]
            or revenue.get("original_10k_sha256") != receipt["source_sha256"]["original_10k"]
            or revenue.get("source_authenticated") is not False
            or revenue.get("source_rights_verified") is not False
            or revenue.get("guard_executed") is not False):
        raise ValueError("LOCAL_REVENUE_TRUST_INVALID")
    policy = original.get("guard_preview")
    if (type(policy) is not dict or policy.get("decision") not in ("HOLD", "REJECT")
            or policy.get("source_authenticated") is not False
            or policy.get("human_approved") is not False
            or policy.get("trade_executed") is not False
            or original.get("cik") != receipt.get("cik")
            or original.get("accession") != receipt.get("selected_10k_accession")
            or original.get("companyfacts_sha256") != receipt["source_sha256"]["companyfacts"]
            or original.get("original_10k_sha256") != receipt["source_sha256"]["original_10k"]
            or original.get("source_authenticated") is not False
            or original.get("guard_executed") is not False
            or original.get("audit_written") is not False):
        raise ValueError("LOCAL_ORIGINAL_GUARD_TRUST_INVALID")
    if (supplementary.get("source_authenticated") is not False
            or supplementary.get("source_rights_verified") is not False
            or supplementary.get("guard_executed") is not False
            or supplementary.get("trade_executed") is not False
            or type(supplementary.get("engine_a")) is not dict
            or type(supplementary.get("engine_c")) is not dict):
        raise ValueError("LOCAL_A_C_TRUST_INVALID")
    report = {
        "schema": "kuodra.local-four-source-review-report.v1",
        "status": "STRUCTURAL_ARITHMETIC_ONLY_UNVERIFIED",
        "source_kind": "CALLER_SUPPLIED_LOCAL_UNAUTHENTICATED",
        "issuer": {
            "ticker": receipt["ticker"], "cik": receipt["cik"],
            "accession": receipt["selected_10k_accession"],
            "filing_date": receipt["selected_10k_filing_date"],
            "as_of": receipt["requested_as_of"],
        },
        "source_sha256": dict(receipt["source_sha256"]),
        "verification": {
            "status": revenue["status"],
            "current_end": revenue["current_end"],
            "prior_end": revenue["prior_end"],
            "current_usd": revenue["current_usd"],
            "prior_usd": revenue["prior_usd"],
            "growth_pct": revenue["growth_pct"],
        },
        "original_context": original["status"],
        "guard_policy_preview": policy["decision"],
        "engine_a_status": supplementary["engine_a"]["status"],
        "engine_c_status": supplementary["engine_c"]["status"],
        "engine_a_input_sha256": supplementary["engine_a"].get("input_sha256"),
        "engine_c_input_sha256": supplementary["engine_c"].get("input_sha256"),
        "limits": {
            "source_authenticated": False, "source_rights_verified": False,
            "independent_original_authenticated": False,
            "live_sec_http_called": False, "external_http_requests": 0,
            "ai_agent_executed": False, "guard_executed": False,
            "audit_written": False, "human_approved": False,
            "trade_executed": False, "official_contest_submission": False,
        },
    }
    canonical = (json.dumps(report, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    report["report_sha256"] = sha256(canonical).hexdigest()
    return report


def report_json_bytes(report: dict) -> bytes:
    """Serialize for an explicit local browser download, no server write."""
    return (json.dumps(report, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


# P118: self-hash is an accidental-corruption detector, NOT a signature.
# The independent verifier additionally regenerates every result from the
# exact user-supplied source bytes. No network, model, trade, or persistent DB.
_MAX_REPORT_BYTES = 32_768
_VERIFY_SCHEMA = "kuodra.local-four-source-replay-verification.v1"


def _verification(status: str, reason: str) -> dict:
    return {
        "schema": _VERIFY_SCHEMA, "status": status,
        "reason_code": reason, "network_requests": 0,
        "source_authenticated": False, "source_rights_verified": False,
        "guard_executed": False, "audit_written": False,
        "trade_executed": False, "report_semantics_recomputed": status == "PASS",
    }


def verify_local_report(
    report: dict, *, sources: dict[str, bytes],
    market_json: bytes | None = None, industry_json: bytes | None = None,
) -> dict:
    """Replay the downloaded report from bytes; reject self-consistent forgeries.

    Exact-source independent verification is *not* SEC-origin authentication.
    Missing A/C sources cannot be replaced by their claimed result statuses.
    """
    if type(report) is not dict or report.get("schema") != (
            "kuodra.local-four-source-review-report.v1"):
        return _verification("FAIL", "REPORT_SCHEMA_UNSUPPORTED")
    digest = report.get("report_sha256")
    if (type(digest) is not str or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)):
        return _verification("FAIL", "REPORT_DIGEST_INVALID")
    try:
        unsealed = {k: v for k, v in report.items() if k != "report_sha256"}
        canonical = (json.dumps(
            unsealed, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ) + "\n").encode("utf-8")
        if not compare_digest(sha256(canonical).hexdigest(), digest):
            return _verification("FAIL", "REPORT_DIGEST_MISMATCH")
        if type(sources) is not dict:
            return _verification("FAIL", "FOUR_LOCAL_SOURCES_REQUIRED")
        from .ticker_local_sources import prepare_local_ticker_sources
        from .ticker_sec_financial_bridge import inspect_collected_annual_revenue
        from .ticker_sec_original_guard_preview import inspect_original_guard_preview
        from .ticker_market_industry_bridge import evaluate_ticker_a_c

        # Do not use an altered report to select a different issuer. The issuer
        # claims are re-bound to the four original local files below.
        identity = report.get("issuer")
        if type(identity) is not dict:
            return _verification("FAIL", "REPORT_ISSUER_INVALID")
        receipt = prepare_local_ticker_sources(
            ticker=identity.get("ticker"), as_of=identity.get("as_of"),
            sources=sources,
        )
        if receipt.get("status") != "local_four_sources_unverified":
            return _verification("FAIL", "SOURCE_REPLAY_UNAVAILABLE")
        if (receipt.get("source_sha256") != report.get("source_sha256")
                or any(sha256(raw).hexdigest() != receipt["source_sha256"].get(name)
                       for name, raw in sources.items())):
            return _verification("FAIL", "SOURCE_BYTES_OR_SHA_CHANGED")
        revenue = inspect_collected_annual_revenue(receipt, sources)
        if revenue.get("status") != "REVENUE_CALCULATED_UNVERIFIED":
            return _verification("FAIL", "REVENUE_REPLAY_UNAVAILABLE")
        original = inspect_original_guard_preview(
            receipt, sources, expected_revenue=revenue)
        supplement = evaluate_ticker_a_c(
            receipt, sources, market_json=market_json,
            industry_json=industry_json)
        expected = make_local_report(receipt, revenue, original, supplement)
        if expected != report:
            return _verification("FAIL", "REPORT_SEMANTIC_REPLAY_MISMATCH")
        return _verification("PASS", "EXACT_LOCAL_BYTES_AND_CALCULATIONS_MATCH")
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError,
            OverflowError, UnicodeError):
        return _verification("FAIL", "SOURCE_OR_REPORT_INVALID")


def _bounded_read(path: Path, limit: int) -> bytes:
    with path.open("rb") as inp:
        raw = inp.read(limit + 1)
    if len(raw) == 0 or len(raw) > limit:
        raise ValueError("FILE_SIZE_INVALID")
    return raw


def _no_duplicate_keys(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("DUPLICATE_REPORT_JSON_KEY")
        out[key] = value
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Verify downloaded KUODRA local report against caller-owned "
                    "source files; no network, source origin or license assertion."
    )
    for flag in ("report", "ticker_map", "submissions", "companyfacts", "original_10k"):
        p.add_argument("--" + flag.replace("_", "-"), type=Path, required=True)
    p.add_argument("--market-json", type=Path)
    p.add_argument("--industry-json", type=Path)
    args = p.parse_args(argv)
    try:
        from .ticker_sec_financial_bridge import _LIMITS
        from .market_reality import MAX_UPLOAD_BYTES as MARKET_LIMIT
        from .industry_vision import MAX_UPLOAD_BYTES as INDUSTRY_LIMIT

        raw_report = _bounded_read(args.report, _MAX_REPORT_BYTES)
        report = json.loads(
            raw_report.decode("utf-8"), object_pairs_hook=_no_duplicate_keys,
            parse_constant=lambda _: (_ for _ in ()).throw(
                ValueError("NONFINITE_REPORT_NUMBER")),
        )
        if type(report) is not dict:
            raise ValueError("INVALID_REPORT_ROOT")
        sources = {k: _bounded_read(getattr(args, k), limit)
                   for k, limit in _LIMITS.items()}
        market = (_bounded_read(args.market_json, MARKET_LIMIT)
                  if args.market_json is not None else None)
        industry = (_bounded_read(args.industry_json, INDUSTRY_LIMIT)
                    if args.industry_json is not None else None)
        result = verify_local_report(
            report, sources=sources, market_json=market, industry_json=industry)
    except (OSError, ValueError, TypeError, KeyError, RecursionError,
            UnicodeError):
        result = _verification("FAIL", "LOCAL_INPUT_UNAVAILABLE")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
