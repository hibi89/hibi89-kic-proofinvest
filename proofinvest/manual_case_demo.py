"""Offline manual-issuer case; no live API, downloaded PDF or invented Risk facts.

The historical 2024 / 2023 Samsung amounts were transcribed from an issuer
statement by a previous reviewer, NOT checked again during this execution.
An issuer page lists that source's publication date as 2025-02-18.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from typing import Any

from .evidence_chain import evaluate_offline_chain
from .evidence_scenarios import EVIDENCE_PATH

IR_PAGE = "https://www.samsung.com/global/ir/reports-disclosures/public-disclosure-view.84315/"
IR_PUBLICATION_DATE = "2025-02-18"
EXPECTED_PDF = ("https://images.samsung.com/is/content/samsung/assets/global/"
                "ir/docs/2025_SEC_Consolidated_Financial_statements.pdf")



# Pin the exact bytes of the originally reviewed, public repository JSON.
# This is a Git blob object id, NOT authentication of the remote issuer PDF.
REVIEWED_GIT_BLOB_SHA1 = "5535653a44297cc34022709be264801402688ecf"


def read_reviewed_evidence() -> dict[str, Any]:
    raw = EVIDENCE_PATH.read_bytes()
    object_id = hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
    ).hexdigest()
    if object_id != REVIEWED_GIT_BLOB_SHA1:
        # Diagnose Windows core.autocrlf without trusting normalized data.
        # Only exact bytes of the previously reviewed Git blob are accepted.
        if b"\r\n" in raw:
            original = raw.replace(b"\r\n", b"\n")
            original_sha = hashlib.sha1(
                b"blob " + str(len(original)).encode("ascii") + b"\0" + original
            ).hexdigest()
            if original_sha == REVIEWED_GIT_BLOB_SHA1:
                raise ValueError(
                    "Previously reviewed evidence bytes changed by CRLF checkout "
                    "conversion; restore the original Git blob bytes before replay"
                )
        raise ValueError("Previously reviewed evidence bytes changed; re-review before replay")
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Pinned evidence is not an object")
    return data


def make_research_request(evidence: dict[str, Any]) -> dict[str, Any]:
    primary = evidence.get("primary_source")
    if not isinstance(primary, dict) or primary.get("url") != EXPECTED_PDF:
        raise ValueError("Pinned issuer source changed")
    if evidence.get("corp_code") != "00126380" or evidence.get("report_year") != 2024:
        raise ValueError("Pinned issuer or report year changed")
    reviewed_at = evidence.get("evidence_date_kst")
    if reviewed_at != "2026-10-24":
        raise ValueError("Unexpected original evidence-review date")
    return {
        "target_name": "Samsung Electronics Co., Ltd. and its subsidiaries",
        "target_id": evidence["corp_code"],
        "as_of": reviewed_at,
        "sources": [{
            "id": "SAMSUNG_2024_CONSOLIDATED_IR",
            "title": "2024 Consolidated Financial Statements",
            "url": EXPECTED_PDF,
            "published_at": IR_PUBLICATION_DATE,
            "collected_at": reviewed_at,
            "license": "RIGHTS_NOT_VERIFIED_NO_REPUBLICATION_PERMISSION",
        }],
        "findings": [{
            "claim": "Issuer statement is the manually reviewed 2024/2023 revenue reference",
            "source_ids": ["SAMSUNG_2024_CONSOLIDATED_IR"],
            "as_of": reviewed_at,
        }],
    }


def run_manual_case(claim: str = "16.20") -> dict[str, Any]:
    """Return the source-linked manual case; withhold absent balance-sheet Risk."""
    evidence = read_reviewed_evidence()
    if not isinstance(evidence, dict):
        raise ValueError("Invalid pinned issuer evidence")
    result = evaluate_offline_chain(
        research_request=make_research_request(evidence),
        financial_evidence=evidence,
        claimed_growth_pct=claim,
        risk_facts=None,
    )
    return {
        **result,
        "issuer_ir_listing": IR_PAGE,
        "issuer_ir_listed_at": IR_PUBLICATION_DATE,
        "manual_evidence_record": "docs/evidence/samsung_2024_cfs_revenue.json",
        "reviewed_record_git_blob_sha1": REVIEWED_GIT_BLOB_SHA1,
        "latest_fiscal_year_claimed": False,
        "actual_pdf_reopened_on_this_execution": False,
        "dart_viewer_accessed_on_this_execution": False,
        "risk_unavailable_due_to_missing_balance_sheet_evidence": True,
        "notice": (
            "The revenue claim is compared with manually transcribed issuer amounts; "
            "no independent DART authentication. No liabilities/equity Risk score inferred."
        ),
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Manual Samsung FY2024 source-linked offline demo")
    p.add_argument("--claim", default="16.20", help="Claimed 2024 vs 2023 revenue growth percent")
    args = p.parse_args()
    print(json.dumps(run_manual_case(args.claim), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
