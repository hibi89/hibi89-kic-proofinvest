"""P144: restore one existing operator SEC source ZIP into the seven-tool path.

This is a *local fallback*, not an automatic SEC/third-party feed. The
SEC-shaped Submissions JSON's tickers/name are caller-controlled: its
single-row derived lookup is never an authenticated company_tickers.json.
No network, extraction, storage, model call, licensing or trade.
"""
from __future__ import annotations

from datetime import datetime, timezone, date
from hashlib import sha256
import json
import re
from typing import Any

from .operator_sec_zip import read_operator_sec_zip_bytes
from .ticker_research_intake import (
    _json, _TICKER, MAX_SUBMISSIONS_BYTES, build_ticker_source_plan,
)
from .ticker_sec_financial_bridge import _LIMITS


def restore_operator_zip_for_ticker(
    archive: bytes, *, ticker: str, as_of: str,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    """Return four in-memory source bytes and a redacted provenance warning.

    Exactly one existing operator ZIP with three SEC-shaped files is accepted.
    Reconstruct the missing ticker map from *untrusted submissions metadata*,
    not from an official ticker-map GET. The selected 10-K accession must
    equal the ZIP's claimed accession. All canonical seven-step checks still
    execute afterward; this is not a license to omit them.
    """
    if type(ticker) is not str or _TICKER.fullmatch(ticker) is None:
        raise ValueError("OPERATOR_ZIP_TICKER_INVALID")
    if type(as_of) is not str:
        raise ValueError("OPERATOR_ZIP_AS_OF_INVALID")
    try:
        cutoff = date.fromisoformat(as_of)
        if (cutoff.isoformat() != as_of
                or cutoff > datetime.now(timezone.utc).date()):
            raise ValueError("OPERATOR_ZIP_AS_OF_INVALID")
    except (ValueError, OverflowError) as exc:
        raise ValueError("OPERATOR_ZIP_AS_OF_INVALID") from exc
    source, claims = read_operator_sec_zip_bytes(archive)
    if claims["as_of"] != as_of:
        raise ValueError("OPERATOR_ZIP_AS_OF_MISMATCH")
    submissions = _json(source["submissions"], MAX_SUBMISSIONS_BYTES, "SUBMISSIONS")
    # SEC-shaped submissions supply zero or more listed symbols, not the
    # independent company_tickers.json global mapping. Reject ambiguity.
    symbols = submissions.get("tickers")
    if (type(symbols) is not list or not 1 <= len(symbols) <= 512
            or any(type(v) is not str for v in symbols)
            or symbols.count(ticker) != 1):
        raise ValueError("OPERATOR_ZIP_TICKER_NOT_UNAMBIGUOUS")
    title = submissions.get("name")
    if (type(title) is not str or not 0 < len(title) <= 250
            or any(ord(c) < 32 or ord(c) == 127 for c in title)):
        raise ValueError("OPERATOR_ZIP_NAME_INVALID")
    cik = claims["issuer_cik"]
    if (type(submissions.get("cik")) not in (int, str)
            or type(submissions["cik"]) is bool
            or not str(submissions["cik"]).isascii()
            or not str(submissions["cik"]).isdecimal()
            or str(int(submissions["cik"])).zfill(10) != cik):
        raise ValueError("OPERATOR_ZIP_CIK_MISMATCH")
    synthesized_map = json.dumps({
        "0": {"cik_str": int(cik), "ticker": ticker, "title": title}
    }, ensure_ascii=True, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("ascii")
    plan = build_ticker_source_plan(
        ticker=ticker, ticker_map=synthesized_map,
        submissions=source["submissions"], as_of=as_of,
    )
    filing = plan.get("latest_10k")
    if (plan.get("status") != "10k_source_plan_unverified"
            or plan.get("cik") != cik or type(filing) is not dict
            or filing.get("accession") != claims["accession"]):
        raise ValueError("OPERATOR_ZIP_FILING_OR_SOURCE_PLAN_MISMATCH")
    restored = {
        "ticker_map": synthesized_map,
        "submissions": source["submissions"],
        "companyfacts": source["companyfacts"],
        "original_10k": source["original_filing"],
    }
    if any(not 0 < len(raw) <= _LIMITS[key]
           for key, raw in restored.items()):
        raise ValueError("OPERATOR_ZIP_DOWNSTREAM_SOURCE_LIMIT")
    receipt = {
        "schema": "kuodra.operator-zip-to-seven-tool-intake.v1",
        "status": "LOCAL_OPERATOR_ZIP_DERIVED_TICKER_MAP_UNVERIFIED",
        "ticker": ticker, "issuer_cik": cik, "as_of": as_of,
        "selected_10k_accession": filing["accession"],
        "ticker_map_derivation": "SELF_REPORTED_SUBMISSIONS_TICKER_NOT_OFFICIAL_MAP",
        "ticker_map_sha256": sha256(synthesized_map).hexdigest(),
        "operator_archive_sha256": sha256(archive).hexdigest(),
        "source_sha256": {key: sha256(raw).hexdigest()
                          for key, raw in restored.items()},
        "source_authenticated": False,
        "source_rights_verified": False,
        "independent_ticker_registry_verified": False,
        "external_http_attempted": False,
        "guard_executed": False, "audit_written": False,
        "trade_executed": False,
    }
    return restored, receipt
