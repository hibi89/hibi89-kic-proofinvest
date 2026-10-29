"""Source-origin and licensing boundary: no self-reported local ZIP grants rights.

All byte fixtures are synthetic. Tests never call SEC, a broker or DAKER.
"""
from __future__ import annotations

import copy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from proofinvest.archived_sec_guard_report import (
    render_archived_sec_guard_markdown, run_archived_sec_guard_report,
)
from proofinvest.archived_sec_guard_ui import _safe_archived_report
from proofinvest.kic_dl_original_demo import PHRASE
from proofinvest.sec_bundle_replay import replay_local_capture
from proofinvest.sec_capture_bundle import save_local_capture_bundle
from proofinvest.source_assurance import (
    evaluate_local_source_assurance, expected_offline_source_assurance,
    validate_local_source_assurance,
)
from tests.test_sec_bundle_replay import fixture


class KICLocalSourceAssuranceTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory(prefix="kic-source-assurance-")
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.zip = self.base / "synthetic-unverified.zip"
        self.audit = self.base / "audit.sqlite"
        receipt, raws = fixture()
        save_local_capture_bundle(self.zip, receipt=receipt, **raws)

    def replay(self):
        return replay_local_capture(
            self.zip, current_end="2025-09-30", prior_end="2024-09-30",
            needle=PHRASE,
        )

    def report(self, **kwargs):
        opts = dict(
            bundle_path=self.zip, audit_db_path=self.audit,
            current_end="2025-09-30", prior_end="2024-09-30",
            needle=PHRASE, run_id="source-assurance-one",
        )
        opts.update(kwargs)
        return run_archived_sec_guard_report(**opts)

    def test_local_hash_match_never_grants_sec_authority_or_rights(self):
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("EXTERNAL_HTTP_NOT_ALLOWED")) as external:
            replay = self.replay()
            assurance = evaluate_local_source_assurance(replay)
            report = self.report()
        external.assert_not_called()
        self.assertEqual(assurance, expected_offline_source_assurance())
        self.assertEqual(report["source_assurance"], assurance)
        self.assertEqual(assurance["status"],
                         "LOCAL_BYTES_ONLY_EXTERNAL_ASSURANCE_BLOCKED")
        statuses = {entry["code"]: entry["status"]
                    for entry in assurance["checks"]}
        self.assertEqual(statuses["LOCAL_THREE_FILE_HASH"], "LOCAL_MATCH")
        self.assertEqual(statuses["ISSUER_AND_PROVIDER_ORIGIN"], "NOT_ATTESTED")
        self.assertEqual(statuses["CAPTURE_TIME_AND_ASOF"], "SELF_REPORTED_ONLY")
        self.assertEqual(statuses["USE_AND_REDISTRIBUTION_RIGHTS"],
                         "NOT_VERIFIED")
        allowed = assurance["software_scope_not_legal_permission"]
        self.assertTrue(allowed["local_human_review"])
        self.assertTrue(allowed["local_derived_hash_and_status_export"])
        for key in ("raw_filing_publication", "raw_filing_redistribution",
                    "unverified_facts_as_verified_public_claims",
                    "investment_model_authorization",
                    "investment_advice_or_execution",
                    "official_contest_submission"):
            self.assertFalse(allowed[key], key)
        self.assertFalse(report["source_authenticated"])
        self.assertFalse(report["source_rights_verified"])
        self.assertFalse(report["decision_brief"]["source_assurance"]
                         ["source_rights_verified"])
        self.assertTrue(_safe_archived_report(report))
        self.assertIn("원문 공개/재배포 금지",
                      render_archived_sec_guard_markdown(report))

    def test_conflicting_financial_claim_cannot_upgrade_rights(self):
        report = self.report(claimed_growth_pct="1.00")
        self.assertEqual(report["guard"]["decision"], "REJECT")
        self.assertFalse(report["source_assurance"]["source_rights_verified"])
        self.assertTrue(_safe_archived_report(report))

    def test_self_reported_claims_refused_before_any_sqlite_write(self):
        valid = self.replay()
        for field in ("source_authenticated", "financial_values_authenticated",
                      "source_rights_verified", "external_http_called",
                      "official_contest_submission"):
            with self.subTest(field=field):
                forged = copy.deepcopy(valid)
                forged[field] = True
                with self.assertRaises(ValueError):
                    evaluate_local_source_assurance(forged)
                with patch(
                    "proofinvest.archived_sec_guard_report.replay_local_capture",
                    return_value=forged,
                ), self.assertRaises(ValueError):
                    self.report()
                self.assertFalse(self.audit.exists())

    def test_unchecked_original_hash_and_missing_source_chain_refused(self):
        original = self.replay()
        for mutation in ("original_file_hash", "local_digest_flag", "no_span"):
            with self.subTest(mutation=mutation):
                forged = copy.deepcopy(original)
                if mutation == "original_file_hash":
                    forged["source_span"]["original_sha256"] = "f" * 64
                elif mutation == "local_digest_flag":
                    forged["local_integrity"]["local_bytes_and_manifest_match"] = False
                else:
                    forged.pop("source_span")
                with self.assertRaises(ValueError):
                    evaluate_local_source_assurance(forged)
                with patch(
                    "proofinvest.archived_sec_guard_report.replay_local_capture",
                    return_value=forged,
                ), self.assertRaises(ValueError):
                    self.report()
                self.assertFalse(self.audit.exists())

    def test_forged_redistribution_permission_cannot_render_or_export(self):
        report = self.report()
        for field, value in (
            ("source_rights_verified", True),
            ("provider_authenticated", True),
            ("checks", []),
            ("software_scope_not_legal_permission",
             {"raw_filing_redistribution": True}),
            ("manual_requirements", ["NO_REVIEW_NEEDED"]),
        ):
            with self.subTest(field=field):
                altered = copy.deepcopy(report)
                altered["source_assurance"][field] = value
                self.assertFalse(validate_local_source_assurance(
                    altered["source_assurance"]
                ))
                self.assertFalse(_safe_archived_report(altered))
                with self.assertRaises(ValueError):
                    render_archived_sec_guard_markdown(altered)
        self.assertTrue(validate_local_source_assurance(report["source_assurance"]))

    def test_independent_assurance_copy_cannot_mutate_contract(self):
        mutated = expected_offline_source_assurance()
        mutated["checks"][0]["status"] = "OFFICIALLY_CERTIFIED"
        self.assertFalse(validate_local_source_assurance(mutated))
        fresh = expected_offline_source_assurance()
        self.assertEqual(fresh["checks"][0]["status"], "LOCAL_MATCH")


if __name__ == "__main__":
    unittest.main()
