"""Offline KUODRA Engine C packet builder from owner-held source bytes.

No downloads, LLM, trades, provider authentication, or source retention.
Sector CSV is operator-normalized and its official provenance is NOT proven.
"""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import re
from typing import Any

from .industry_vision import analyze_industry_vision
from .industry_peer_companyfacts import bind_peer_companyfacts_to_industry
from .local_sec_packet import _json_object, _read_regular_local, _MAX_FILE_BYTES
from .sec_companyfacts import verify_sec_annual_revenue

_MAX_SECTOR_BYTES = 1_000_000
_MAX_TOTAL_FINANCIAL_BYTES = 48_000_000
_NUMBER = re.compile(r"(?:0|[1-9][0-9]{0,14})(?:\.[0-9]{1,6})?\Z")
_CIK = re.compile(r"[0-9]{10}\Z")
_ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}\Z")


def _annual(cik: str, accession: str, raw: bytes, *,
            as_of: str, prior_end: str, current_end: str) -> dict:
    if (type(cik) is not str or _CIK.fullmatch(cik) is None
            or type(accession) is not str or _ACCESSION.fullmatch(accession) is None
            or type(raw) is not bytes or not 0 < len(raw) <= _MAX_FILE_BYTES):
        raise ValueError("INVALID_LOCAL_COMPANYFACTS_SOURCE")
    verdict = verify_sec_annual_revenue(
        _json_object(raw, limit=_MAX_FILE_BYTES),
        cik=cik, accession=accession, as_of=as_of,
        prior_end=prior_end, current_end=current_end,
    )
    if (verdict.get("status") != "calculated_unverified"
            or verdict.get("source_rights_verified") is not False
            or verdict.get("authenticated_external_source") is not False
            or verdict.get("live_api_called") is not False):
        raise ValueError("COMPANYFACTS_ANNUAL_REVENUE_UNAVAILABLE")
    return verdict


def _sector_rows(raw: bytes, prior_end: str, current_end: str) -> tuple[str, str]:
    """Exactly two annual observations in an operator-normalized CSV."""
    if type(raw) is not bytes or not 0 < len(raw) <= _MAX_SECTOR_BYTES:
        raise ValueError("SECTOR_SOURCE_SIZE_INVALID")
    try:
        reader = csv.DictReader(StringIO(raw.decode("utf-8-sig"), newline=""),
                                strict=True)
        if reader.fieldnames != ["period_end", "value"]:
            raise ValueError("SECTOR_CSV_HEADER_INVALID")
        data = {}
        for row in reader:
            if (type(row) is not dict or set(row) != {"period_end", "value"}
                    or row["period_end"] not in (prior_end, current_end)
                    or type(row["value"]) is not str
                    or _NUMBER.fullmatch(row["value"]) is None
                    or row["period_end"] in data):
                raise ValueError("SECTOR_CSV_PERIOD_OR_VALUE_INVALID")
            data[row["period_end"]] = row["value"]
        if set(data) != {prior_end, current_end}:
            raise ValueError("SECTOR_CSV_INCOMPLETE_ANNUAL_PERIODS")
        return data[prior_end], data[current_end]
    except (UnicodeError, csv.Error) as exc:
        raise ValueError("SECTOR_CSV_INVALID") from None


