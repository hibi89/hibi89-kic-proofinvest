"""Read-only local SEC-format peer revenue binding for KUODRA Engine C.

This checks SEC-shaped CompanyFacts *bytes* against declared industry peers.
It neither fetches originals nor authenticates the provider, license or vintage.
"""
from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
import re
from typing import Any

from .industry_vision import parse_industry_vision_json, analyze_industry_vision
from .local_sec_packet import _json_object, _MAX_FILE_BYTES
from .sec_companyfacts import verify_sec_annual_revenue

_MAX_PEERS = 8
_MAX_TOTAL_PEER_BYTES = 48_000_000
_CIK = re.compile(r"[0-9]{10}\Z", re.ASCII)
_ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}\Z", re.ASCII)


def bind_peer_companyfacts_to_industry(
    industry_raw: bytes, *, peer_sources: list[tuple[str, str, bytes]],
) -> dict[str, Any]:
    """Require all declared peers to agree with original local CompanyFacts bytes.

    Each entry: (peer_cik, filing_accession, exact CompanyFacts JSON bytes).
    The industry's prior/current source IDs must BOTH hash to these same
    CompanyFacts bytes and use the canonical *claimed* SEC data URL. A claimed
    URL is never proof that the bytes were actually downloaded from there.
    """
    payload = parse_industry_vision_json(industry_raw)
    # Validate chronology, industry and company contracts before using inputs.
    analyze_industry_vision(payload)
    peers = payload["peers"]
    if (type(peer_sources) is not list or
            not 1 <= len(peer_sources) <= _MAX_PEERS or
            len(peer_sources) != len(peers)):
        raise ValueError("PEER_FACTS_COMPLETE_COVERAGE_REQUIRED")
    indexed = {peer["cik"]: peer for peer in peers}
    sources = {src["id"]: src for src in payload["sources"]}
    receipts = []
    seen: set[str] = set()
    aggregate = 0
    for peer in peer_sources:
        if (type(peer) is not tuple or len(peer) != 3 or
                type(peer[0]) is not str or
                _CIK.fullmatch(peer[0]) is None or
                type(peer[1]) is not str or
                _ACCESSION.fullmatch(peer[1]) is None or
                type(peer[2]) is not bytes):
            raise ValueError("PEER_FACTS_INPUT_INVALID")
        cik, accession, raw = peer
        if cik in seen or cik not in indexed or cik == payload["issuer_cik"]:
            raise ValueError("PEER_FACTS_CIK_MISMATCH_OR_DUPLICATE")
        seen.add(cik)
        aggregate += len(raw)
        if not 0 < len(raw) <= _MAX_FILE_BYTES or aggregate > _MAX_TOTAL_PEER_BYTES:
            raise ValueError("PEER_FACTS_BYTES_OVER_BUDGET")
        digest = sha256(raw).hexdigest()
        record = indexed[cik]
        claim = verify_sec_annual_revenue(
            _json_object(raw, limit=_MAX_FILE_BYTES),
            cik=cik, accession=accession,
            current_end=payload["current_period_end"],
            prior_end=payload["prior_period_end"],
            as_of=payload["as_of"],
        )
        if (claim.get("status") != "calculated_unverified" or
                claim.get("authenticated_external_source") is not False or
                claim.get("source_rights_verified") is not False or
                claim.get("live_api_called") is not False):
            raise ValueError("PEER_FACTS_FINANCIAL_UNAVAILABLE_OR_UNTRUSTED")
        if (Decimal(record["prior_revenue_usd"]) != Decimal(claim["prior_usd"])
                or Decimal(record["current_revenue_usd"]) !=
                   Decimal(claim["current_usd"])):
            raise ValueError("PEER_FACTS_REVENUE_CONFLICT")
        expected_url = (
            "https://data.sec.gov/api/xbrl/companyfacts/CIK" + cik + ".json"
        )
        for field in ("prior_source_id", "current_source_id"):
            ref = sources[record[field]]
            if (ref["sha256"] != digest or
                    ref["url"] != expected_url or
                    ref["published_at"] != claim["filing_date"]):
                raise ValueError("PEER_FACTS_SOURCE_HASH_OR_DATE_MISMATCH")
        receipts.append({
            "peer_cik": cik,
            "companyfacts_sha256": digest,
            "accession": accession,
            "filing_date_self_reported": claim["filing_date"],
            "revenue_concept": claim["revenue_concept"],
            "prior_revenue_usd": claim["prior_usd"],
            "current_revenue_usd": claim["current_usd"],
            "growth_pct": claim["growth_pct"],
        })
    if seen != set(indexed):
        raise ValueError("PEER_FACTS_COMPLETE_COVERAGE_REQUIRED")
    return {
        "schema": "kuodra.industry-peer-companyfacts-binding.v1",
        "status": "local_peer_values_hash_matched_origin_unverified",
        "peer_count": len(receipts),
        "peer_records": sorted(receipts, key=lambda x: x["peer_cik"]),
        "source_authenticated": False,
        "source_rights_verified": False,
        "point_in_time_provider_vintage_authenticated": False,
        "live_sec_called": False,
        "audit_written": False,
        "trade_executed": False,
    }
