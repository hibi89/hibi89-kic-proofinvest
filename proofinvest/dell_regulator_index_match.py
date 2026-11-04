"""P203 reconcile independently published SEC EDGAR index with issuer 10-K.

The SEC official filing index is reviewed manually on 2026-11-05.
Network calls: ZERO, including no retry of P105 SEC 403.
Publisher first-party 10-K raw receipt from real P195 and FY2026 iXBRL
from P198 are pinned. Checks issuer CIK, accession, year and original URL;
does NOT prove regulator raw-byte equality, copyright, NDx/AI rights.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from .dell_2026_publisher_evidence import actual_p195_source_receipt
from .dell_2026_ixbrl_review import observed_ixbrl_receipt

_SEC_INDEX = {
    "url": ("https://www.sec.gov/Archives/edgar/data/1571996/"
            "000157199626000008/0001571996-26-000008-index.htm"),
    "issuer": "Dell Technologies Inc.", "cik": "0001571996",
    "accession": "0001571996-26-000008", "form": "10-K",
    "document": "dell-20260130.htm", "filed": "2026-03-16",
    "fiscal_end": "2026-01-30", "document_size_index_bytes": 3552634,
    "source_reviewed": "2026-11-05",
}


def official_sec_index_reference() -> dict[str, Any]:
    return dict(_SEC_INDEX)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.p203-independent-regulator-issuer-index-match.v1",
        "status": "BLOCKED", "reason_code": reason, "evidence": None,
        "independent_regulator_index_metadata_reconciled": False,
        "issuer_xbrl_fiscal_context_matched": False,
        "real_issuer_raw_source_observed": False,
        "raw_sec_edgar_original_authenticated": False,
        "sec_original_bytes_obtained": False,
        "commercial_and_model_processing_rights_proven": False,
        "licensed_real_stock_ndx_peers": False,
        "full_abc_engine_ready": False,
        "guard_policy_preview": "HOLD", "trade_executed": False,
        "network_requests": 0, "external_ai_requests": 0,
    }


def verify_regulator_issuer_filing_index(
    *, reviewed_as_of: str, index: dict, publisher: dict, xbrl: dict,
) -> dict[str, Any]:
    try:
        if (type(reviewed_as_of) is not str or reviewed_as_of != "2026-11-05"
                or date.fromisoformat(reviewed_as_of) <
                date.fromisoformat(_SEC_INDEX["filed"])):
            return _blocked("SEC_INDEX_VINTAGE_INVALID")
        if type(index) is not dict or index != _SEC_INDEX:
            return _blocked("SEC_OFFICIAL_INDEX_METADATA_UNVERIFIED")
        if (type(publisher) is not dict
                or publisher != actual_p195_source_receipt()
                or type(xbrl) is not dict or xbrl != observed_ixbrl_receipt()):
            return _blocked("PUBLISHER_ACTUAL_ORIGINAL_CI_RECEIPT_CHANGED")
        idx = index
        src_url = publisher["public_issuer_report_url"]
        parsed_cik = idx["accession"].split("-")[0]
        if (parsed_cik != idx["cik"]
                or idx["form"] != "10-K"
                or idx["accession"] not in src_url
                or idx["document"] != src_url.rsplit("/",1)[-1]
                or idx["fiscal_end"] != publisher["fy2026_end"]
                or idx["fiscal_end"] != xbrl["xbrl_facts"]["FY2026"]["period_end"]
                or publisher["ticker"] != "DELL"
                or publisher["issuer_https_host_verified"] is not True
                or publisher["issuer_html_10k_numbers_crosschecked"] is not True
                or publisher["source_rights_verified"] is not False
                or publisher["sec_edgar_identical_original_verified"] is not False
                or xbrl["source_url"] != src_url
                or xbrl["source_sha256"] != publisher["source_original_sha256"]
                or xbrl["source_bytes"] != publisher["source_original_bytes"]
                or xbrl["xbrl_concept"] != "us-gaap:revenues"
                or xbrl["origin_sec_edgar_byte_identical"] is not False
                or xbrl["xbrl_facts"]["FY2026"]["amount_usd_millions"] !=
                   publisher["annual_net_revenue_2026_usd_millions"]
                or xbrl["xbrl_facts"]["FY2025"]["amount_usd_millions"] !=
                   publisher["annual_net_revenue_2025_usd_millions"]):
            return _blocked("SEC_INDEX_CIK_ACCESSION_SOURCE_FY_MISMATCH")
        issuer_size = publisher["source_original_bytes"]
        index_size = idx["document_size_index_bytes"]
        if type(issuer_size) is not int or type(index_size) is not int:
            return _blocked("DOCUMENT_SIZE_TYPE_INVALID")
        return {
            **_blocked("INDEX_METADATA_ONLY_NO_SEC_RAW_BYTE_ATTESTATION"),
            "status": "INDEPENDENT_SEC_FILING_INDEX_MATCHED_WITH_LIVE_ISSUER_XBRL",
            "independent_regulator_index_metadata_reconciled": True,
            "issuer_xbrl_fiscal_context_matched": True,
            "real_issuer_raw_source_observed": True,
            "evidence": {
                "issuer": idx["issuer"], "ticker": "DELL",
                "cik": idx["cik"], "accession": idx["accession"],
                "form": idx["form"], "report_end": idx["fiscal_end"],
                "filing_date": idx["filed"], "regulator_index_url": idx["url"],
                "publisher_official_url": src_url,
                "publisher_sha256": publisher["source_original_sha256"],
                "publisher_file_bytes": issuer_size,
                "sec_index_document_size_bytes": index_size,
                "index_and_publisher_display_sizes_differ": issuer_size != index_size,
                "regulator_original_not_downloaded": True,
                "actual_raw_issuer_ci_run": (
                    "https://github.com/hibi89/hibi89-kic-proofinvest/"
                    "actions/runs/41881814888"),
                "actual_ixbrl_ci_run": xbrl["ci_run"],
            },
        }
    except (KeyError, ValueError, TypeError, OverflowError, RecursionError):
        return _blocked("SEC_INDEX_RECEIPT_MALFORMED")


def reviewed_real_dell_regulator_issuer_evidence() -> dict[str, Any]:
    return verify_regulator_issuer_filing_index(
        reviewed_as_of="2026-11-05",
        index=official_sec_index_reference(),
        publisher=actual_p195_source_receipt(),
        xbrl=observed_ixbrl_receipt(),
    )