def build_industry_packet(
    *, target: tuple[str, str, str, bytes],
    peers: list[tuple[str, str, str, bytes]],
    sector_csv: bytes, sector_url: str, sector_published_at: str,
    as_of: str, prior_end: str, current_end: str,
    industry_name: str, series_name: str, series_kind: str,
    sector_unit: str,
) -> bytes:
    """Return validated Engine C JSON, never raw financial/sector file contents.

    Target/peers are (CIK, 10-K accession, display name, raw CompanyFacts).
    All sources are operator-supplied. This is not point-in-time certification.
    """
    if (type(target) is not tuple or len(target) != 4
            or type(peers) is not list or not 1 <= len(peers) <= 8
            or any(type(row) is not tuple or len(row) != 4 for row in peers)
            or any(type(item) is not str for row in [target, *peers]
                   for item in row[:3])):
        raise ValueError("INDUSTRY_BUILDER_COMPANIES_INVALID")
    if sum(len(row[3]) for row in [target, *peers]
           if type(row[3]) is bytes) > _MAX_TOTAL_FINANCIAL_BYTES:
        raise ValueError("INDUSTRY_BUILDER_TOTAL_BYTES_INVALID")
    if (any(type(row[3]) is not bytes for row in [target, *peers])
            or len({row[0] for row in [target, *peers]}) != len(peers) + 1):
        raise ValueError("INDUSTRY_BUILDER_DUPLICATE_OR_BAD_SOURCE")
    source_rows = []
    analysis_rows = []
    for i, (cik, accession, name, raw) in enumerate([target, *peers]):
        if type(name) is not str or not 0 < len(name) <= 90:
            raise ValueError("INDUSTRY_BUILDER_NAME_INVALID")
        fact = _annual(cik, accession, raw, as_of=as_of,
                       prior_end=prior_end, current_end=current_end)
        sid = "target-companyfacts" if i == 0 else "peer-" + str(i) + "-companyfacts"
        source_rows.append({
            "id": sid,
            "url": "https://data.sec.gov/api/xbrl/companyfacts/CIK" + cik + ".json",
            "published_at": fact["filing_date"],  # claimed filing, NOT snapshot release
            "sha256": sha256(raw).hexdigest(),
        })
        analysis_rows.append({
            "cik": cik, "name": name,
            "prior_revenue_usd": fact["prior_usd"],
            "current_revenue_usd": fact["current_usd"],
            "prior_source_id": sid, "current_source_id": sid,
        })
    prior, current = _sector_rows(sector_csv, prior_end, current_end)
    source_rows.append({
        "id": "sector-normalized-csv", "url": sector_url,
        "published_at": sector_published_at,
        "sha256": sha256(sector_csv).hexdigest(),
    })
    result = {
        "schema": "kuodra.industry-vision.v1",
        "issuer_cik": target[0],
        "as_of": as_of,
        "industry": industry_name,
        "prior_period_end": prior_end,
        "current_period_end": current_end,
        "target": analysis_rows[0],
        "peers": analysis_rows[1:],
        "industry_series": {
            "name": series_name, "kind": series_kind,
            "prior_value": prior, "current_value": current,
            "prior_source_id": "sector-normalized-csv",
            "current_source_id": "sector-normalized-csv",
            "unit": sector_unit,
        },
        "drivers": [],
        "sources": source_rows,
    }
    # Only produce a packet if the existing Engine C and P66 peer gates
    # accept it. This preserves existing UI/CLI contracts and no-trust flags.
    analyzed = analyze_industry_vision(
        result, expected_issuer_cik=target[0], analysis_as_of=as_of,
    )
    if analyzed["source_authenticated"] is not False:
        raise ValueError("INDUSTRY_BUILDER_TRUST_CONTRACT")
    serialized = json.dumps(result, sort_keys=True, ensure_ascii=True,
                            separators=(",", ":")).encode("utf-8")
    checked = bind_peer_companyfacts_to_industry(
        serialized, peer_sources=[(row[0], row[1], row[3]) for row in peers],
    )
    if (checked["peer_count"] != len(peers)
            or checked["source_authenticated"] is not False):
        raise ValueError("INDUSTRY_BUILDER_PEER_GATE_INVALID")
    return serialized


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build Engine C industry JSON offline from local CompanyFacts + normalized two-row industry CSV. NO HTTP."
    )
    parser.add_argument("--target-companyfacts", type=Path, required=True)
    parser.add_argument("--target-cik", required=True)
    parser.add_argument("--target-accession", required=True)
    parser.add_argument("--target-name", required=True)
    parser.add_argument("--peer-companyfacts", type=Path, action="append", dest="peer_companyfacts", required=True)
    parser.add_argument("--peer-cik", action="append", dest="peer_ciks", required=True)
    parser.add_argument("--peer-accession", action="append", dest="peer_accessions", required=True)
    parser.add_argument("--peer-name", action="append", dest="peer_name", required=True)
    parser.add_argument("--industry-csv", type=Path, required=True)
    parser.add_argument("--sector-source-url", required=True)
    parser.add_argument("--sector-published-at", required=True)
    parser.add_argument("--industry-name", required=True)
    parser.add_argument("--series-name", required=True)
    parser.add_argument("--series-kind", required=True)
    parser.add_argument("--sector-unit", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--prior-end", required=True)
    parser.add_argument("--current-end", required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if (not 1 <= len(args.peer_ciks) <= 8
                or not (len(args.peer_ciks) == len(args.peer_accessions)
                        == len(args.peer_companyfacts)
                        == len(args.peer_name))):
            raise ValueError("PEER_INPUT_GROUP_MISMATCH")
        paths = [args.target_companyfacts, args.industry_csv,
                 *args.peer_companyfacts]
        out = args.output_json.resolve()
        if out in [p.resolve() for p in paths]:
            raise ValueError("OUTPUT_EQUALS_INPUT_BLOCKED")
        target_raw = _read_regular_local(args.target_companyfacts, _MAX_FILE_BYTES)
        peers = [
            (cik, accession, name,
             _read_regular_local(path, _MAX_FILE_BYTES))
            for cik, accession, name, path in zip(
                args.peer_ciks, args.peer_accessions,
                args.peer_name, args.peer_companyfacts,
            )
        ]
        result = build_industry_packet(
            target=(args.target_cik, args.target_accession,
                    args.target_name, target_raw),
            peers=peers,
            sector_csv=_read_regular_local(args.industry_csv, _MAX_SECTOR_BYTES),
            sector_url=args.sector_source_url,
            sector_published_at=args.sector_published_at,
            as_of=args.as_of, prior_end=args.prior_end,
            current_end=args.current_end,
            industry_name=args.industry_name, series_name=args.series_name,
            series_kind=args.series_kind, sector_unit=args.sector_unit,
        )
        # Exclusive create; never overwrite existing user data/symlinks.
        with args.output_json.open("xb") as dst:
            dst.write(result)
        print(json.dumps({
            "status": "local_industry_packet_written_origin_unverified",
            "output_sha256": sha256(result).hexdigest(),
            "peer_count": len(peers),
            "source_authenticated": False,
            "rights_verified": False,
            "real_data_verified": False,
            "external_requests": 0,
        }, sort_keys=True))
        return 0
    except (ValueError, TypeError, KeyError, OSError, OverflowError,
            UnicodeError, RecursionError):
        print(json.dumps({
            "status": "blocked",
            "reason_code": "OFFLINE_INDUSTRY_PACKET_BUILD_BLOCKED",
            "source_authenticated": False,
            "external_requests": 0,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
