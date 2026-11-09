"""Private-local human review packet for group/time evaluated KUODRA insights.

No raw records/filenames or issuer IDs are rendered. Caller must use approved
local worker, host IAM and OS deny-egress before handling actual private data.
Returns pure JSON-compatible metadata and optional inert offline HTML string.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from html import escape
import json
from typing import Any

from .kuodra_private_gateway import OwnerLocalGateway, VerifiedPrincipal
from .kuodra_group_time_ml import evaluate_owner_local_group, evaluate_owner_local_hybrid_group


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=True, sort_keys=True,
            separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _evidence(dataset: dict) -> dict:
    return {"raw_source_sha256": dataset["source_sha256"],
            "row_count": dataset["rows"],
            "access_level": dataset["access_level"],
            "publisher_authenticated": False, "source_rights_verified": False}


def build_owner_group_review(vault: OwnerLocalGateway, principal: VerifiedPrincipal,
                             *, private_dataset_id: str, target_metric: str,
                             feature_metrics: tuple[str, ...], as_of: str,
                             public_dataset_id: str | None = None) -> dict:
    """One authorized analysis pass and immutable evidence-linked local receipt.

    Reporting operation does not mutate gateway state, publish to external
    services, perform raw exports or certify publisher identity/model accuracy.
    """
    if type(vault) is not OwnerLocalGateway or type(principal) is not VerifiedPrincipal:
        raise PermissionError("REVIEW_ACCESS_DENIED")
    if public_dataset_id is None:
        vault._check(principal, dataset_id=private_dataset_id)
        private = deepcopy(vault._datasets[private_dataset_id])
        if private["access_level"] != "PRIVATE":
            raise PermissionError("REVIEW_PRIVATE_SCOPE_REQUIRED")
        answer = evaluate_owner_local_group(vault, principal,
            dataset_id=private_dataset_id, target_metric=target_metric,
            feature_metrics=feature_metrics, as_of=as_of)
        items = [_evidence(private)]
        mode = "PRIVATE"
    else:
        # Re-check both IDs before any data read or analysis (generic denial).
        vault._check(principal, dataset_id=private_dataset_id)
        vault._check(principal, dataset_id=public_dataset_id)
        private = deepcopy(vault._datasets[private_dataset_id])
        public = deepcopy(vault._datasets[public_dataset_id])
        if private["access_level"] != "PRIVATE" or public["access_level"] != "PUBLIC":
            raise PermissionError("REVIEW_ZONE_MISMATCH")
        answer = evaluate_owner_local_hybrid_group(vault, principal,
            public_dataset_id=public_dataset_id, private_dataset_id=private_dataset_id,
            target_metric=target_metric, feature_metrics=feature_metrics, as_of=as_of)
        items = [_evidence(public), _evidence(private)]
        mode = "LOCAL_HYBRID"
    result = answer["analysis"] if mode == "LOCAL_HYBRID" else answer
    if result.get("guard") != "HOLD" or result.get("production_ready") is not False:
        raise ValueError("REVIEW_UNGUARDED_MODEL_OUTPUT")
    # No arbitrary user-controlled model text; shallow, stable allowlist only.
    wanted = ("schema", "status", "reason", "split", "cv_policy", "cv_folds",
              "issuer_count", "train_issuer_count", "holdout_issuer_count",
              "train_n", "holdout_n", "cv_mae", "selected_by_cv",
              "holdout_mae", "holdout_dummy_mae", "holdout_improvement_pct",
              "holdout_beats_dummy", "holdout_stability",
              "statistical_significance", "target_horizon")
    summary = {key: result[key] for key in wanted if key in result}
    packet = {
        "schema": "kuodra.local-restricted-review.v1",
        "status": "HUMAN_REVIEW_REQUIRED", "scope": mode, "as_of": as_of,
        "evidence": items, "analysis": summary,
        "decision": "HOLD", "allowed_purpose": "OWNER_LOCAL_RESEARCH_REVIEW",
        "public_export_allowed": False, "external_llm_allowed": False,
        "origin_verified": False, "calibrated_probability": None,
        "causal_claim": False, "finance_validity_verified": False,
        "host_egress_verified": False, "network_requests": 0,
        "data_rows_disclosed": False,
        "review_requirements": [
            "Confirm institution host authentication and access policy",
            "Confirm source origin and license or right to analyze",
            "Review temporal and issuer sampling independence",
            "Do not make a financial trade decision from this packet alone",
        ],
    }
    packet["receipt_sha256"] = sha256(_canonical(packet)).hexdigest()
    return packet


def render_restricted_review_html(packet: dict) -> str:
    """Inert HTML representation; never publish this PRIVATE evidence."""
    if (type(packet) is not dict or packet.get("schema") != "kuodra.local-restricted-review.v1"
            or packet.get("status") != "HUMAN_REVIEW_REQUIRED"
            or packet.get("decision") != "HOLD"
            or packet.get("public_export_allowed") is not False
            or packet.get("external_llm_allowed") is not False):
        raise ValueError("REVIEW_REPORT_CONTRACT_INVALID")
    copied = dict(packet)
    digest = copied.pop("receipt_sha256", None)
    if type(digest) is not str or len(digest) != 64 or sha256(_canonical(copied)).hexdigest() != digest:
        raise ValueError("REVIEW_REPORT_HASH_MISMATCH")
    # Render only selected safe keys: no dataset identifiers, raw rows or user text.
    view = {key: packet[key] for key in ("status", "scope", "as_of", "analysis",
        "evidence", "decision", "review_requirements", "receipt_sha256")}
    text = escape(json.dumps(view, ensure_ascii=True, sort_keys=True, indent=2,
                             allow_nan=False))
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta http-equiv='Content-Security-Policy' "
            "content=\"default-src 'none'; style-src 'unsafe-inline'\">"
            "<title>KUODRA local review — HOLD</title>"
            "<style>body{max-width:900px;margin:2rem auto;background:#111;color:#eee;"
            "font:14px/1.5 system-ui;padding:1rem}pre{white-space:pre-wrap;"
            "overflow-wrap:anywhere}h1{font-size:1.5rem}</style></head>"
            "<body><h1>KUODRA — Local human review: HOLD</h1><pre>"
            + text + "</pre></body></html>")
