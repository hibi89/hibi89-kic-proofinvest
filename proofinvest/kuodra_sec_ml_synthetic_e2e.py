"""Actual local SEC Guard + restricted ML bridge replay using fictional inputs only.

This connects two *existing* engines in one offline execution, not a live SEC
provider, institutional IAM, issuer alignment, approved data license or product
release. The SEC evidence archive exists only in a temporary test directory.
Do not invoke this demo with non-fictional data or use its results as a trade.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from .kic_dl_demo import (AS_OF, COLLECTED_AT, SYNTHETIC_ACCESSION,
                          SYNTHETIC_CIK, synthetic_companyfacts, synthetic_submissions)
from .kic_dl_original_demo import PHRASE, SYNTHETIC_HTML
from .kuodra_private_gateway import OwnerLocalGateway, VerifiedPrincipal
from .kuodra_review_report import build_owner_group_review
from .kuodra_sec_ml_review_bridge import (build_local_sec_ml_review,
                                          render_local_sec_ml_review_html)
from .kuodra_synthetic_demo import _csv, _table_rows
from .local_sec_guard_report import review_local_sec_with_guard


def run_synthetic_sec_ml_e2e() -> dict[str, Any]:
    """Exercise the real SEC->Guard->SQLite and ML->receipt->bridge call chain.

    Validates that both a conventional local HOLD and a conflicting claimed
    financial growth REJECT remain fail-closed after downstream ML co-review.
    Source digests bind *local fictional bytes*, not external SEC identity.
    """
    owner = VerifiedPrincipal('fictionalOwner', 'fictionalFund', ('owner',), True)
    reviewer = VerifiedPrincipal('fictionalAnalyst', 'fictionalFund', ('analyst',), True)
    vault = OwnerLocalGateway('fictionalFund')
    feature = [(issuer, 'feature', observed, available, value, unit)
               for issuer, _, observed, available, value, unit
               in _table_rows(metric='factor')]
    outcome = [(issuer, 'target', observed, available, value, unit)
               for issuer, _, observed, available, value, unit
               in _table_rows(metric='outcome')]
    vault.ingest_csv(owner, raw=_csv(feature + outcome),
                     dataset_id='fictionalLocalML', source_id='fictionalMLSource',
                     access_level='PRIVATE')
    ml = build_owner_group_review(
        vault, reviewer, private_dataset_id='fictionalLocalML',
        target_metric='target', feature_metrics=('feature',),
        as_of='2026-01-01T00:00:00Z')
    if (ml.get('scope') != 'PRIVATE' or ml.get('decision') != 'HOLD'
            or ml.get('public_export_allowed') is not False):
        raise RuntimeError('SYNTHETIC_ML_REVIEW_NOT_RESTRICTED')

    submissions = synthetic_submissions()
    facts = json.dumps(synthetic_companyfacts(), sort_keys=True).encode('utf-8')
    original = SYNTHETIC_HTML
    pins = {
        'submissions': sha256(submissions).hexdigest(),
        'companyfacts': sha256(facts).hexdigest(),
        'original_filing': sha256(original).hexdigest(),
    }
    cases = []
    for label, claim, decision in (
            ('UNVERIFIED_FINANCIAL_CLAIM', '100.00', 'HOLD'),
            ('CONFLICTING_FINANCIAL_CLAIM', '300.00', 'REJECT')):
        with TemporaryDirectory(prefix='kuodra-fictitious-sec-') as directory:
            sec = review_local_sec_with_guard(
                submissions_json=submissions, companyfacts_json=facts,
                original_filing=original, cik=SYNTHETIC_CIK,
                accession=SYNTHETIC_ACCESSION, as_of=AS_OF,
                collected_at=COLLECTED_AT, current_end='2025-09-30',
                prior_end='2024-09-30', needle=PHRASE,
                audit_db_path=Path(directory) / 'audit.sqlite',
                run_id='offline-one', claimed_growth_pct=claim,
                expected_source_sha256=pins)
            if (sec['operator_reviewed_source_digests_matched'] is not True
                    or sec['audit_chain_valid'] is not True):
                raise RuntimeError('SYNTHETIC_SEC_LOCAL_AUDIT_OR_PINS_INVALID')
            joined = build_local_sec_ml_review(sec, ml)
            html = render_local_sec_ml_review_html(joined)
            if (joined['decision'] != decision or joined['public_export_allowed'] is not False
                    or joined['trade_authorized'] is not False
                    or joined['cross_source_entity_link']
                       != 'NOT_ESTABLISHED_DO_NOT_JOIN_OR_COMPARE_ISSUERS'
                    or 'default-src' not in html
                    or 'fictionalLocalML' in html):
                raise RuntimeError('SYNTHETIC_SEC_ML_GUARD_CONTRACT_INVALID')
            cases.append({
                'case': label, 'sec_numeric_status': joined['sec']['numeric_status'],
                'decision': joined['decision'],
                'local_source_pins_matched': True,
                'local_sqlite_audit_valid': True,
                'ml_status': joined['ml']['summary']['status'],
                'bridge_receipt_sha256': joined['receipt_sha256'],
            })
    return {
        'schema': 'kuodra.synthetic-sec-ml-e2e.v1',
        'synthetic_only': True, 'real_institution_data_used': False,
        'sec_publisher_authenticated': False, 'real_data_rights_verified': False,
        'institution_host_iam_verified': False, 'os_egress_policy_verified': False,
        'independent_issuer_link_verified': False,
        'live_sec_requests': 0, 'external_llm_requests': 0,
        'public_export_allowed': False, 'trade_authorized': False,
        'production_ready': False, 'cases': cases,
    }


def main() -> int:
    print(json.dumps(run_synthetic_sec_ml_e2e(), sort_keys=True, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
