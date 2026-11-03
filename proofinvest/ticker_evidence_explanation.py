"""P158: deterministic, source-linked interpretation of a replayed KUODRA receipt.

This is NOT an LLM explanation, publisher authentication, licensed market-data
reuse permission, audit execution or investment advice. No network or storage.
Only the strict 16KiB canonical derived receipt enters this module.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from typing import Any

from .ticker_market_pair_evidence import linked_evidence_json_bytes

_SCHEMA = "kuodra.replayed-evidence-explanation.v1"


def _canonical(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def explain_linked_market_receipt(receipt: Any) -> dict:
    """Create a reviewer-visible A/B/C summary linked to exact source hashes.

    Caller still must verify_linked_market_evidence against the original local
    bytes and the paired price receipts before displaying or exporting this.
    """
    if type(receipt) is not dict:
        raise ValueError("EXPLANATION_RECEIPT_REQUIRED")
    # Includes exact schema/nested allowlists, Guard HOLD, rights flags,
    # numerical shapes, and self-consistent evidence_sha256.
    linked_evidence_json_bytes(receipt)
    market, engine_b, engine_c = (
        receipt["premium_engine_a"], receipt["engine_b"], receipt["engine_c"])
    security = market["security_return_pct"]
    benchmark = market["benchmark_return_pct"]
    gap = None
    if security is not None and benchmark is not None:
        try:
            gap = str((Decimal(security) - Decimal(benchmark)).quantize(
                Decimal("0.0001")))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("EXPLANATION_MARKET_NUMERIC_INVALID") from exc

    a_status = market["status"]
    b_status = engine_b["status"]
    c_status = engine_c["status"]
    result = {
        "schema": _SCHEMA,
        "status": "DETERMINISTIC_LOCAL_INTERPRETATION_UNVERIFIED",
        "issuer": dict(receipt["issuer"]),
        "linked_evidence_sha256": receipt["evidence_sha256"],
        "source_hashes": {
            "local_report_sha256": receipt["local_report_sha256"],
            "companyfacts_sha256": engine_b["companyfacts_sha256"],
            "stock_response_sha256": market["stock_response_sha256"],
            "index_response_sha256": market["index_response_sha256"],
            "industry_input_sha256": engine_c["input_sha256"],
        },
        "findings": [
            {
                "engine": "A",
                "status": a_status,
                "basis": "PRICE_ONLY_CLOSE_VS_ACTUAL_NASDAQ_100",
                "period_start": market["matched_period_start"],
                "period_end": market["matched_period_end"],
                "matched_sessions": market["matched_observation_count"],
                "security_return_pct": security,
                "benchmark_return_pct": benchmark,
                "simple_return_gap_pp": gap,
                "interpretation": (
                    "두 가격 수익률의 단순 관측 차이입니다. "
                    "초과수익 알파, 주가 거품, 인과관계 또는 매매 신호가 아닙니다."
                    if gap is not None else
                    "가격 분산 또는 수익률 정보가 불충분합니다. "
                    "베타나 시장 대비 판단을 확정할 수 없습니다."
                ),
            },
            {
                "engine": "B",
                "status": b_status,
                "interpretation": (
                    "10-K 회계·현금흐름 로컬 검토 결과가 존재하지만 "
                    "공시 원본의 진위가 미인증이며 회계부정을 입증하지 않습니다."
                    if b_status == "REVIEWED_UNVERIFIED" else
                    "검증 가능한 회계·현금흐름 지표가 부족해 판단을 보류합니다."
                ),
            },
            {
                "engine": "C",
                "status": c_status,
                "interpretation": (
                    "동종기업 비교는 로컬 입력에 따른 관측치일 뿐 "
                    "산업 전체의 대표 표본이나 미래 전망이 아닙니다."
                    if c_status == "OBSERVED_COMPARISON_UNVERIFIED" else
                    "유효한 업종·동종기업 비교 근거가 부족해 판단을 보류합니다."
                ),
            },
        ],
        "guard_policy_preview": "HOLD",
        "guard_executed": False,
        "source_authenticated": False,
        "source_rights_verified": False,
        "ai_agent_executed": False,
        "investment_recommendation": False,
        "trade_executed": False,
        "external_sharing_allowed": False,
        "notice": (
            "로컬 수학적 재검산만 확인됨. 출처 진위·재배포 권한·시장 시점은 "
            "별도 인증되지 않았으며 사람의 검토가 필요합니다."
        ),
    }
    result["explanation_sha256"] = sha256(_canonical(result)).hexdigest()
    if len(_canonical(result)) > 8192:
        raise ValueError("EXPLANATION_TOO_LARGE")
    return result


def explanation_json_bytes(result: Any) -> bytes:
    """Serialize only the exact deterministic explanation contract."""
    if type(result) is not dict or result.get("schema") != _SCHEMA:
        raise ValueError("EXPLANATION_EXPORT_INVALID")
    # No unrecognized field can be smuggled into a locally downloaded file,
    # even if the caller recalculates the (non-authenticating) SHA256.
    expected = {
        "schema", "status", "issuer", "linked_evidence_sha256",
        "source_hashes", "findings", "guard_policy_preview", "guard_executed",
        "source_authenticated", "source_rights_verified",
        "ai_agent_executed", "investment_recommendation", "trade_executed",
        "external_sharing_allowed", "notice", "explanation_sha256",
    }
    if (set(result) != expected
            or result.get("status") != "DETERMINISTIC_LOCAL_INTERPRETATION_UNVERIFIED"
            or result.get("guard_policy_preview") != "HOLD"
            or any(result.get(k) is not False for k in (
                "guard_executed", "source_authenticated",
                "source_rights_verified", "ai_agent_executed",
                "investment_recommendation", "trade_executed",
                "external_sharing_allowed"))
            or type(result.get("issuer")) is not dict
            or set(result["issuer"]) != {
                "ticker", "cik", "accession", "as_of", "filing_date"
            }
            or type(result.get("source_hashes")) is not dict
            or set(result["source_hashes"]) != {
                "local_report_sha256", "companyfacts_sha256",
                "stock_response_sha256", "index_response_sha256",
                "industry_input_sha256"
            }
            or type(result.get("findings")) is not list
            or len(result["findings"]) != 3
            or [f.get("engine") for f in result["findings"]
                if type(f) is dict] != ["A", "B", "C"]):
        raise ValueError("EXPLANATION_EXPORT_CONTRACT_INVALID")
    import re
    hex64 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
    hashes = [result.get("linked_evidence_sha256")] + [
        value for value in result["source_hashes"].values()
        if value is not None
    ]
    if (any(type(v) is not str or hex64.fullmatch(v) is None
            for v in hashes)
            or any(type(f) is not dict for f in result["findings"])
            or set(result["findings"][0]) != {
                "engine", "status", "basis", "period_start", "period_end",
                "matched_sessions", "security_return_pct",
                "benchmark_return_pct", "simple_return_gap_pp",
                "interpretation"
            }
            or any(set(result["findings"][i]) != {
                "engine", "status", "interpretation"} for i in (1, 2))
            or any(type(f["interpretation"]) is not str
                   or len(f["interpretation"]) > 240
                   for f in result["findings"])):
        raise ValueError("EXPLANATION_EXPORT_CONTRACT_INVALID")
    digest = result.get("explanation_sha256")
    if type(digest) is not str or hex64.fullmatch(digest) is None:
        raise ValueError("EXPLANATION_EXPORT_INVALID")
    unsigned = {k: v for k, v in result.items() if k != "explanation_sha256"}
    # Strictly reconstruct from provided evidence is the caller's job; this
    # checksum alone cannot authenticate a publisher or original sources.
    from hmac import compare_digest
    if not compare_digest(digest, sha256(_canonical(unsigned)).hexdigest()):
        raise ValueError("EXPLANATION_EXPORT_CHECKSUM_INVALID")
    raw = _canonical(result)
    if len(raw) > 8192:
        raise ValueError("EXPLANATION_TOO_LARGE")
    return raw
