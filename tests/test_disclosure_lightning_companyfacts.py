"""Synthetic raw CompanyFacts evidence and cache tests; no SEC traffic."""
from __future__ import annotations

import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import urllib.error
from unittest.mock import patch

from disclosure_lightning import companyfacts, core
from proofinvest.sec_companyfacts import verify_sec_annual_revenue


CIK = "0000320193"
AS_OF = "2026-10-28"
COLLECTED = "2026-10-28T00:00:00Z"
RAW = json.dumps({
    "cik": 320193,
    "entityName": "Synthetic Issuer",
    "facts": {"us-gaap": {"Assets": {"units": {"USD": [
        {"fy": 2025, "fp": "FY", "form": "10-K", "val": 100,
         "filed": "2025-11-01", "end": "2025-09-27"},
    ]}}}},
}, separators=(",", ":")).encode()


class CompanyFactsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dl-companyfacts-")
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "ledger.sqlite3"

    def save(self, raw=RAW, provenance="OFFLINE_UNVERIFIED", etag=None,
             check_provenance=None):
        meta = companyfacts.index_companyfacts(
            raw, cik=CIK, as_of=AS_OF, collected_at=COLLECTED,
            provenance=provenance,
        )
        return companyfacts.save_companyfacts(
            self.db, raw, meta, etag=etag,
            check_provenance=check_provenance,
        ), meta

    def test_raw_evidence_append_only_deduplicates_and_read_is_as_of_gated(self):
        first, meta = self.save()
        second, _ = self.save()
        self.assertEqual(first["status"], "SAVED")
        self.assertEqual(second["status"], "REUSED")
        self.assertEqual(companyfacts.read_companyfacts(
            self.db, cik=CIK, sha256=meta["source_sha256"], as_of=AS_OF), RAW)
        self.assertEqual(len(companyfacts.list_companyfacts(
            self.db, cik=CIK, as_of=AS_OF)), 1)
        with self.assertRaises(ValueError):
            companyfacts.read_companyfacts(
                self.db, cik=CIK, sha256=meta["source_sha256"], as_of="2026-10-27")
        with closing(sqlite3.connect(self.db)) as db:
            count = db.execute("SELECT count(*) FROM companyfacts_observations").fetchone()[0]
        self.assertEqual(count, 1)

    def test_cik_payload_and_future_collection_are_rejected(self):
        wrong = RAW.replace(b'"cik":320193', b'"cik":1')
        with self.assertRaisesRegex(ValueError, "CIK"):
            companyfacts.index_companyfacts(wrong, cik=CIK, as_of=AS_OF,
                                             collected_at=COLLECTED)
        with self.assertRaisesRegex(ValueError, "COLLECTION_AFTER_AS_OF"):
            companyfacts.index_companyfacts(RAW, cik=CIK, as_of="2026-10-27",
                                             collected_at=COLLECTED)

    def test_response_hash_corruption_is_detected_on_read(self):
        _, meta = self.save()
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("UPDATE companyfacts_observations SET response=? WHERE sha256=?",
                       (b"{}", meta["source_sha256"]))
            db.commit()
        with self.assertRaisesRegex(ValueError, "integrity"):
            companyfacts.read_companyfacts(self.db, cik=CIK,
                                            sha256=meta["source_sha256"])

    def test_offline_companyfacts_input_uses_its_larger_explicit_bound(self):
        padded = RAW[:-1] + b',"padding":"' + b"x" * 8_000_001 + b'"}'
        source = Path(self.temp.name) / "large-companyfacts.json"
        source.write_bytes(padded)
        with self.assertRaisesRegex(ValueError, "bounded regular file"):
            core._read_local_json(source)
        loaded = core._read_local_json(
            source, max_bytes=companyfacts.MAX_COMPANYFACTS_BYTES,
        )
        self.assertEqual(len(loaded), len(padded))
        indexed = companyfacts.index_companyfacts(
            loaded, cik=CIK, as_of=AS_OF, collected_at=COLLECTED,
        )
        self.assertEqual(indexed["source_bytes"], len(padded))

    def test_failed_check_write_rolls_back_new_observation(self):
        self.save()
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("CREATE TRIGGER reject_companyfacts_check "
                       "BEFORE INSERT ON companyfacts_checks "
                       "BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END")
            db.commit()
        changed = RAW.replace(b'"val":100', b'"val":101')
        indexed = companyfacts.index_companyfacts(
            changed, cik=CIK, as_of=AS_OF, collected_at=COLLECTED,
        )
        with self.assertRaises(sqlite3.IntegrityError):
            companyfacts.save_companyfacts(self.db, changed, indexed)
        with closing(sqlite3.connect(self.db)) as db:
            count = db.execute("SELECT count(*) FROM companyfacts_observations").fetchone()[0]
        self.assertEqual(count, 1)

    def test_live_response_validator_is_bound_to_saved_hash_and_uri(self):
        tag = '"synthetic-v1"'
        self.save(provenance="SEC_HTTPS_RESPONSE", etag=tag)
        cache = companyfacts._load_cache(self.db, CIK)
        self.assertEqual(cache["etag"], tag)
        self.assertEqual(cache["sha256"], hashlib.sha256(RAW).hexdigest())
        self.assertEqual(cache["raw"], RAW)
        self.assertFalse(companyfacts.index_companyfacts(
            RAW, cik=CIK, as_of=AS_OF, collected_at=COLLECTED,
            provenance="SEC_HTTPS_RESPONSE",
        )["financial_claim_verified"])

    def test_mocked_live_200_requires_json_and_returns_validated_etag(self):
        class Response:
            status = 200

            def __init__(self, content_type="application/json; charset=utf-8"):
                self.headers = {"Content-Type": content_type,
                                "Content-Length": str(len(RAW)),
                                "ETag": '"synthetic-v1"'}

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def geturl(self):
                return companyfacts.source_uri(CIK)

            def read(self, size):
                self.asserted_read_limit = size
                return RAW

        opener = unittest.mock.Mock()
        opener.open.return_value = Response()
        with patch("disclosure_lightning.companyfacts.urllib.request.build_opener",
                   return_value=opener):
            result = companyfacts._fetch_http(
                CIK, user_agent="DL synthetic test contact@sec.gov",
            )
        self.assertEqual(result, (RAW, '"synthetic-v1"', False))
        request = opener.open.call_args.args[0]
        self.assertEqual(request.get_header("Accept"), "application/json")
        self.assertIsNone(request.get_header("If-none-match"))

        opener.open.return_value = Response("text/html")
        with patch("disclosure_lightning.companyfacts.urllib.request.build_opener",
                   return_value=opener):
            with self.assertRaisesRegex(ValueError, "not JSON"):
                companyfacts._fetch_http(
                    CIK, user_agent="DL synthetic test contact@sec.gov",
                )

    def test_conditional_304_reuses_verified_bytes_without_network(self):
        tag = '"synthetic-v1"'
        self.save(provenance="SEC_HTTPS_RESPONSE", etag=tag)
        cached = companyfacts._load_cache(self.db, CIK)
        url = companyfacts.source_uri(CIK)
        error = urllib.error.HTTPError(
            url, 304, "Not Modified", {"ETag": tag}, io.BytesIO(),
        )
        opener = unittest.mock.Mock()
        opener.open.side_effect = error
        with patch("disclosure_lightning.companyfacts.urllib.request.build_opener",
                   return_value=opener):
            raw, etag, unchanged = companyfacts._fetch_http(
                CIK, user_agent="DL synthetic test contact@sec.gov", cached=cached,
            )
        self.assertEqual((raw, etag, unchanged), (RAW, tag, True))
        request = opener.open.call_args.args[0]
        self.assertEqual(request.get_header("If-none-match"), tag)
        self.assertEqual(request.full_url, url)
        indexed = companyfacts.index_companyfacts(
            raw, cik=CIK, as_of=AS_OF, collected_at=COLLECTED,
            provenance="SEC_HTTPS_RESPONSE",
        )
        saved = companyfacts.save_companyfacts(
            self.db, raw, indexed, etag=etag,
            check_provenance="SEC_HTTPS_304_NOT_MODIFIED",
        )
        self.assertEqual(saved["status"], "REUSED")
        with closing(sqlite3.connect(self.db)) as db:
            check = db.execute(
                "SELECT provenance FROM companyfacts_checks WHERE issuer_cik=? AND sha256=?",
                (CIK, indexed["source_sha256"]),
            ).fetchall()
        self.assertEqual({row[0] for row in check}, {
            "SEC_HTTPS_RESPONSE", "SEC_HTTPS_304_NOT_MODIFIED",
        })

    def test_live_fetch_requires_explicit_opt_in_and_valid_contact(self):
        with self.assertRaisesRegex(ValueError, "Network disabled"):
            companyfacts.fetch_companyfacts_with_cache(
                self.db, CIK, user_agent="analyst@example.org")
        with patch("disclosure_lightning.companyfacts.urllib.request.build_opener") as opener:
            with self.assertRaisesRegex(ValueError, "User-Agent"):
                companyfacts._fetch_http(CIK, user_agent="placeholder@example.org")
            opener.assert_not_called()

    def test_offline_cli_import_then_read_only_list(self):
        source = Path(self.temp.name) / "companyfacts.json"
        source.write_bytes(RAW)
        output = StringIO()
        argv = ["--db", str(self.db), "--cik", CIK, "--as-of", AS_OF]
        with redirect_stdout(output), redirect_stderr(StringIO()):
            self.assertEqual(companyfacts.main(argv + [
                "--input-json", str(source), "--collected-at", COLLECTED,
            ]), 0)
        saved = json.loads(output.getvalue())
        self.assertEqual(saved["status"], "SAVED")
        self.assertFalse(saved["financial_claim_verified"])
        output = StringIO()
        with redirect_stdout(output), redirect_stderr(StringIO()):
            self.assertEqual(companyfacts.main(argv + ["--list"]), 0)
        listed = json.loads(output.getvalue())
        self.assertEqual(listed["status"], "READ_ONLY")
        self.assertEqual(len(listed["observations"]), 1)
        output = StringIO()
        with redirect_stdout(output), redirect_stderr(StringIO()):
            self.assertEqual(companyfacts.main(argv + [
                "--read-sha256", saved["source_sha256"],
            ]), 0)
        envelope = json.loads(output.getvalue())
        self.assertEqual(envelope["schema"],
                         "disclosure-lightning.companyfacts-envelope.v1")
        self.assertEqual(envelope["companyfacts"], json.loads(RAW))
        self.assertFalse(envelope["financial_claim_verified"])
        self.assertFalse(envelope["source_authenticity_verified"])

    def test_saved_companyfacts_bytes_feed_current_kic_read_only_consumer(self):
        accession = "0000320193-25-000079"
        current = {"accn": accession, "form": "10-K", "start": "2024-09-29",
                   "end": "2025-09-27", "filed": "2025-11-01", "val": 125}
        prior = {"accn": accession, "form": "10-K", "start": "2023-10-01",
                 "end": "2024-09-28", "filed": "2025-11-01", "val": 100}
        raw = json.dumps({
            "cik": 320193, "entityName": "Synthetic Issuer",
            "facts": {"us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {"USD": [prior, current]},
                },
            }},
        }, separators=(",", ":")).encode()
        cutoff = "2025-11-02"
        indexed = companyfacts.index_companyfacts(
            raw, cik=CIK, as_of=cutoff, collected_at="2025-11-02T00:00:00Z",
        )
        companyfacts.save_companyfacts(self.db, raw, indexed)
        handoff = companyfacts.read_companyfacts_envelope(
            self.db, cik=CIK, sha256=indexed["source_sha256"], as_of=cutoff,
        )
        verdict = verify_sec_annual_revenue(
            handoff["companyfacts"], cik=CIK, accession=accession,
            current_end="2025-09-27", prior_end="2024-09-28", as_of=cutoff,
        )
        self.assertEqual(verdict["status"], "calculated_unverified")
        self.assertEqual(verdict["current_usd"], "125")
        self.assertFalse(verdict["authenticated_external_source"])
        self.assertFalse(verdict["live_api_called"])


if __name__ == "__main__":
    unittest.main()
