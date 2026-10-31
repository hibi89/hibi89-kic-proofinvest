"""KUODRA P49: one-shot, no-network preflight for legally supplied local files.

Uses the existing checked SEC ZIP, source-pinned Guard, and market/industry
parsers. Never authenticates the sender, market vendor, publication timestamp,
adjusted prices, corporate actions, redistribution rights or economic truth.
No persistent originals, reports, SQLite, HTTP, AI, trades or uploads.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from .guard_audit import GuardAuditStore
from .industry_vision import MAX_UPLOAD_BYTES as INDUSTRY_MAX
from .local_sec_guard_report import review_local_sec_with_guard
from .local_sec_html_report import render_local_sec_html
from .local_sec_packet import _read_regular_local
from .market_price_csv import market_price_csv_to_json
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
    sec_bundle: Path, *, prior_end: str, current_end: str, needle: str,
    market_csv: Path | None = None, symbol: str | None = None,
    benchmark: str | None = None, return_basis: str | None = None,
    market_source_url: str | None = None,
    market_published_at: str | None = None,
    industry_json: Path | None = None,
) -> dict[str, Any]:
    """Run real-file *format and local-integrity* gates; fail closed.

    All file paths are supplied explicitly. A pass means locally consistent
    bytes and declared dates, NOT verified real SEC or vendor source data.
    """
    blocked = _base("PRECHECK_FAILED")
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
    blocked.update({
        "sec_capture_digest_matched": True, "issuer_cik": cik,
        "as_of_self_reported": asof, "sec_accession": acc,
    })
    has_market = market_csv is not None
    has_industry = industry_json is not None
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
            if has_market:
                original_csv = _read_regular_local(Path(market_csv), MARKET_MAX)
                csv_source_digest = sha256(original_csv).hexdigest()
                normalized = market_price_csv_to_json(
                    original_csv, issuer_cik=cik, as_of=asof,
                    symbol=symbol, benchmark=benchmark, return_basis=return_basis,
                    source_url=market_source_url,
                    published_at=market_published_at,
                )
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
    parser.add_argument("--sec-bundle", required=True, type=Path)
    parser.add_argument("--prior-end", required=True)
    parser.add_argument("--current-end", required=True)
    parser.add_argument("--needle", required=True)
    parser.add_argument("--market-csv", type=Path)
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
    )
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
    return 0 if result["status"] == "local_structure_pass_origin_unverified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
