"""Fail-closed origin, chronology, licensing and reuse gate for local SEC-shaped ZIPs.

SHA-256 + SEC-shaped URLs are evidence of *local byte consistency only*. No
signature, trusted capture log, provider-issued receipt or license evidence
is available in these offline bundles. Never promote user-supplied metadata.
"""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Mapping

_SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)

# Product claims are intentionally fixed. A self-reported URL, clock, rights
# assertion or copy of this dict cannot make a provider/rights check pass.
_LOCAL_ASSURANCE = {
    "schema": "proofinvest.archived-source-assurance.v1",
    "status": "LOCAL_BYTES_ONLY_EXTERNAL_ASSURANCE_BLOCKED",
    "source_claim_type": "SELF_REPORTED_ARCHIVED_SEC_SHAPED_BYTES",
    "checks": [
        {"code": "LOCAL_THREE_FILE_HASH", "status": "LOCAL_MATCH",
         "meaning": "로컬 ZIP에 저장된 3개 파일의 해시 일치만 확인"},
        {"code": "ISSUER_AND_PROVIDER_ORIGIN", "status": "NOT_ATTESTED",
         "meaning": "SEC 발행기관과 실제 공시 출처를 독립 인증하지 못함"},
        {"code": "CAPTURE_TIME_AND_ASOF", "status": "SELF_REPORTED_ONLY",
         "meaning": "기록된 수집시각·공개시점은 외부 증빙이 아님"},
        {"code": "USE_AND_REDISTRIBUTION_RIGHTS", "status": "NOT_VERIFIED",
         "meaning": "원문 재사용·재배포의 권리 및 조건을 확인하지 못함"},
        {"code": "FINANCIAL_FACT_AUTHORITY", "status": "NOT_ATTESTED",
         "meaning": "출처 및 회계 금액의 독립 검증이 수행되지 않음"},
        {"code": "EXTERNAL_AUDIT_ANCHOR", "status": "NOT_PRESENT",
         "meaning": "감사 기록은 외부 고정이 아닌 로컬 SQLite 해시 체인"},
    ],
    "software_scope_not_legal_permission": {
        "local_human_review": True,
        "local_derived_hash_and_status_export": True,
        "raw_filing_publication": False,
        "raw_filing_redistribution": False,
        "unverified_facts_as_verified_public_claims": False,
        "investment_model_authorization": False,
        "investment_advice_or_execution": False,
        "official_contest_submission": False,
    },
    "manual_requirements": [
        "INDEPENDENT_PROVIDER_ORIGIN_EVIDENCE",
        "INDEPENDENT_POINT_IN_TIME_EVIDENCE",
        "LAWFUL_USE_AND_REDISTRIBUTION_SCOPE_REVIEW",
        "INDEPENDENT_FINANCIAL_FACT_RECONCILIATION",
    ],
    "provider_authenticated": False,
    "source_rights_verified": False,
    "financial_facts_authenticated": False,
    "live_http_performed_by_this_gate": False,
}


def expected_offline_source_assurance() -> dict[str, Any]:
    """Return an independent copy; reject modifications elsewhere."""
    return deepcopy(_LOCAL_ASSURANCE)


def evaluate_local_source_assurance(replay: Any) -> dict[str, Any]:
    """Only success if a *previously validated* local replay is fail-closed.

    This is not a general SEC authentication API. The local SHA gate is a
    prerequisite, but does not replace independent issuer, time or license
    provenance.
    """
    if not isinstance(replay, Mapping):
        raise ValueError("INVALID_ARCHIVED_REPLAY_FOR_SOURCE_ASSURANCE")
    if replay.get("status") != "offline_capture_replayed_unverified":
        raise ValueError("NO_VALID_LOCAL_REPLAY")
    for flag in ("source_authenticated", "financial_values_authenticated",
                 "source_rights_verified", "external_http_called",
                 "official_contest_submission"):
        if replay.get(flag) is not False:
            raise ValueError("UNAUTHORIZED_SOURCE_PROMOTION")
    local = replay.get("local_integrity")
    span = replay.get("source_span")
    if not isinstance(local, Mapping) or not isinstance(span, Mapping):
        raise ValueError("SOURCE_DIGESTS_UNAVAILABLE")
    digests = local.get("sha256")
    if (local.get("status") != "bundle_integrity_pass_origin_unverified"
            or local.get("local_bytes_and_manifest_match") is not True
            or type(digests) is not dict
            or set(digests) != {"submissions", "companyfacts", "original_filing"}
            or any(type(value) is not str or _SHA.fullmatch(value) is None
                   for value in digests.values())
            or span.get("original_sha256") != digests["original_filing"]):
        raise ValueError("LOCAL_BYTES_NOT_ELIGIBLE_FOR_REVIEW")
    return expected_offline_source_assurance()


def validate_local_source_assurance(value: Any) -> bool:
    """Validate an exported/report/UI gate without trusting caller text."""
    return type(value) is dict and value == expected_offline_source_assurance()
