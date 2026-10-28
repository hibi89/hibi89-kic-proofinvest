"""Tests for DL's real stdlib SEC recent-index / SQLite / CLI path.

The bundled SEC-like fixture is SYNTHETIC. Network testing uses a stub.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from disclosure_lightning import core

FIXTURE = Path(__file__).resolve().parents[1] / "disclosure_lightning" / "fixtures" / "sec_submissions_synthetic.json"
CIK = "0000320193"
FORMS = core.parse_forms("10-K,10-K/A,10-Q,8-K")


@contextlib.contextmanager
def _sqlite_connection(path):
    connection = sqlite3.connect(path)
    try:
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


class DisclosureLightningTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="dl-kic-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.db = self.root / "dl.sqlite3"
        self.raw = FIXTURE.read_bytes()

    def indexed(self, raw=None, *, forms=FORMS, as_of="2026-10-27",
                collected_at=None):
        return core.index_submissions(
            self.raw if raw is None else raw, cik=CIK,
            as_of=as_of, forms=forms,
            collected_at=collected_at or "2026-10-27T00:00:00Z",
        )

    def test_offline_recent_index_has_correct_source_and_cutoff(self):
        indexed = self.indexed()
        self.assertEqual(indexed["indexed_count"], 3)
        self.assertEqual(indexed["provenance"], "OFFLINE_UNVERIFIED")
        self.assertEqual(indexed["source_sha256"], hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(indexed["issuer_cik"], CIK)
        self.assertEqual(indexed["filings"][0]["evidence_status"], "OFFLINE_SOURCE_UNVERIFIED")
        self.assertIsNone(indexed["filings"][0]["raw_sha256"])
        self.assertEqual(indexed["filings"][0]["form"], "10-K")
        self.assertIn("320193/000032019325000901/example-10k.htm",
                      indexed["filings"][0]["source_uri"])
        self.assertNotIn("0000320193-26-000903", [item["accession"] for item in indexed["filings"]])

    def test_amendment_stored_as_separate_immutable_filing(self):
        indexed = self.indexed()
        saved = core.save_index(self.db, self.raw, indexed)
        self.assertEqual((saved["status"], saved["new_filings"], saved["total_filings"]),
                         ("SAVED", 3, 3))
        exported = core.list_filings(self.db, cik=CIK)
        self.assertEqual(len(exported), 3)
        self.assertIn("10-K/A", [r["form"] for r in exported])
        self.assertIsNone(next(x for x in exported if x["form"] == "10-K/A")["amends_accession"])

    def test_idempotent_second_run_reuses_snapshot(self):
        data = self.indexed()
        first = core.save_index(self.db, self.raw, data)
        second = core.save_index(self.db, self.raw, data)
        self.assertEqual(first["observation_id"], second["observation_id"])
        self.assertEqual(second["status"], "REUSED")
        self.assertEqual(second["new_filings"], 0)
        with _sqlite_connection(self.db) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM observations").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT count(*) FROM filings").fetchone()[0], 3)
            self.assertEqual(db.execute("SELECT response FROM observations").fetchone()[0], self.raw)

    def test_simultaneous_replay_serializes_and_reuses_observation(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        indexed = self.indexed()
        start = Barrier(2)

        def save_after_start():
            start.wait(timeout=5)
            return core.save_index(self.db, self.raw, indexed)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [future.result(timeout=10) for future in (
                pool.submit(save_after_start), pool.submit(save_after_start))]
        self.assertEqual(sorted(item["status"] for item in results), ["REUSED", "SAVED"])
        self.assertEqual(results[0]["observation_id"], results[1]["observation_id"])
        with _sqlite_connection(self.db) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM observations").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT count(*) FROM filings").fetchone()[0], 3)

    def test_read_only_list_refuses_tampered_original_response(self):
        core.save_index(self.db, self.raw, self.indexed())
        with _sqlite_connection(self.db) as db:
            db.execute("UPDATE observations SET response=response || ?", (b" ",))
        with self.assertRaisesRegex(ValueError, "index response integrity"):
            core.list_filings(self.db, cik=CIK)

    def test_read_only_list_refuses_tampered_filing_metadata(self):
        core.save_index(self.db, self.raw, self.indexed())
        with _sqlite_connection(self.db) as db:
            record = json.loads(db.execute(
                "SELECT filing_json FROM filings LIMIT 1"
            ).fetchone()[0])
            record["source_uri"] = "https://attacker.invalid/filing.htm"
            db.execute("UPDATE filings SET filing_json=? WHERE accession=?",
                       (json.dumps(record), record["accession"]))
        with self.assertRaisesRegex(ValueError, "metadata does not match"):
            core.list_filings(self.db, cik=CIK)

    def test_read_only_list_refuses_uncontracted_metadata_fields(self):
        core.save_index(self.db, self.raw, self.indexed())
        with _sqlite_connection(self.db) as db:
            record = json.loads(db.execute(
                "SELECT filing_json FROM filings LIMIT 1"
            ).fetchone()[0])
            record["financial_claim_verified"] = True
            db.execute("UPDATE filings SET filing_json=? WHERE accession=?",
                       (json.dumps(record), record["accession"]))
        with self.assertRaisesRegex(ValueError, "metadata does not match"):
            core.list_filings(self.db, cik=CIK)

    def test_read_only_as_of_listing_does_not_change_sqlite_bytes(self):
        core.save_index(self.db, self.raw, self.indexed())
        before = self.db.read_bytes()
        self.assertEqual(len(core.list_filings(
            self.db, cik=CIK, as_of="2026-10-27")), 3)
        self.assertEqual(self.db.read_bytes(), before)

    def test_read_only_list_supports_uri_reserved_filename_characters(self):
        special_db = self.root / "ledger#archive.sqlite3"
        core.save_index(special_db, self.raw, self.indexed())
        self.assertEqual(len(core.list_filings(special_db, cik=CIK)), 3)

    def test_as_of_list_excludes_filings_not_observed_by_cutoff_day(self):
        core.save_index(self.db, self.raw, self.indexed())
        self.assertEqual(core.list_filings(self.db, cik=CIK, as_of="2026-10-26"), [])
        self.assertEqual(len(core.list_filings(self.db, cik=CIK, as_of="2026-10-27")), 3)

    def test_as_of_list_uses_observation_ledger_after_later_replay(self):
        first = self.indexed(collected_at="2026-10-27T00:00:00Z")
        core.save_index(self.db, self.raw, first)
        later_payload = json.loads(self.raw)
        later_payload["name"] = "SYNTHETIC UPDATED NAME"
        later_raw = json.dumps(later_payload).encode("utf-8")
        later = self.indexed(later_raw, as_of="2026-10-28",
                             collected_at="2026-10-28T00:00:00Z")
        core.save_index(self.db, later_raw, later)
        self.assertEqual(core.list_filings(self.db, cik=CIK, as_of="2026-10-26"), [])
        self.assertEqual(len(core.list_filings(self.db, cik=CIK, as_of="2026-10-27")), 3)
        self.assertEqual(len(core.list_filings(self.db, cik=CIK, as_of="2026-10-28")), 3)

    def test_identical_snapshot_tracks_last_check_without_rewriting_source(self):
        first = self.indexed(collected_at="2026-10-27T23:00:00Z")
        core.save_index(self.db, self.raw, first)
        later = self.indexed(as_of="2026-10-28", collected_at="2026-10-28T00:00:00Z")
        core.save_index(self.db, self.raw, later)
        core.save_index(self.db, self.raw, later)
        with _sqlite_connection(self.db) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM observations").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT count(*) FROM observation_checks").fetchone()[0], 2)
        before_read = self.db.read_bytes()
        as_of_27 = core.list_filings(self.db, cik=CIK, as_of="2026-10-27")[0]
        as_of_28 = core.list_filings(self.db, cik=CIK, as_of="2026-10-28")[0]
        self.assertEqual(as_of_27["first_seen_at"], "2026-10-27T23:00:00Z")
        self.assertEqual(as_of_27["last_checked_at"], "2026-10-27T23:00:00Z")
        self.assertEqual(as_of_28["first_seen_at"], "2026-10-27T23:00:00Z")
        self.assertEqual(as_of_28["last_checked_at"], "2026-10-28T00:00:00Z")
        self.assertEqual(as_of_28["last_checked_provenances"], ["OFFLINE_UNVERIFIED"])
        self.assertEqual(self.db.read_bytes(), before_read)

    def test_list_limit_requires_an_integer_not_bool_or_fraction(self):
        core.save_index(self.db, self.raw, self.indexed())
        for limit in (True, False, 1.5, "2"):
            with self.subTest(limit=limit), self.assertRaisesRegex(ValueError, "limit"):
                core.list_filings(self.db, cik=CIK, limit=limit)

    def test_list_orders_by_filing_date_across_accession_year_rollover(self):
        payload = json.loads(self.raw)
        recent = payload["filings"]["recent"]
        for key, values in (
                ("accessionNumber", ["0000320193-99-000001", "0000320193-00-000001"]),
                ("form", ["10-K", "10-K"]),
                ("filingDate", ["1999-01-01", "2000-01-01"]),
                ("acceptanceDateTime", ["1999-01-01T12:00:00Z", "2000-01-01T12:00:00Z"]),
                ("primaryDocument", ["old-1999.htm", "old-2000.htm"])):
            recent[key].extend(values)
        raw = json.dumps(payload).encode("utf-8")
        indexed = core.index_submissions(
            raw, cik=CIK, as_of="2026-10-27", forms=core.ALLOWED_FORMS,
            collected_at="2026-10-27T00:00:00Z",
        )
        core.save_index(self.db, raw, indexed)
        latest = core.list_filings(self.db, cik=CIK, limit=1)
        self.assertEqual(latest[0]["filed_at"], "2025-10-18")

    def test_changed_payload_creates_observation_not_revision_overwrite(self):
        baseline = self.indexed()
        core.save_index(self.db, self.raw, baseline)
        before = {x["accession"]: x for x in core.list_filings(self.db, cik=CIK)}
        payload = json.loads(self.raw)
        payload["name"] = "SYNTHETIC CHANGED SOURCE"
        payload["filings"]["recent"]["primaryDocument"][0] = "modified-10k.htm"
        raw2 = json.dumps(payload).encode()
        changed = self.indexed(raw2)
        outcome = core.save_index(self.db, raw2, changed)
        self.assertEqual(outcome["new_filings"], 0)
        self.assertEqual(before, {x["accession"]: x for x in core.list_filings(self.db, cik=CIK)})
        with _sqlite_connection(self.db) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM observations").fetchone()[0], 2)
            self.assertEqual(db.execute("SELECT count(*) FROM filing_observations").fetchone()[0], 6)

    def test_as_of_filter_excludes_future_and_historical_limit(self):
        before_acceptance = self.indexed(
            as_of="2025-10-15",
            collected_at="2025-10-15T17:59:59Z",
        )
        self.assertEqual(before_acceptance["indexed_count"], 0)

        at_acceptance = self.indexed(
            as_of="2025-10-15",
            collected_at="2025-10-15T18:00:00Z",
        )
        self.assertEqual(at_acceptance["indexed_count"], 1)
        self.assertEqual(at_acceptance["filings"][0]["form"], "10-K")

    def test_supported_form_filter(self):
        data = self.indexed(forms=core.parse_forms("8-K"))
        self.assertEqual([x["form"] for x in data["filings"]], ["8-K"])
        self.assertEqual(core.parse_forms("10-Q,8-K"), frozenset({"10-Q", "8-K"}))
        for raw in ("8-K,DO-NOT-ALLOW", "", "10-K,", None):
            with self.subTest(value=raw), self.assertRaises(ValueError):
                core.parse_forms(raw)

    def test_cik_and_calendar_validation(self):
        self.assertEqual(core.cik10("320193"), CIK)
        for raw in ("0", "-5", "0000000000", " 320193", "0x4e", "１", "12345678901"):
            with self.subTest(cik=raw), self.assertRaises(ValueError):
                core.cik10(raw)
        for raw in ("2026-02-30", "2026/10/27", "2026-1-1", "2026-13-01"):
            with self.subTest(date=raw), self.assertRaises(ValueError):
                core.parse_day(raw)

    def test_invalid_issuer_cik_rejected_before_db_save(self):
        payload = json.loads(self.raw)
        payload["cik"] = 1
        with self.assertRaisesRegex(ValueError, "issuer CIK"):
            self.indexed(json.dumps(payload).encode())
        self.assertFalse(self.db.exists())

    def test_invalid_alignment_and_duplicate_accession_rejected(self):
        payload = json.loads(self.raw)
        payload["filings"]["recent"]["form"].pop()
        with self.assertRaisesRegex(ValueError, "aligned"):
            self.indexed(json.dumps(payload).encode())
        payload = json.loads(self.raw)
        payload["filings"]["recent"]["accessionNumber"][1] = payload["filings"]["recent"]["accessionNumber"][0]
        with self.assertRaisesRegex(ValueError, "Duplicate accession"):
            self.indexed(json.dumps(payload).encode())

    def test_invalid_primary_document_does_not_enable_arbitrary_url(self):
        payload = json.loads(self.raw)
        payload["filings"]["recent"]["primaryDocument"][0] = "../secrets.html"
        record = self.indexed(json.dumps(payload).encode())["filings"][0]
        self.assertIsNone(record["source_uri"])

    def test_oversized_and_invalid_json_are_refused(self):
        with self.assertRaisesRegex(ValueError, "1..8MB"):
            self.indexed(b" " * (core.MAX_JSON_BYTES + 1))
        with self.assertRaisesRegex(ValueError, "Invalid UTF-8"):
            self.indexed(b"{BAD-JSON")
        with self.assertRaisesRegex(ValueError, "must be an aligned"):
            payload = json.loads(self.raw)
            del payload["filings"]["recent"]["primaryDocument"]
            self.indexed(json.dumps(payload).encode())

    def test_sqlite_output_symlink_is_refused_without_mutation(self):
        original = self.root / "original.sqlite3"
        indexed = self.indexed()
        core.save_index(original, self.raw, indexed)
        before = original.read_bytes()
        alias = self.root / "db-link.sqlite3"
        try:
            alias.symlink_to(original)
        except (NotImplementedError, OSError):
            self.skipTest("Symlink creation unavailable")
        with self.assertRaisesRegex(ValueError, "symbolic link"):
            core.save_index(alias, self.raw, indexed)
        self.assertEqual(original.read_bytes(), before)

    def test_module_entrypoint_process_offline_import(self):
        import subprocess
        import sys
        completed = subprocess.run([
            sys.executable, "-m", "disclosure_lightning",
            "--cik", CIK, "--as-of", "2026-10-27",
            "--db", str(self.db), "--input-json", str(FIXTURE),
            "--forms", "10-K,10-K/A,8-K",
            "--collected-at", "2026-10-27T00:00:00Z",
        ], capture_output=True, text=True, timeout=12,
           cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "SAVED")
        self.assertEqual(payload["new_filings"], 3)
        self.assertEqual(len(core.list_filings(self.db, cik=CIK)), 3)

    def test_local_cli_import_and_read_only_list(self):
        args = [
            "--cik", CIK, "--as-of", "2026-10-27", "--db", str(self.db),
            "--input-json", str(FIXTURE),
            "--forms", "10-K,10-K/A,8-K",
            "--collected-at", "2026-10-27T00:00:00Z",
        ]
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(core.main(args), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "SAVED")
        self.assertEqual(result["indexed"]["indexed_count"], 3)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(core.main(args), 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "REUSED")
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(core.main([
                "--cik", CIK, "--as-of", "2026-10-26", "--db", str(self.db), "--list"
            ]), 0)
        listing = json.loads(output.getvalue())
        self.assertEqual(listing["as_of"], "2026-10-26")
        self.assertEqual(listing["filings"], [])
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(core.main([
                "--cik", CIK, "--as-of", "2026-10-27", "--db", str(self.db), "--list"
            ]), 0)
        self.assertEqual(len(json.loads(output.getvalue())["filings"]), 3)

    def test_local_cli_refuses_ambiguous_input_without_writes(self):
        args = ["--cik", CIK, "--as-of", "2026-10-27", "--db", str(self.db)]
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(core.main(args), 2)
        self.assertIn("Choose exactly one", err.getvalue())
        self.assertFalse(self.db.exists())

    def test_historical_as_of_fails_closed_if_collected_later(self):
        for t in ("2026-10-28T00:00:00Z", "2026-10-27T23:30:00-12:00"):
            with self.subTest(collected=t), self.assertRaisesRegex(
                    ValueError, "COLLECTION_AFTER_AS_OF"):
                self.indexed(collected_at=t)
        for t in ("2026-10-27T00:00:00", "not-a-time", ""):
            with self.subTest(collected=t), self.assertRaisesRegex(
                    ValueError, "timestamp"):
                core.index_submissions(
                    self.raw, cik=CIK, as_of="2026-10-27",
                    forms=FORMS, collected_at=t or "not-a-time",
                )

    def test_utc_offset_timestamp_normalized_and_future_filing_filtered(self):
        record = self.indexed(collected_at="2026-10-27T21:00:00+09:00")
        self.assertEqual(record["collected_at"], "2026-10-27T12:00:00Z")
        self.assertEqual(record["indexed_count"], 3)
        for entry in record["filings"]:
            self.assertEqual(entry["collected_at"], record["collected_at"])
        before_acceptance = self.indexed(
            collected_at="2025-10-16T02:59:59+09:00",
            as_of="2025-10-15",
        )
        self.assertEqual(before_acceptance["indexed_count"], 0)
        at_acceptance = self.indexed(
            collected_at="2025-10-16T03:00:00+09:00",
            as_of="2025-10-15",
        )
        self.assertEqual(at_acceptance["indexed_count"], 1)
        self.assertEqual(at_acceptance["filings"][0]["accepted_at"],
                         "2025-10-15T18:00:00+00:00")

    def test_rejects_index_digest_spoof_before_creating_db(self):
        indexed = self.indexed()
        bad = {**indexed, "source_sha256": "0" * 64}
        with self.assertRaisesRegex(ValueError, "digest"):
            core.save_index(self.db, self.raw, bad)
        self.assertFalse(self.db.exists())

    def test_rejects_caller_edited_index_metadata_before_creating_db(self):
        import copy

        wrong_issuer = copy.deepcopy(self.indexed())
        wrong_issuer["issuer_cik"] = "0000000001"
        for record in wrong_issuer["filings"]:
            record["issuer_cik"] = "0000000001"
        wrong_document = copy.deepcopy(self.indexed())
        wrong_document["filings"][0]["filed_at"] = "2020-01-01"

        for name, candidate, reason in (
                ("wrong-issuer", wrong_issuer, "issuer CIK"),
                ("wrong-document", wrong_document, "does not match source row")):
            with self.subTest(name=name):
                db = self.root / f"{name}.sqlite3"
                with self.assertRaisesRegex(ValueError, reason):
                    core.save_index(db, self.raw, candidate)
                self.assertFalse(db.exists())

    def test_save_index_preserves_recent_source_row_bound(self):
        payload = json.loads(self.raw)
        recent = payload["filings"]["recent"]
        source_rows = core.MAX_RECORDS + 1
        for key, values in recent.items():
            recent[key] = [values[0]] * source_rows
        raw = json.dumps(payload).encode("utf-8")
        candidate = self.indexed()
        candidate["source_sha256"] = hashlib.sha256(raw).hexdigest()
        candidate["source_bytes"] = len(raw)
        candidate["filings"] = []
        candidate["indexed_count"] = 0
        with self.assertRaisesRegex(ValueError, "row limit"):
            core.save_index(self.db, raw, candidate)
        self.assertFalse(self.db.exists())

    def test_user_agent_placeholders_and_control_characters_rejected_pre_http(self):
        invalid = (
            "", "DisclosureLightning contact@example.com",
            "DisclosureLightning contact@example.org",
            "DisclosureLightning contact@your-real-domain.tld",
            "DisclosureLightning contact@placeholder.company",
            "DisclosureLightning contact@corp.invalid",
            "DisclosureLightning fake@example.net",
            "DisclosureLightning a@corp.com\r\nX-Evil: injected",
        )
        with patch("disclosure_lightning.core.urllib.request.build_opener") as opener:
            for user_agent in invalid:
                with self.subTest(ua=user_agent), self.assertRaisesRegex(
                        ValueError, "User-Agent"):
                    core.fetch_submissions(
                        CIK, user_agent=user_agent, allow_network=True
                    )
            opener.assert_not_called()

    def test_default_cli_preserves_amendment_filing(self):
        args = ["--cik", CIK, "--as-of", "2026-10-27",
                "--db", str(self.db), "--collected-at",
                "2026-10-27T00:00:00Z", "--input-json", str(FIXTURE)]
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(core.main(args), 0)
        result = json.loads(output.getvalue())
        self.assertIn("10-K/A", [x["form"] for x in result["indexed"]["filings"]])
        self.assertEqual(result["indexed"]["indexed_count"], 3)

    def test_live_request_rejects_injected_collected_time_without_io(self):
        with patch("disclosure_lightning.core.fetch_submissions") as fetch:
            with contextlib.redirect_stderr(io.StringIO()) as error:
                rc = core.main([
                    "--cik", CIK, "--as-of", "2026-10-27",
                    "--db", str(self.db), "--allow-network",
                    "--collected-at", "2026-10-27T00:00:00Z",
                ])
            self.assertEqual(rc, 2)
            self.assertIn("must be measured", error.getvalue())
            fetch.assert_not_called()
        self.assertFalse(self.db.exists())

    def test_kic_issuer_metadata_matches_curated_numeric_contract_without_auth(self):
        # This is DL PRODUCER contract only: proofinvest/dl_bridge.py is on
        # lead/kic and must still be integration-tested after PR review.
        from proofinvest.sec_companyfacts import run_curated_apple_demo
        fixture = (
            Path(__file__).resolve().parents[1] /
            "disclosure_lightning/fixtures/kic_apple_handoff_synthetic.json"
        ).read_bytes()
        indexed = core.index_submissions(
            fixture, cik=CIK, as_of="2025-11-01",
            forms=core.parse_forms("10-K"), collected_at="2025-11-01T10:30:00Z",
        )
        verdict = run_curated_apple_demo(as_of="2025-11-01")
        self.assertEqual(verdict["status"], "calculated_unverified")
        self.assertEqual(indexed["indexed_count"], 1)
        filing = indexed["filings"][0]
        self.assertEqual(filing["issuer_cik"], verdict["cik"])
        self.assertEqual(filing["accession"], verdict["accession"])
        self.assertEqual(filing["filed_at"], verdict["filing_date"])
        self.assertEqual(indexed["as_of_cutoff"], verdict["as_of"])
        self.assertEqual(filing["index_raw_sha256"], indexed["source_sha256"])
        self.assertIsNone(filing["raw_sha256"])
        self.assertEqual(filing["evidence_status"], "OFFLINE_SOURCE_UNVERIFIED")

    def test_network_requires_explicit_consent_and_contact(self):
        with patch("disclosure_lightning.core.urllib.request.build_opener") as opener:
            with self.assertRaisesRegex(ValueError, "Network disabled"):
                core.fetch_submissions(CIK, user_agent="", allow_network=False)
            with self.assertRaisesRegex(ValueError, "contact-bearing"):
                core.fetch_submissions(CIK, user_agent="Hi", allow_network=True)
            opener.assert_not_called()

    def test_network_mocked_https_response_sets_provenance_without_certifying_original(self):
        class FakeResponse:
            status = 200
            headers = {"Content-Type": "application/json"}
            def geturl(self):
                return "https://data.sec.gov/submissions/CIK0000320193.json"
            def read(self, size):
                return self_fixture
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return None
        self_fixture = self.raw
        with patch("disclosure_lightning.core.urllib.request.build_opener") as opener:
            opener.return_value.open.return_value = FakeResponse()
            received = core.fetch_submissions(
                CIK, user_agent="DisclosureLightning lab team@real-company.org",
                allow_network=True,
            )
            self.assertEqual(received, self.raw)
            opener.return_value.open.assert_called_once()
        index = core.index_submissions(
            received, cik=CIK, as_of="2026-10-27", forms=FORMS,
            provenance="SEC_HTTPS_RESPONSE",
            collected_at="2026-10-27T12:00:00Z",
        )
        self.assertEqual(index["filings"][0]["evidence_status"],
                         "INDEXED_OFFICIAL_HTTP_NOT_FULL_FILING_VERIFIED")
        self.assertIsNone(index["filings"][0]["raw_sha256"])


    def test_history_continuation_pinned_offline_dedup(self):
        from disclosure_lightning import history
        manifest = {
            "cik": 320193, "name": "SYNTHETIC",
            "filings": {
                "recent": {
                    "accessionNumber": [], "form": [],
                    "filingDate": [], "primaryDocument": [],
                },
                "files": [{
                    "name": "CIK0000320193-submissions-001.json",
                    "filingCount": 2, "filingFrom": "2015-01-01",
                    "filingTo": "2015-12-31",
                }],
            },
        }
        base_raw = json.dumps(manifest).encode("utf-8")
        base = core.index_submissions(
            base_raw, cik=CIK, as_of="2026-10-28",
            collected_at="2026-10-28T00:00:00Z",
            forms=core.parse_forms("10-K,8-K"))
        core.save_index(self.db, base_raw, base)
        pin = hashlib.sha256(base_raw).hexdigest()
        raw = json.dumps({
            "accessionNumber": [
                "0000320193-15-000001", "0000320193-15-000002"],
            "form": ["10-K", "8-K"],
            "filingDate": ["2015-10-30", "2015-11-02"],
            "primaryDocument": ["a.htm", "b.htm"],
        }).encode("utf-8")
        name = "CIK0000320193-submissions-001.json"
        params = dict(raw=raw, db_path=self.db, cik=CIK,
                      manifest_sha256=pin, name=name, as_of="2026-10-28",
                      collected_at="2026-10-28T00:05:00Z",
                      forms=core.parse_forms("10-K,8-K"))
        result = history.index_history_page(**params)
        self.assertEqual(result["indexed_count"], 2)
        self.assertTrue(all(x["evidence_status"] == "OFFLINE_SOURCE_UNVERIFIED"
                            and x["raw_sha256"] is None
                            for x in result["filings"]))
        self.assertEqual(core.save_index(self.db, raw, result)["new_filings"], 2)
        self.assertEqual(core.save_index(self.db, raw, result)["new_filings"], 0)
        for field, value in (
                ("history_manifest_sha256", "0" * 64),
                ("source_uri", "https://data.sec.gov/submissions/"
                 "CIK0000320193-submissions-002.json")):
            candidate = {**result, "filings": [dict(row) for row in result["filings"]]}
            candidate[field] = value
            if field == "source_uri":
                for row in candidate["filings"]:
                    row["index_source_uri"] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                core.save_index(self.db, raw, candidate)
        with self.assertRaises(ValueError):
            history.index_history_page(**{**params, "manifest_sha256": "0" * 64})
        with self.assertRaises(ValueError):
            history.index_history_page(**{**params, "collected_at": "2026-10-27T23:59:00Z"})
        wrong = json.loads(raw)
        wrong["filingDate"][0] = "2014-11-01"
        with self.assertRaisesRegex(ValueError, "OUTSIDE"):
            history.index_history_page(**{**params, "raw": json.dumps(wrong).encode("utf-8")})


    def _history_batch_fixture(self):
        from disclosure_lightning import history
        pages = [
            {"name": "CIK0000320193-submissions-001.json",
             "filingCount": 1, "filingFrom": "2014-01-01",
             "filingTo": "2014-12-31"},
            {"name": "CIK0000320193-submissions-002.json",
             "filingCount": 1, "filingFrom": "2015-01-01",
             "filingTo": "2015-12-31"},
        ]
        manifest = {
            "cik": 320193, "name": "SYNTHETIC TWO PAGE TEST",
            "filings": {
                "recent": {"accessionNumber": [], "form": [],
                           "filingDate": [], "primaryDocument": []},
                "files": pages,
            },
        }
        original = json.dumps(manifest).encode("utf-8")
        base = core.index_submissions(
            original, cik=CIK, as_of="2026-10-28",
            collected_at="2026-10-26T01:00:00Z",
            forms=core.parse_forms("10-K,8-K"),
        )
        core.save_index(self.db, original, base)
        source = {}
        for number, (name, year) in enumerate((
            ("CIK0000320193-submissions-001.json", 2014),
            ("CIK0000320193-submissions-002.json", 2015),
        ), 1):
            source[name] = json.dumps({
                "accessionNumber": [f"0000320193-{year % 100:02d}-{number:06d}"],
                "form": ["10-K"], "filingDate": [f"{year}-09-15"],
                "primaryDocument": [f"synthetic-{year}.htm"],
            }).encode("utf-8")
        args = {
            "db_path": self.db, "cik": CIK,
            "manifest_sha256": hashlib.sha256(original).hexdigest(),
            "as_of": "2026-10-28",
            "collected_at": "2026-10-28T01:05:00Z",
            "forms": core.parse_forms("10-K,8-K"),
        }
        return history, source, args

    def test_history_multi_page_preflight_and_idempotent_replay(self):
        history, pages, args = self._history_batch_fixture()
        with self.assertRaisesRegex(ValueError, "NOT_AVAILABLE_BY_AS_OF"):
            history.list_manifest_pages(
                db_path=self.db, cik=CIK,
                manifest_sha256=args["manifest_sha256"], as_of="2026-10-25")
        result = history.import_history_batch(pages=pages, **args)
        self.assertEqual(result["pages_processed"], 2)
        self.assertEqual(result["new_filings"], 2)
        self.assertEqual(result["provenance"], "OFFLINE_UNVERIFIED")
        self.assertEqual(result["network_requests"], 0)
        replay = history.import_history_batch(pages=pages, **args)
        self.assertEqual(replay["status"], "REUSED_BATCH")
        self.assertEqual(replay["new_filings"], 0)
        self.assertEqual(len(core.list_filings(self.db, cik=CIK)), 2)

    def test_history_multi_page_rejects_untrusted_before_any_write(self):
        history, pages, args = self._history_batch_fixture()
        first, second = sorted(pages)
        with self.assertRaisesRegex(ValueError, "DUPLICATE_ACCESSION"):
            other = json.loads(pages[second])
            other["accessionNumber"] = json.loads(pages[first])["accessionNumber"]
            history.import_history_batch(
                pages={first: pages[first], second: json.dumps(other).encode()},
                **args,
            )
        with self.assertRaises(ValueError):
            history.import_history_batch(
                pages={first: pages[first], second: b"not-json"}, **args)
        with _sqlite_connection(self.db) as connection:
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM observations").fetchone()[0], 1)
        self.assertEqual(len(core.list_filings(self.db, cik=CIK)), 0)

    def test_history_manifest_listing_and_local_directory(self):
        history, pages, args = self._history_batch_fixture()
        allowed = history.list_manifest_pages(
            db_path=self.db, cik=CIK,
            manifest_sha256=args["manifest_sha256"], as_of=args["as_of"])
        self.assertEqual(len(allowed), 2)
        self.assertTrue(all(item["eligible_by_start_date"] for item in allowed))
        folder = self.root / "offline-history"
        folder.mkdir()
        for name, contents in pages.items():
            (folder / name).write_bytes(contents)
        result = history.import_history_directory(directory=folder, **args)
        self.assertEqual(result["new_filings"], 2)
        with self.assertRaisesRegex(ValueError, "LIMIT"):
            history.import_history_directory(
                directory=folder, max_pages=1, **args)

    def test_history_batch_partial_failure_is_explicit_and_recoverable(self):
        from disclosure_lightning import history
        history, pages, args = self._history_batch_fixture()
        original_save = core.save_index
        attempts = [0]
        def second_page_failure(db_path, raw, indexed):
            attempts[0] += 1
            if attempts[0] == 2:
                raise sqlite3.OperationalError("SYNTHETIC_SAVE_FAILURE")
            return original_save(db_path, raw, indexed)
        with patch("disclosure_lightning.history.core.save_index",
                   side_effect=second_page_failure):
            with self.assertRaisesRegex(ValueError, "HISTORY_BATCH_PARTIAL_WRITE:1/2"):
                history.import_history_batch(pages=pages, **args)
        self.assertEqual(len(core.list_filings(self.db, cik=CIK)), 1)
        resumed = history.import_history_batch(pages=pages, **args)
        self.assertEqual(resumed["new_filings"], 1)
        self.assertEqual(len(core.list_filings(self.db, cik=CIK)), 2)


    def test_history_batch_cli_listing_and_replay(self):
        from disclosure_lightning import history
        history, pages, args = self._history_batch_fixture()
        directory = self.root / "saved-history-pages"
        directory.mkdir()
        for name, raw in pages.items():
            (directory / name).write_bytes(raw)
        shared = [
            "--db", str(self.db), "--cik", CIK,
            "--manifest-sha256", args["manifest_sha256"],
            "--as-of", args["as_of"],
        ]
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(history.main(shared + ["--list-manifest"]), 0)
        names = {item["name"] for item in json.loads(output.getvalue())["pages"]}
        self.assertEqual(names, set(pages))
        batch_args = shared + [
            "--batch-dir", str(directory),
            "--collected-at", args["collected_at"],
        ]
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(history.main(batch_args), 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "SAVED_BATCH")
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(history.main(batch_args), 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "REUSED_BATCH")


    def _amendment_review_fixture(self, *, with_period=True, ambiguous=False):
        from disclosure_lightning import history
        accessions = [
            "0000320193-25-000001", "0000320193-25-000002",
            "0000320193-25-000003",
        ]
        kinds = ["10-K", "10-K/A", "10-Q/A"]
        filing_dates = ["2025-02-20", "2025-03-04", "2025-08-10"]
        periods = ["2024-12-31", "2024-12-31", "2025-06-30"]
        if ambiguous:
            accessions.append("0000320193-25-000004")
            kinds.append("10-K")
            filing_dates.append("2025-02-28")
            periods.append("2024-12-31")
        columns = {
            "accessionNumber": accessions, "form": kinds,
            "filingDate": filing_dates,
            "primaryDocument": [f"local-{i}.htm" for i in range(len(kinds))],
        }
        if with_period:
            columns["reportDate"] = periods
        raw = json.dumps({
            "cik": 320193, "name": "SYNTHETIC ONLY",
            "filings": {"recent": columns, "files": []},
        }).encode("utf-8")
        indexed = core.index_submissions(
            raw, cik=CIK, as_of="2026-10-28",
            forms=core.parse_forms("10-K,10-K/A,10-Q/A"),
            collected_at="2026-10-28T00:30:00Z",
        )
        core.save_index(self.db, raw, indexed)
        return history

    def test_amendment_review_single_candidate_read_only(self):
        history = self._amendment_review_fixture()
        with _sqlite_connection(self.db) as conn:
            before = conn.execute(
                "SELECT COUNT(*) FROM observations").fetchone()[0]
        result = history.review_amendment_candidates(
            db_path=self.db, cik=CIK, as_of="2026-10-28")
        self.assertEqual(result["status"], "READ_ONLY_UNVERIFIED_AMENDMENT_REVIEW")
        amendments = {row["amendment_form"]: row for row in result["amendments"]}
        self.assertEqual(amendments["10-K/A"]["status"], "UNVERIFIED_PERIOD_MATCH_CANDIDATE")
        self.assertEqual(
            amendments["10-K/A"]["candidate_parent_accession"],
            "0000320193-25-000001")
        self.assertEqual(amendments["10-Q/A"]["status"], "NO_UNIQUE_BASE_MATCH")
        self.assertIsNone(amendments["10-Q/A"]["candidate_parent_accession"])
        self.assertTrue(all(not row["authenticated_amendment_relation"] and
                            row["authoritative_amends_accession"] is None
                            for row in amendments.values()))
        self.assertFalse(result["ledger_mutated"])
        with _sqlite_connection(self.db) as conn:
            self.assertEqual(before, conn.execute(
                "SELECT COUNT(*) FROM observations").fetchone()[0])
        self.assertTrue(all(item["amends_accession"] is None
                            for item in core.list_filings(self.db, cik=CIK)))

    def test_amendment_review_ambiguous_and_report_period_missing(self):
        history = self._amendment_review_fixture(ambiguous=True)
        result = history.review_amendment_candidates(
            db_path=self.db, cik=CIK, as_of="2026-10-28")
        first = next(row for row in result["amendments"]
                     if row["amendment_form"] == "10-K/A")
        self.assertEqual(first["status"], "AMBIGUOUS_MULTIPLE_BASE_MATCHES")
        self.assertEqual(first["candidate_count"], 2)
        self.assertIsNone(first["candidate_parent_accession"])

    def test_amendment_review_without_report_date_never_infers(self):
        history = self._amendment_review_fixture(with_period=False)
        result = history.review_amendment_candidates(
            db_path=self.db, cik=CIK, as_of="2026-10-28")
        self.assertEqual(len(result["amendments"]), 2)
        self.assertTrue(all(
            row["status"] == "REPORT_PERIOD_MISSING_NO_INFERENCE"
            and row["candidate_parent_accession"] is None
            for row in result["amendments"]
        ))

    def test_amendment_review_as_of_chronology_and_corrupted_raw(self):
        history = self._amendment_review_fixture()
        earlier = history.review_amendment_candidates(
            db_path=self.db, cik=CIK, as_of="2025-12-31")
        self.assertEqual(earlier["indexed_filings_checked"], 0)
        self.assertEqual(earlier["amendments"], [])
        with _sqlite_connection(self.db) as conn:
            conn.execute("UPDATE observations SET response=?",
                         (b"CORRUPTED-BY-SYNTHETIC-TEST",))
        with self.assertRaisesRegex(ValueError, "CORRUPTED"):
            history.review_amendment_candidates(
                db_path=self.db, cik=CIK, as_of="2026-10-28")


    def test_amendment_review_cli_read_only_no_manifest(self):
        from disclosure_lightning import history
        self._amendment_review_fixture()
        args = ["--db", str(self.db), "--cik", CIK,
                "--as-of", "2026-10-28", "--review-amendments"]
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(history.main(args), 0)
        data = json.loads(output.getvalue())
        self.assertEqual(data["status"], "READ_ONLY_UNVERIFIED_AMENDMENT_REVIEW")
        self.assertEqual(len(data["amendments"]), 2)
        with contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(history.main(args + ["--manifest-sha256", "0" * 64]), 2)
        self.assertIn("READ_ONLY", output.getvalue())


    def test_known_acceptance_time_after_local_observation_is_excluded(self):
        payload = json.loads(self.raw)
        payload["filings"]["recent"]["filingDate"][0] = "2026-10-28"
        payload["filings"]["recent"]["acceptanceDateTime"][0] = (
            "2026-10-28T12:00:00+09:00")
        source = json.dumps(payload).encode("utf-8")
        earlier = core.index_submissions(
            source, cik=CIK, as_of="2026-10-28", forms=FORMS,
            collected_at="2026-10-28T02:59:59Z")
        later = core.index_submissions(
            source, cik=CIK, as_of="2026-10-28", forms=FORMS,
            collected_at="2026-10-28T03:00:00Z")
        key = payload["filings"]["recent"]["accessionNumber"][0]
        self.assertNotIn(key, [entry["accession"] for entry in earlier["filings"]])
        self.assertIn(key, [entry["accession"] for entry in later["filings"]])
        self.assertTrue(all(entry["raw_sha256"] is None for entry in later["filings"]))

    def test_history_known_future_acceptance_excluded_before_batch_save(self):
        history, pages, args = self._history_batch_fixture()
        chosen = sorted(pages)[0]
        shaped = json.loads(pages[chosen])
        shaped["acceptanceDateTime"] = ["2026-10-28T01:06:00Z"]
        pages[chosen] = json.dumps(shaped).encode("utf-8")
        indexed = history.index_history_page(
            raw=pages[chosen], name=chosen, **args)
        self.assertEqual(indexed["filings"], [])
        first = history.import_history_batch(pages=pages, **args)
        self.assertEqual(first["new_filings"], 1)
        self.assertEqual(len(core.list_filings(self.db, cik=CIK)), 1)


    def test_unknown_same_day_acceptance_recent_is_excluded(self):
        base = json.loads(self.raw)
        base["filings"]["recent"]["filingDate"][0] = "2026-10-28"
        observation = "2026-10-28T01:00:00Z"
        accession = base["filings"]["recent"]["accessionNumber"][0]
        for invalid in (None, "", "2026-10-28T00:45:00"):
            with self.subTest(unknown_acceptance=invalid):
                snapshot = json.loads(json.dumps(base))
                snapshot["filings"]["recent"]["acceptanceDateTime"][0] = invalid
                actual = core.index_submissions(
                    json.dumps(snapshot).encode(), cik=CIK, as_of="2026-10-28",
                    forms=FORMS, collected_at=observation)
                self.assertNotIn(accession,
                                 [item["accession"] for item in actual["filings"]])
        prior = json.loads(json.dumps(base))
        prior["filings"]["recent"]["filingDate"][0] = "2026-10-27"
        prior["filings"]["recent"]["acceptanceDateTime"][0] = None
        allowed = core.index_submissions(
            json.dumps(prior).encode(), cik=CIK, as_of="2026-10-28",
            forms=FORMS, collected_at=observation)
        self.assertIn(accession, [item["accession"] for item in allowed["filings"]])

    def test_unknown_same_day_acceptance_history_is_excluded(self):
        from disclosure_lightning import history
        page_name = "CIK0000320193-submissions-001.json"
        index = json.dumps({
            "cik": 320193, "name": "SYNTHETIC ONLY",
            "filings": {
                "recent": {"accessionNumber": [], "form": [],
                           "filingDate": [], "primaryDocument": []},
                "files": [{
                    "name": page_name, "filingCount": 1,
                    "filingFrom": "2026-10-28", "filingTo": "2026-10-28"}],
            },
        }).encode()
        indexed = core.index_submissions(
            index, cik=CIK, as_of="2026-10-28",
            forms=core.parse_forms("10-K"),
            collected_at="2026-10-28T00:00:00Z")
        core.save_index(self.db, index, indexed)
        params = {
            "db_path": self.db, "cik": CIK, "name": page_name,
            "manifest_sha256": hashlib.sha256(index).hexdigest(),
            "as_of": "2026-10-28",
            "collected_at": "2026-10-28T01:00:00Z",
            "forms": core.parse_forms("10-K"),
        }
        payload = {
            "accessionNumber": ["0000320193-26-000001"],
            "form": ["10-K"], "filingDate": ["2026-10-28"],
            "primaryDocument": ["synthetic.htm"],
            "acceptanceDateTime": [""],
        }
        for invalid in ("", "2026-10-28T00:45:00"):
            with self.subTest(unknown=invalid):
                payload["acceptanceDateTime"][0] = invalid
                parsed = history.index_history_page(
                    json.dumps(payload).encode(), **params)
                self.assertEqual(parsed["indexed_count"], 0)
        payload["acceptanceDateTime"][0] = "2026-10-28T00:45:00Z"
        parsed = history.index_history_page(
            json.dumps(payload).encode(), **params)
        self.assertEqual(parsed["indexed_count"], 1)


    def test_history_batch_reports_missing_pages_without_claiming_authenticity(self):
        from disclosure_lightning import history
        history, pages, args = self._history_batch_fixture()
        first, second = sorted(pages)
        database_before_audit = self.db.read_bytes()
        initial_audit = history.audit_manifest_pages(
            db_path=self.db, cik=CIK,
            manifest_sha256=args["manifest_sha256"], as_of=args["as_of"])
        self.assertEqual(initial_audit["missing_eligible_pages"], [first, second])
        self.assertFalse(initial_audit["complete_for_pinned_manifest"])
        self.assertEqual(self.db.read_bytes(), database_before_audit)
        partial = history.import_history_batch(pages={first: pages[first]}, **args)
        self.assertEqual(partial["pages_processed"], 1)
        self.assertEqual(partial["selected_batch_missing_manifest_pages"], [second])
        self.assertFalse(partial["selected_batch_covers_eligible_manifest"])
        self.assertFalse(partial["issuer_history_authenticity_verified"])
        partial_audit = history.audit_manifest_pages(
            db_path=self.db, cik=CIK,
            manifest_sha256=args["manifest_sha256"], as_of=args["as_of"])
        self.assertEqual(partial_audit["missing_eligible_pages"], [second])
        completed = history.import_history_batch(pages=pages, **args)
        self.assertEqual(completed["selected_batch_missing_manifest_pages"], [])
        self.assertTrue(completed["selected_batch_covers_eligible_manifest"])
        self.assertFalse(completed["issuer_history_authenticity_verified"])
        self.assertEqual(completed["new_filings"], 1)
        final_audit = history.audit_manifest_pages(
            db_path=self.db, cik=CIK,
            manifest_sha256=args["manifest_sha256"], as_of=args["as_of"])
        self.assertTrue(final_audit["complete_for_pinned_manifest"])
        self.assertEqual(final_audit["imported_page_count"], 2)
        self.assertFalse(final_audit["source_authenticity_verified"])
        older_audit = history.audit_manifest_pages(
            db_path=self.db, cik=CIK,
            manifest_sha256=args["manifest_sha256"], as_of="2026-10-27")
        self.assertEqual(older_audit["missing_eligible_pages"], [first, second])
        with patch.object(history, "MAX_HISTORY_AUDIT_BYTES", 1):
            with self.assertRaisesRegex(ValueError, "BYTE_BUDGET"):
                history.audit_manifest_pages(
                    db_path=self.db, cik=CIK,
                    manifest_sha256=args["manifest_sha256"], as_of=args["as_of"])
        with _sqlite_connection(self.db) as db:
            db.execute("UPDATE observations SET response=response || ? WHERE sha256=?",
                       (b" ", hashlib.sha256(pages[first]).hexdigest()))
        with self.assertRaisesRegex(ValueError, "INTEGRITY_FAILED"):
            history.audit_manifest_pages(
                db_path=self.db, cik=CIK,
                manifest_sha256=args["manifest_sha256"], as_of=args["as_of"])

    def test_history_page_audit_requires_indexed_filing_associations(self):
        from disclosure_lightning import history
        history, pages, args = self._history_batch_fixture()
        first = sorted(pages)[0]
        history.import_history_batch(pages={first: pages[first]}, **args)
        with _sqlite_connection(self.db) as db:
            db.execute(
                "DELETE FROM filing_observations WHERE filing_cik=? AND accession=?",
                (CIK, "0000320193-14-000001"),
            )
        with self.assertRaisesRegex(ValueError, "INDEX_LINK_MISSING"):
            history.audit_manifest_pages(
                db_path=self.db, cik=CIK,
                manifest_sha256=args["manifest_sha256"], as_of=args["as_of"])

    def test_read_only_list_binds_historical_source_uri_to_page_receipt(self):
        from disclosure_lightning import history
        history, pages, args = self._history_batch_fixture()
        first = sorted(pages)[0]
        history.import_history_batch(pages={first: pages[first]}, **args)
        self.assertEqual(len(core.list_filings(self.db, cik=CIK)), 1)
        with _sqlite_connection(self.db) as db:
            encoded = db.execute(
                "SELECT filing_json FROM filings WHERE accession=?",
                ("0000320193-14-000001",),
            ).fetchone()[0]
            record = json.loads(encoded)
            record["index_source_uri"] = (
                "https://data.sec.gov/submissions/CIK0000320193-submissions-002.json")
            db.execute("UPDATE filings SET filing_json=? WHERE accession=?",
                       (json.dumps(record), record["accession"]))
        with self.assertRaisesRegex(ValueError, "page URI"):
            core.list_filings(self.db, cik=CIK)

    def test_history_page_revisions_are_preserved_and_audited_as_of(self):
        from disclosure_lightning import history
        history, pages, args = self._history_batch_fixture()
        first = sorted(pages)[0]
        early = args | {
            "as_of": "2026-10-27",
            "collected_at": "2026-10-27T01:05:00Z",
        }
        history.import_history_batch(pages={first: pages[first]}, **early)
        before_revision = history.audit_manifest_pages(
            db_path=self.db, cik=CIK,
            manifest_sha256=args["manifest_sha256"], as_of="2026-10-27")
        old_receipt = next(item for item in before_revision["pages"]
                           if item["name"] == first)
        self.assertEqual(old_receipt["page_sha256"], hashlib.sha256(pages[first]).hexdigest())
        self.assertEqual(before_revision["missing_eligible_pages"], [sorted(pages)[1]])

        revised_payload = json.loads(pages[first])
        revised_payload["primaryDocument"][0] = "revised-synthetic-2014.htm"
        revised_bytes = json.dumps(revised_payload).encode("utf-8")
        revised_args = args | {"collected_at": "2026-10-28T02:05:00Z"}
        first_save = history.import_history_batch(pages={first: revised_bytes}, **revised_args)
        replay = history.import_history_batch(pages={first: revised_bytes}, **revised_args)
        self.assertEqual(first_save["new_filings"], 0)
        self.assertEqual(replay["new_filings"], 0)
        with _sqlite_connection(self.db) as db:
            self.assertEqual(db.execute(
                "SELECT count(*) FROM history_page_receipt_versions WHERE page_name=?",
                (first,),
            ).fetchone()[0], 1)
        current = history.audit_manifest_pages(
            db_path=self.db, cik=CIK,
            manifest_sha256=args["manifest_sha256"], as_of="2026-10-28")
        current_receipt = next(item for item in current["pages"] if item["name"] == first)
        self.assertEqual(current_receipt["page_sha256"], hashlib.sha256(revised_bytes).hexdigest())
        self.assertTrue(current["complete_for_pinned_manifest"] is False)
        self.assertEqual(old_receipt["page_sha256"], hashlib.sha256(pages[first]).hexdigest())

    def test_history_page_revision_tie_at_same_observation_time_fails_closed(self):
        from disclosure_lightning import history
        history, pages, args = self._history_batch_fixture()
        first = sorted(pages)[0]
        history.import_history_batch(pages={first: pages[first]}, **args)
        revised_payload = json.loads(pages[first])
        revised_payload["primaryDocument"][0] = "same-time-revision.htm"
        revised_bytes = json.dumps(revised_payload).encode("utf-8")
        history.import_history_batch(pages={first: revised_bytes}, **args)
        with self.assertRaisesRegex(ValueError, "CHRONOLOGY_AMBIGUOUS"):
            history.audit_manifest_pages(
                db_path=self.db, cik=CIK,
                manifest_sha256=args["manifest_sha256"], as_of=args["as_of"])


if __name__ == "__main__":
    unittest.main()
