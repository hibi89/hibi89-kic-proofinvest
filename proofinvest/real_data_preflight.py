"""KUODRA P49: one-shot, no-network preflight for legally supplied local files.

Uses the existing checked SEC ZIP, source-pinned Guard, and market/industry
parsers. Never authenticates the sender, market vendor, publication timestamp,
adjusted prices, corporate actions, redistribution rights or economic truth.
No persistent originals, reports, SQLite, HTTP, AI, trades or uploads.
"""
from __future__ import annotations

import argparse
from datetime import datetime, date, timezone
import re
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from .guard_audit import GuardAuditStore
from disclosure_lightning.core import MAX_JSON_BYTES
from disclosure_lightning.originals import MAX_FILING_BYTES
from .industry_vision import MAX_UPLOAD_BYTES as INDUSTRY_MAX
from .local_sec_guard_report import review_local_sec_with_guard
from .local_sec_html_report import render_local_sec_html
from .local_sec_packet import _read_regular_local, _MAX_FILE_BYTES
from .market_price_csv import market_price_csv_to_json
from .market_data_evidence import validate_market_evidence
from .market_reality import (
    MAX_UPLOAD_BYTES as MARKET_MAX, analyze_market_reality,
    parse_market_reality_json,
)
from .sec_bundle_replay import _receipt_capture_clock
from .sec_capture_bundle import _read_checked_capture_bundle
from .three_engine_research import bind_industry_to_sec, summarize_three_engines


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.offline-real-file-preflight.v1",
        "status": "blocked",
        "reason_code": reason,
        "sec_capture_digest_matched": False,
        "sec_input_mode": None,
        "sec_local_byte_sha256_computed": False,
        "issuer_cik": None,
        "as_of_self_reported": None,
        "sec_accession": None,
        "guard_decision_unchanged": None,
        "source_authenticated": False,
        "historical_market_vintage_authenticated": False,
        "corporate_actions_verified": False,
        "data_rights_verified": False,
        "point_in_time_backtest_verified": False,
        "industry_outlook_verified": False,
        "three_engine_real_world_validated": False,
        "external_http_called": False,
        "ai_generated": False,
        "trade_executed": False,
        "audit_retained": False,
    }


