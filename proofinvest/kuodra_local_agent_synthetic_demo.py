"""No-provider-cost fictional user-question -> local tool -> SEC/ML review CLI.

Every principal, SEC original and financial observation is synthetic.
This demonstrates bounded routing and receipts only; no real licensed
publisher, institution IAM, production deployment or financial efficacy.
Run: python -B -m proofinvest.kuodra_local_agent_synthetic_demo
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from .guard_audit import GuardAuditStore
from .kic_dl_demo import (
    AS_OF, COLLECTED_AT, SYNTHETIC_CIK, SYNTHETIC_ACCESSION,
    synthetic_companyfacts, synthetic_submissions,
)
from .kic_dl_original_demo import PHRASE, SYNTHETIC_HTML
from .kuodra_private_gateway import OwnerLocalGateway, VerifiedPrincipal
from .kuodra_synthetic_demo import _csv, _table_rows
from .kuodra_local_agent_workflow import (
    run_owner_local_question, render_local_question_html,
)


def run_fictional_question_agent_demo() -> dict:
    owner = VerifiedPrincipal("fictionalOwner", "fictionalFund", ("owner",), True)
    analyst = VerifiedPrincipal("fictionalAnalyst", "fictionalFund", ("analyst",), True)
    vault = OwnerLocalGateway("fictionalFund")
    factor = [(entity, "feature", observed, ready, value, unit)
              for entity, _, observed, ready, value, unit
              in _table_rows(metric="factor")]
    target = [(entity, "target", observed, ready, value, unit)
              for entity, _, observed, ready, value, unit
              in _table_rows(metric="outcome")]
    vault.ingest_csv(
        owner, raw=_csv(factor + target), dataset_id="fictionalLocalML",
        source_id="fictionalPrivateSource", access_level="PRIVATE")
    submissions = synthetic_submissions()
    facts = json.dumps(synthetic_companyfacts(), sort_keys=True).encode("utf-8")
    raw = dict(submissions_json=submissions, companyfacts_json=facts,
               original_filing=SYNTHETIC_HTML)
    pins = {"submissions": sha256(submissions).hexdigest(),
            "companyfacts": sha256(facts).hexdigest(),
            "original_filing": sha256(SYNTHETIC_HTML).hexdigest()}

    cases = []
    for claim, expected in (("100.00", "HOLD"), ("300.00", "REJECT")):
        with TemporaryDirectory(prefix="kuodra-fictional-question-") as tmp:
            audit_db = Path(tmp) / "evidence.sqlite"
            result = run_owner_local_question(
                "SEC 공시 원문과 다변수 ML을 함께 검토해줘",
                vault=vault, principal=analyst,
                private_dataset_id="fictionalLocalML",
                target_metric="target", feature_metrics=("feature",),
                ml_as_of="2026-01-01T00:00:00Z",
                sec_bytes=raw,
                sec_options={
                    "cik": SYNTHETIC_CIK, "accession": SYNTHETIC_ACCESSION,
                    "as_of": AS_OF, "collected_at": COLLECTED_AT,
                    "current_end": "2025-09-30", "prior_end": "2024-09-30",
                    "needle": PHRASE, "audit_db_path": audit_db,
                    "run_id": "fictionalReview", "claimed_growth_pct": claim,
                    "expected_source_sha256": pins,
                },
                consent_local_sec_audit=True)
            html = render_local_question_html(result)
            if (result["status"] != "LOCAL_HUMAN_REVIEW_REQUIRED"
                    or result["decision"] != expected
                    or result["tool_calls"] != 2
                    or not audit_db.exists()
                    or not GuardAuditStore(audit_db).verify_chain()
                    or "default-src 'none'" not in html
                    or result["public_export_allowed"] is not False
                    or result["production_ready"] is not False
                    or result["cross_source_entity_link"] !=
                       "NOT_ESTABLISHED_DO_NOT_JOIN_OR_COMPARE_ISSUERS"):
                raise RuntimeError("FICTIONAL_AGENT_REVIEW_ACCEPTANCE_FAILED")
            if any(word in html for word in
                   ("fictionalLocalML", "fictionalOwner", "fictitiousIssuer0")):
                raise RuntimeError("FICTIONAL_AGENT_PRIVATE_IDENTIFIER_LEAK")
            cases.append({
                "scenario": "FICTIONAL_DISPUTED_REVENUE"
                            if expected == "REJECT" else "FICTIONAL_UNVERIFIED_REVENUE",
                "decision": expected, "tools": result["selected_tools"],
                "audit_valid": True, "source_pins_checked": True,
                "receipt_sha256": result["receipt_sha256"],
            })
    return {
        "schema": "kuodra.fictional-question-agent-demo.v1",
        "synthetic_only": True, "cases": cases,
        "status": "PASS_OFFLINE_LOCAL_TOOL_WORKFLOW",
        "institution_data_used": False, "finance_accuracy_proven": False,
        "issuer_link_verified": False, "source_rights_verified": False,
        "publisher_origin_verified": False, "host_iam_verified": False,
        "host_no_egress_verified": False, "production_ready": False,
        "external_network_requests": 0, "external_llm_requests": 0,
        "public_export_allowed": False, "trade_authorized": False,
    }


def main() -> int:
    print(json.dumps(run_fictional_question_agent_demo(),
                     ensure_ascii=True, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
