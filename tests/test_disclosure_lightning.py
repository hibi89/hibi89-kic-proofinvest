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
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM observations").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT count(*) FROM filings").fetchone()[0], 3)
            self.assertEqual(db.execute("SELECT response FROM observations").fetchone()[0], self.raw)

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
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM observations").fetchone()[0], 2)
            self.assertEqual(db.execute("SELECT count(*) FROM filing_observations").fetchone()[0], 6)

    def test_as_of_filter_excludes_future_and_historical_limit(self):
        result = self.indexed(as_of="2025-10-15",
                              collected_at="2025-10-15T00:00:00Z")
        self.assertEqual(result["indexed_count"], 1)
        self.assertEqual(result["filings"][0]["form"], "10-K")

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
        before = self.indexed(
            collected_at="2025-10-15T08:00:00Z",
            as_of="2026-10-27",
        )
        self.assertEqual(before["indexed_count"], 1)

    def test_rejects_index_digest_spoof_before_creating_db(self):
        indexed = self.indexed()
        bad = {**indexed, "source_sha256": "0" * 64}
        with self.assertRaisesRegex(ValueError, "digest"):
            core.save_index(self.db, self.raw, bad)
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
            collected_at="2026-10-28T01:00:00Z",
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
        with sqlite3.connect(self.db) as connection:
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


if __name__ == "__main__":
    unittest.main()