def inspect_offline_data_files(
    sec_bundle: Path | None = None, *, prior_end: str, current_end: str, needle: str,
    market_csv: Path | None = None, symbol: str | None = None,
    benchmark: str | None = None, return_basis: str | None = None,
    market_source_url: str | None = None,
    market_published_at: str | None = None,
    industry_json: Path | None = None,
    market_evidence_json: Path | None = None,
    sec_submissions: Path | None = None,
    sec_companyfacts: Path | None = None,
    sec_filing: Path | None = None,
    issuer_cik: str | None = None,
    accession: str | None = None,
    as_of: str | None = None,
    collected_at: str | None = None,
) -> dict[str, Any]:
    """Run real-file *format and local-integrity* gates; fail closed.

    All file paths are supplied explicitly. A pass means locally consistent
    bytes and declared dates, NOT verified real SEC or vendor source data.
    """
    blocked = _base("PRECHECK_FAILED")
    direct_fields = (sec_submissions, sec_companyfacts, sec_filing,
                     issuer_cik, accession, as_of, collected_at)
    direct_present = any(v is not None for v in direct_fields)
    # Exactly one mode; no silent fallback to unrelated original files.
    if sec_bundle is not None and direct_present:
        return {**blocked, "reason_code": "MIXED_SEC_INPUT_MODES_BLOCKED"}
    if sec_bundle is None and not all(v is not None for v in direct_fields):
        return {**blocked, "reason_code": "INCOMPLETE_DIRECT_SEC_THREE_FILES"}
    if sec_bundle is not None:
        integrity, raws, receipt = _read_checked_capture_bundle(Path(sec_bundle))
        if (integrity.get("status") != "bundle_integrity_pass_origin_unverified"
                or raws is None or receipt is None):
            return {**blocked, "reason_code": "SEC_ZIP_INTEGRITY_OR_MANIFEST_INVALID"}
        captured = _receipt_capture_clock(receipt)
        if captured is None:
            return {**blocked, "reason_code": "SEC_ZIP_CAPTURE_CLOCK_INVALID"}
        cik, asof, acc = (receipt[k] for k in (
            "issuer_cik", "observed_utc_day", "accession",
        ))
        input_mode = "CAPTURE_ZIP_SELF_REPORTED"
        bundle_match = True
    else:
        # Bounded, non-symlink, no-follow reads. The existing SEC/Guard
        # validators check issuer, accession, filing and numeric claims.
        if (type(issuer_cik) is not str
                or re.fullmatch(r"[0-9]{10}", issuer_cik, re.ASCII) is None
                or issuer_cik == "0000000000"
                or type(accession) is not str
                or re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}",
                                accession, re.ASCII) is None
                or type(as_of) is not str
                or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}",
                                as_of, re.ASCII) is None
                or type(collected_at) is not str):
            return {**blocked, "reason_code": "DIRECT_SEC_METADATA_INVALID"}
        try:
            if date.fromisoformat(as_of).isoformat() != as_of:
                raise ValueError("INVALID_DATE")
            timestamp = datetime.fromisoformat(collected_at.replace("Z", "+00:00"))
            if (timestamp.tzinfo is None or timestamp.utcoffset() is None
                    or timestamp.utcoffset().total_seconds() != 0
                    or timestamp.astimezone(timezone.utc).date().isoformat() != as_of):
                raise ValueError("INVALID_CAPTURE_TIME")
            # Require an explicit timezone marker, not an accidentally
            # parser-accepted naive or variable date/time notation.
            if (re.fullmatch(
                    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
                    r"(?:Z|\+00:00)", collected_at, re.ASCII
                ) is None):
                raise ValueError("CAPTURE_TIME_FORMAT")
            raws = {
                "submissions": _read_regular_local(
                    Path(sec_submissions), MAX_JSON_BYTES),
                "companyfacts": _read_regular_local(
                    Path(sec_companyfacts), _MAX_FILE_BYTES),
                "original_filing": _read_regular_local(
                    Path(sec_filing), MAX_FILING_BYTES),
            }
        except (ValueError, TypeError, OSError, OverflowError) :
            return {**blocked, "reason_code": "DIRECT_SEC_BYTES_OR_CLOCK_INVALID"}
        cik, asof, acc = issuer_cik, as_of, accession
        captured = timestamp.isoformat()
        integrity = {"sha256": {k: sha256(v).hexdigest()
                                for k, v in raws.items()}}
        input_mode = "DIRECT_THREE_FILES_UNAUTHENTICATED"
        bundle_match = False
    blocked.update({
        "sec_capture_digest_matched": bundle_match,
        "sec_input_mode": input_mode, "sec_local_byte_sha256_computed": True,
        "issuer_cik": cik, "as_of_self_reported": asof,
        "sec_accession": acc,
    })
    has_market = market_csv is not None
    has_industry = industry_json is not None
    has_evidence = market_evidence_json is not None
    if has_evidence and not has_market:
        return {**blocked, "reason_code": "MARKET_EVIDENCE_WITHOUT_PRICE_CSV"}
    if has_market and return_basis == "ADJUSTED_CLOSE_TOTAL_RETURN_PROXY" and not has_evidence:
        return {**blocked, "reason_code": "ADJUSTED_PRICE_REQUIRES_EVIDENCE_MANIFEST"}
    if has_market and any(type(field) is not str or not field
                          for field in (symbol, benchmark, return_basis,
                                        market_source_url, market_published_at)):
        return {**blocked, "reason_code": "MARKET_METADATA_REQUIRED"}
    if not has_market and any(field is not None for field in (
            symbol, benchmark, return_basis, market_source_url,
            market_published_at)):
        return {**blocked, "reason_code": "MARKET_METADATA_WITHOUT_FILE"}

    try:
        # All guard writes are isolated in a temporary directory that is
        # destroyed before return. This does not authorize SEC data retention.
        with TemporaryDirectory(prefix="kuodra-preflight-") as tmp:
            db = Path(tmp) / "audit.sqlite"
            report = review_local_sec_with_guard(
                submissions_json=raws["submissions"],
                companyfacts_json=raws["companyfacts"],
                original_filing=raws["original_filing"],
                cik=cik, accession=acc, as_of=asof, collected_at=captured,
                current_end=current_end, prior_end=prior_end,
                needle=needle, audit_db_path=db,
                run_id="offline-preflight", expected_source_sha256={
                    key: integrity["sha256"][key] for key in (
                        "submissions", "companyfacts", "original_filing",
                    )
                },
            )
            if not GuardAuditStore(db).verify_chain():
                return {**blocked, "reason_code": "TEMPORARY_GUARD_CHAIN_FAILED"}
            if (report["issuer"]["cik"] != cik
                    or report["issuer"]["as_of"] != asof
                    or report["source"]["companyfacts_sha256"]
                       != integrity["sha256"]["companyfacts"]
                    or report["guard"]["decision"] not in ("HOLD", "REJECT")
                    or report["guard"]["source_authenticated"] is not False):
                return {**blocked, "reason_code": "SEC_GUARD_CONTEXT_MISMATCH"}
            csv_source_digest = None
            market_evidence_status = "NO_INPUT"
            market_evidence_digest = None
            market_evidence_vintage = "NO_INPUT"
            if has_market:
                original_csv = _read_regular_local(Path(market_csv), MARKET_MAX)
                csv_source_digest = sha256(original_csv).hexdigest()
                normalized = market_price_csv_to_json(
                    original_csv, issuer_cik=cik, as_of=asof,
                    symbol=symbol, benchmark=benchmark, return_basis=return_basis,
                    source_url=market_source_url,
                    published_at=market_published_at,
                )
                if has_evidence:
                    evidence_bytes = _read_regular_local(
                        Path(market_evidence_json), 8_192
                    )
                    evidence_result = validate_market_evidence(
                        evidence_bytes, csv_bytes=original_csv,
                        normalized_market_payload=parse_market_reality_json(normalized),
                    )
                    market_evidence_status = evidence_result["status"]
                    market_evidence_digest = evidence_result["metadata_sha256"]
                    market_evidence_vintage = evidence_result["claimed_vintage_status"]
                    if (evidence_result["source_authenticated"] is not False
                            or evidence_result["corporate_actions_verified"] is not False
                            or evidence_result["data_rights_verified"] is not False
                            or evidence_result["point_in_time_backtest_verified"] is not False):
                        return {**blocked, "reason_code": "EVIDENCE_TRUST_CONTRACT_INVALID"}
                else:
                    market_evidence_status = "MISSING_OPERATOR_EVIDENCE"
                    market_evidence_vintage = "NO_OPERATOR_EVIDENCE"
                market = analyze_market_reality(
                    parse_market_reality_json(normalized),
                    expected_issuer_cik=cik, analysis_as_of=asof,
                    sec_review=report,
                    uploaded_sha256=sha256(normalized).hexdigest(),
                )
                if (market["source"]["stock"]["sha256_reported"]
                        != csv_source_digest
                        or market["source_authenticated"] is not False
                        or market["point_in_time_backtest_verified"] is not False):
                    return {**blocked, "reason_code": "MARKET_BYTES_OR_TRUST_MISMATCH"}
                report["market_reality"] = market
            industry_source_digest = None
            if has_industry:
                industry_raw = _read_regular_local(Path(industry_json), INDUSTRY_MAX)
                industry_source_digest = sha256(industry_raw).hexdigest()
                vision = bind_industry_to_sec(report, industry_raw)
                if vision["input_sha256"] != industry_source_digest:
                    return {**blocked, "reason_code": "INDUSTRY_BYTES_MISMATCH"}
                report["industry_vision"] = vision
            report["three_engine_summary"] = summarize_three_engines(report)
            html = render_local_sec_html(report)
            if not isinstance(html, bytes) or not html:
                return {**blocked, "reason_code": "FINAL_LOCAL_HTML_INVALID"}

            ledger = report["three_engine_summary"]
            return {
                **blocked, "status": "local_structure_pass_origin_unverified",
                "reason_code": "LOCAL_ONLY_REVIEW_NOT_REAL_DATA_AUTHENTICATION",
                "guard_decision_unchanged": report["guard"]["decision"],
                "sec_revenue_status": report["verification"]["status"],
                "accounting_status": report["accounting_integrity"]["status"],
                "market_status": (
                    report["market_reality"]["status"] if has_market
                    else "NO_INPUT"
                ),
                "market_sec_context_temporal_status": (
                    report["market_reality"]["sec_context_temporal_status"]
                    if has_market else "NO_INPUT"
                ),
                "industry_status": (
                    report["industry_vision"]["status"] if has_industry
                    else "NO_INPUT"
                ),
                "all_three_inputs_present": ledger["all_three_inputs_present"],
                "sec_source_sha256": dict(integrity["sha256"]),
                "market_csv_original_sha256": csv_source_digest,
                "market_evidence_status": market_evidence_status,
                "market_evidence_sha256": market_evidence_digest,
                "market_evidence_vintage": market_evidence_vintage,
                "industry_original_sha256": industry_source_digest,
                "rendered_report_sha256_not_persisted": sha256(html).hexdigest(),
                "limitations": [
                    "Matching local SHA and data contracts do not certify issuer, provider, license, or true publication time.",
                    "Corporate actions and adjusted-close history are not independently audited.",
                    "Historical price backtests and sector vision remain unverified.",
                    "Temporary Guard audit is deleted; no persistent permission or trading authorization.",
                ],
            }
    except (ValueError, TypeError, KeyError, OSError, OverflowError,
            RecursionError, UnicodeError):
        return {**blocked, "reason_code": "OPTIONAL_OR_SEC_INPUT_FAILED_CLOSED"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline, read-only KUODRA SEC + market + industry file preflight (NO provider API)."
    )
    parser.add_argument("--sec-bundle", type=Path)
    parser.add_argument("--sec-submissions", type=Path)
    parser.add_argument("--sec-companyfacts", type=Path)
    parser.add_argument("--sec-filing", type=Path)
    parser.add_argument("--issuer-cik")
    parser.add_argument("--accession")
    parser.add_argument("--as-of")
    parser.add_argument("--collected-at")
    parser.add_argument("--prior-end", required=True)
    parser.add_argument("--current-end", required=True)
    parser.add_argument("--needle", required=True)
    parser.add_argument("--market-csv", type=Path)
    parser.add_argument("--market-evidence-json", type=Path)
    parser.add_argument("--symbol")
    parser.add_argument("--benchmark")
    parser.add_argument("--return-basis")
    parser.add_argument("--market-source-url")
    parser.add_argument("--market-published-at")
    parser.add_argument("--industry-json", type=Path)
    args = parser.parse_args(argv)
    result = inspect_offline_data_files(
        args.sec_bundle, prior_end=args.prior_end,
        current_end=args.current_end, needle=args.needle,
        market_csv=args.market_csv, symbol=args.symbol,
        benchmark=args.benchmark, return_basis=args.return_basis,
        market_source_url=args.market_source_url,
        market_published_at=args.market_published_at,
        industry_json=args.industry_json,
        market_evidence_json=args.market_evidence_json,
        sec_submissions=args.sec_submissions,
        sec_companyfacts=args.sec_companyfacts,
        sec_filing=args.sec_filing,
        issuer_cik=args.issuer_cik,
        accession=args.accession,
        as_of=args.as_of,
        collected_at=args.collected_at,
    )
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
    return 0 if result["status"] == "local_structure_pass_origin_unverified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
