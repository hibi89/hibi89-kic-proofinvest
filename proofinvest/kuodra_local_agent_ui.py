"""Streamlit operator-facing, SYNTHETIC-ONLY KUODRA SEC+ML workflow.

Only fixed fictional fixtures are fed to the existing bounded tool runner.
No uploads, paths, external API, KIC records, host-auth impersonation claims,
public production integration or persistent audit DB. All review reports are
human-HOLD/REJECT, with explicit source/rights/issuer-link limitations.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from .guard_audit import GuardAuditStore
from .kic_dl_demo import (
    AS_OF, COLLECTED_AT, SYNTHETIC_ACCESSION, SYNTHETIC_CIK,
    synthetic_companyfacts, synthetic_submissions,
)
from .kic_dl_original_demo import PHRASE, SYNTHETIC_HTML
from .kuodra_local_agent_workflow import (
    plan_local_question, run_owner_local_question, render_local_question_html,
)
from .kuodra_private_gateway import OwnerLocalGateway, VerifiedPrincipal
from .kuodra_identity_approval import approve_local_identity_mapping
from .kuodra_review_report import _canonical
from .kuodra_synthetic_demo import _csv, _table_rows

_CHOICES = {
    "가상 공시 + 공개/비공개 ML": "SEC_ML",
    "가상 공시만": "SEC_ONLY",
    "공개/비공개 ML만": "ML_ONLY",
}
_EXAMPLES = {
    "SEC_ML": "SEC 공시와 다변수 ML을 함께 검토해줘",
    "SEC_ONLY": "SEC 공시 원문 수치를 검토해줘",
    "ML_ONLY": "공개/비공개 다변수 ML 결과를 검토해줘",
}
_CASES = {"일치 주장 (HOLD)": "100.00", "충돌 주장 (REJECT)": "300.00"}


def _fictional_vault() -> tuple[OwnerLocalGateway, VerifiedPrincipal, VerifiedPrincipal]:
    """Build a fresh in-memory fictional owner-scoped PUBLIC/PRIVATE pair."""
    owner = VerifiedPrincipal("syntheticOwner", "syntheticInstitution", ("owner",), True)
    analyst = VerifiedPrincipal("syntheticAnalyst", "syntheticInstitution",
                                ("analyst",), True)
    vault = OwnerLocalGateway("syntheticInstitution")
    public = _csv(_table_rows(metric="factor"))
    private = _csv(_table_rows(metric="outcome"))
    vault.ingest_csv(owner, raw=public, dataset_id="fakePublic",
                     source_id="syntheticSourceA", access_level="PUBLIC")
    vault.ingest_csv(owner, raw=private, dataset_id="fakePrivate",
                     source_id="syntheticSourceB", access_level="PRIVATE")
    return vault, owner, analyst


def run_fictional_agent_ui_case(
    *, question: str, mode: str, claim: str,
    consent_ephemeral_audit: bool,
    consent_fictional_identity_mapping: bool = False,
) -> dict[str, Any]:
    """Actual local engine invocation with a discarded, ephemeral audit.

    No input bytes, user files or real host principal can be supplied here.
    A selected data mode MUST exactly match the deterministic question plan.
    Returning only a restricted JSON packet allows safe page rerenders.
    """
    if (mode not in _EXAMPLES or claim not in _CASES.values()
            or type(consent_ephemeral_audit) is not bool
            or type(consent_fictional_identity_mapping) is not bool):
        raise ValueError("SYNTHETIC_UI_SELECTION_INVALID")
    plan = plan_local_question(question)
    if plan["status"] != "READY" or plan["mode"] != mode:
        raise ValueError("QUESTION_AND_SELECTED_SOURCES_MUST_MATCH")
    if mode != "ML_ONLY" and not consent_ephemeral_audit:
        raise ValueError("EXPLICIT_EPHEMERAL_SQLITE_CONSENT_REQUIRED")
    if mode in ("ML_ONLY", "SEC_ML") and not consent_fictional_identity_mapping:
        raise ValueError("FICTIONAL_IDENTITY_MAPPING_EXPLICIT_ACK_REQUIRED")
    with TemporaryDirectory(prefix="kuodra-fictional-agent-screen-") as tmp:
        vault, owner, principal = _fictional_vault()
        arguments = {"vault": vault, "principal": principal}
        if mode in ("ML_ONLY", "SEC_ML"):
            pub = vault._datasets["fakePublic"]
            priv = vault._datasets["fakePrivate"]
            aliases = {r["entity_id"]: r["entity_id"] for r in pub["records"]}
            approval = approve_local_identity_mapping(
                vault, owner,
                public_dataset_id="fakePublic", private_dataset_id="fakePrivate",
                public_sha256=pub["source_sha256"],
                private_sha256=priv["source_sha256"],
                aliases=aliases, as_of="2026-01-01T00:00:00Z",
                delegate_subject=principal.subject,
                acknowledge_unverified_issuer_identity=True)
            arguments["identity_approval_token"] = approval["one_use_token"]
            arguments.update(
                private_dataset_id="fakePrivate", public_dataset_id="fakePublic",
                target_metric="private.outcome", feature_metrics=("public.factor",),
                ml_as_of="2026-01-01T00:00:00Z",
            )
        if mode in ("SEC_ONLY", "SEC_ML"):
            subs = synthetic_submissions()
            facts = json.dumps(synthetic_companyfacts(), sort_keys=True).encode("utf-8")
            raw = {"submissions_json": subs, "companyfacts_json": facts,
                   "original_filing": SYNTHETIC_HTML}
            audit_db = Path(tmp) / "audit.sqlite"
            arguments.update(
                sec_bytes=raw,
                sec_options={
                    "cik": SYNTHETIC_CIK, "accession": SYNTHETIC_ACCESSION,
                    "as_of": AS_OF, "collected_at": COLLECTED_AT,
                    "current_end": "2025-09-30", "prior_end": "2024-09-30",
                    "needle": PHRASE, "audit_db_path": audit_db,
                    "run_id": "fictionalAgentScreen", "claimed_growth_pct": claim,
                    "expected_source_sha256": {
                        "submissions": sha256(subs).hexdigest(),
                        "companyfacts": sha256(facts).hexdigest(),
                        "original_filing": sha256(SYNTHETIC_HTML).hexdigest(),
                    },
                },
                consent_local_sec_audit=True,
            )
        result = run_owner_local_question(question, **arguments)
        if (result.get("status") != "LOCAL_HUMAN_REVIEW_REQUIRED"
                or result.get("mode") != mode
                or result.get("decision") not in ("HOLD", "REJECT")
                or result.get("public_export_allowed") is not False
                or result.get("trade_authorized") is not False
                or result.get("production_ready") is not False
                or result.get("network_requests") != 0):
            raise ValueError("SYNTHETIC_UI_GUARDED_RESULT_UNAVAILABLE")
        audited = mode != "ML_ONLY"
        if audited and (not audit_db.is_file()
                        or not GuardAuditStore(audit_db).verify_chain()
                        or result.get("audit_written") is not True):
            raise ValueError("SYNTHETIC_UI_EPHEMERAL_AUDIT_INVALID")
        if not audited and result.get("audit_written") is not False:
            raise ValueError("SYNTHETIC_UI_UNSELECTED_AUDIT_INVALID")
        if mode == "SEC_ML" and result.get("cross_source_entity_link") != (
                "NOT_ESTABLISHED_DO_NOT_JOIN_OR_COMPARE_ISSUERS"):
            raise ValueError("SYNTHETIC_UI_ISSUER_LINK_POLICY_INVALID")
        mapping = result.get("local_public_private_identity_review")
        if mode in ("ML_ONLY", "SEC_ML"):
            if (type(mapping) is not dict
                    or mapping.get("single_use_consumed") is not True
                    or mapping.get("cross_source_identity_verified") is not False
                    or vault._local_identity_approvals):
                raise ValueError("SYNTHETIC_IDENTITY_MAPPING_NOT_CONSUMED")
        elif mapping is not None:
            raise ValueError("UNSELECTED_IDENTITY_MAPPING_RESULT")
        html = render_local_question_html(result)
        if "<script" in html.lower() or "default-src 'none'" not in html:
            raise ValueError("SYNTHETIC_UI_HTML_INERTNESS_INVALID")
        receipt = {
            "schema": "kuodra.fictional-agent-ui-receipt.v1",
            "synthetic_only": True, "mode": mode,
            "selected_tools": result["selected_tools"],
            "question_sha256": result["question_sha256"],
            "decision": result["decision"], "tool_calls": result["tool_calls"],
            "trace": result["trace"],
            "review": result["review"],
            "local_public_private_identity_review":
                result["local_public_private_identity_review"],
            "agent_receipt_sha256": result["receipt_sha256"],
            "audit_chain_verified_ephemeral": audited,
            "audit_retained": False,
            "human_review_required": True,
            "source_authenticated": False, "source_rights_verified": False,
            "cross_source_entity_link_verified": False,
            "host_iam_verified": False, "host_no_egress_verified": False,
            "finance_model_accuracy_proven": False,
            "external_model_called": False, "network_requests": 0,
            "public_export_allowed": False, "trade_authorized": False,
            "production_ready": False,
        }
        receipt["receipt_sha256"] = sha256(_canonical(receipt)).hexdigest()
        # Must not return leaked mocked owner, dataset names or row values.
        serialized = json.dumps(receipt, ensure_ascii=True, sort_keys=True, allow_nan=False)
        if len(serialized.encode("utf-8")) > 32_768 or any(token in serialized for token in (
                "fakePrivate", "fakePublic", "syntheticInstitution",
                "syntheticOwner", "fictitiousIssuer")):
            raise ValueError("SYNTHETIC_UI_REDACTION_OR_SIZE_INVALID")
        return receipt


def render_fictional_agent_ui(st) -> None:
    """Render a fictional-only control panel; execution requires a real click."""
    def reset_audit_consent() -> None:
        # Consent is tied to one exact source/question/claim selection.
        st.session_state["kuodra_agent_audit_consent"] = False
        st.session_state["kuodra_agent_identity_consent"] = False

    def source_changed() -> None:
        reset_audit_consent()
        st.session_state["kuodra_agent_question"] = _EXAMPLES[
            _CHOICES[st.session_state["kuodra_agent_sources"]]]

    st.title("KUODRA — 질문 기반 SEC / ML / Guard Agent")
    st.warning(
        "SYNTHETIC ONLY · 실제 투자자료, 인증된 SEC 원본, 기관 비공개 파일을 "
        "이 화면으로 입력하지 마십시오. 출처 이용권·기관 IAM·차단된 외부 통신 "
        "및 재무 예측력은 확인되지 않았습니다."
    )
    st.caption("한 번의 클릭에 선택된 로컬 도구 최대 2개 실행 · "
               "HOLD/REJECT만 출력 · 감사 SQLite는 임시 생성 후 삭제")
    selection = st.selectbox("가상 자료 선택", list(_CHOICES),
                             key="kuodra_agent_sources",
                             on_change=source_changed)
    mode = _CHOICES[selection]
    question = st.text_area("분석 요청 (SEC/공시, ML/다변수 중 명시)",
                            value=_EXAMPLES[mode], key="kuodra_agent_question",
                            max_chars=200, on_change=reset_audit_consent)
    claim_label = st.selectbox("가상 매출 주장", list(_CASES),
                               key="kuodra_agent_claim",
                               disabled=mode == "ML_ONLY",
                               on_change=reset_audit_consent)
    consent = st.checkbox(
        "임시 SQLite 감사 생성·검증·즉시 삭제에 동의 (SEC 선택 시 필수)",
        value=False, key="kuodra_agent_audit_consent",
        disabled=mode == "ML_ONLY",
    )
    identity_consent = st.checkbox(
        "가상 공개·비공개 기업 연결은 출처 인증이 아님을 확인하고 승인",
        value=False, key="kuodra_agent_identity_consent",
        disabled=mode == "SEC_ONLY")
    plan = plan_local_question(question)
    if plan["status"] == "READY" and plan["mode"] == mode:
        st.json({"selected_tools": list(plan["selected_tools"]),
                 "tool_budget": plan["tool_budget"],
                 "source_mode": mode, "ready_to_execute": True,
                 "real_source_authenticated": False})
    else:
        st.warning("질문의 SEC/ML 요청과 선택한 자료가 일치해야 합니다. "
                   "지원하지 않는 실행·주문 요청은 차단됩니다.")
    allowed = (plan["status"] == "READY" and plan["mode"] == mode
               and (mode == "ML_ONLY" or consent is True)
               and (mode == "SEC_ONLY" or identity_consent is True))
    if not st.button("선택한 Agent 검토 실행", key="kuodra_agent_execute",
                     disabled=not allowed):
        return
    try:
        receipt = run_fictional_agent_ui_case(
            question=question, mode=mode, claim=_CASES[claim_label],
            consent_ephemeral_audit=consent if mode != "ML_ONLY" else False,
            consent_fictional_identity_mapping=(
                identity_consent if mode != "SEC_ONLY" else False))
    except RuntimeError:
        st.error("감사 결과 불명: 실행을 재시도하지 말고 로컬 상태를 확인하십시오.")
        return
    except (ValueError, TypeError, KeyError, OSError, OverflowError):
        st.error("검토 실행 차단: 자료·기간·권한 또는 감사 계약 위반")
        return
    st.subheader("근거 연결 · 사람 검토 필요")
    st.metric("Guard", receipt["decision"])
    st.caption("이 판정은 가상 원본 기반입니다. 실기업/투자 승인·예측 검증이 아닙니다.")
    st.json(receipt)
    st.download_button(
        "검증된 가상 보고서 JSON",
        data=_canonical(receipt),
        file_name="kuodra-fictional-agent-review.json",
        mime="application/json",
        key="kuodra_agent_download",
    )
