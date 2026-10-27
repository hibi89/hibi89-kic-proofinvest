"""Offline SEC-shaped fixtures only. No live API or private Bid Owl code."""
from __future__ import annotations
from datetime import date
from pathlib import Path
import copy
import hashlib
import json
import tempfile
import unittest

from disclosure_lightning.mvp import parse_submissions, persist, export_filings, read_json_file
from disclosure_lightning.cli import main

CIK = "0000320193"
COLLECTED = "2026-10-27T10:00:00+00:00"
AS_OF = "2026-10-27"


def sample():
    return {
        "cik": 320193,
        "filings": {"recent": {
            "accessionNumber": ["0000320193-26-000001", "0000320193-26-000002"],
            "form": ["10-K", "10-K/A"],
            "filingDate": ["2026-10-20", "2026-10-21"],
            "primaryDocument": ["a10k.htm", "a10ka.htm"],
        }},
    }


def raw(payload=None):
    return json.dumps(sample() if payload is None else payload, sort_keys=True).encode()


def parsed(payload=None, **kw):
    return parse_submissions(raw(payload), cik=CIK, collected_at=COLLECTED,
                             as_of=AS_OF, **kw)


class DlMinimumUnitTests(unittest.TestCase):
    def test_offline_ingestion_and_no_filing_content_claim(self):
        result = parsed()
        self.assertEqual(result["status"], "parsed_offline_unverified")
        self.assertEqual(len(result["records"]), 2)
        self.assertFalse(result["live_api_called"])
        self.assertEqual(result["source_payload_sha256"], hashlib.sha256(raw()).hexdigest())
        first = result["records"][0]
        self.assertEqual(first["record_type"], "RawFilingEnvelopeV1")
        self.assertEqual(first["issuer_cik"], CIK)
        self.assertEqual(first["evidence_status"], "METADATA_ONLY_UNVERIFIED")
        self.assertEqual(first["raw_sha256_scope"], "SEC_SUBMISSIONS_JSON_NOT_FILING")
        self.assertIsNone(first["filing_content_sha256"])
        self.assertFalse(first["original_filing_retrieved"])
        self.assertEqual(first["source_uri"],
            "https://www.sec.gov/Archives/edgar/data/320193/000032019326000001/a10k.htm")

    def test_repeated_import_is_idempotent_and_amendment_kept(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "filings.db"
            record = parsed()
            self.assertEqual(persist(db, record),
                             {"versions_added": 2, "observations_added": 2})
            self.assertEqual(persist(db, record),
                             {"versions_added": 0, "observations_added": 0})
            exported = export_filings(db, cik=CIK)
            self.assertEqual(len(exported), 2)
            self.assertEqual([x["form"] for x in exported], ["10-K", "10-K/A"])
            self.assertFalse(exported[0]["amendment_form"])
            self.assertTrue(exported[1]["amendment_form"])
            self.assertIsNone(exported[1]["amends_accession"])

    def test_second_snapshot_adds_observation_not_duplicate_version(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "filings.db"
            persist(db, parsed())
            newer = sample()
            newer["filings"]["recent"]["accessionNumber"].append("0000320193-26-000003")
            newer["filings"]["recent"]["form"].append("8-K")
            newer["filings"]["recent"]["filingDate"].append("2026-10-26")
            newer["filings"]["recent"]["primaryDocument"].append("a8k.htm")
            self.assertEqual(persist(db, parsed(newer)),
                             {"versions_added": 1, "observations_added": 3})
            self.assertEqual(len(export_filings(db, cik=CIK)), 3)

    def test_cik_mismatch_and_bad_target_rejected(self):
        poison = sample()
        poison["cik"] = 42
        with self.assertRaisesRegex(ValueError, "SOURCE_CIK_MISMATCH"):
            parsed(poison)
        with self.assertRaisesRegex(ValueError, "INVALID_CIK"):
            parse_submissions(raw(), cik="320193", collected_at=COLLECTED, as_of=AS_OF)

    def test_future_filing_is_excluded(self):
        poison = sample()
        poison["filings"]["recent"]["filingDate"][1] = "2026-10-29"
        result = parsed(poison)
        self.assertEqual(result["excluded_future"], 1)
        self.assertEqual(len(result["records"]), 1)

    def test_collection_after_asof_is_not_historical_evidence(self):
        with self.assertRaisesRegex(ValueError, "COLLECTION_AFTER_AS_OF"):
            parse_submissions(raw(), cik=CIK,
                              collected_at="2026-10-28T00:01:00Z", as_of=AS_OF)

    def test_missing_timezone_rejected(self):
        with self.assertRaisesRegex(ValueError, "COLLECTION_TIME_MUST_HAVE_OFFSET"):
            parse_submissions(raw(), cik=CIK,
                              collected_at="2026-10-27T10:00:00", as_of=AS_OF)

    def test_adversarial_document_and_accession_rejected(self):
        for field, value, error in (
            ("primaryDocument", "../secret", "INVALID_PRIMARY_DOCUMENT"),
            ("accessionNumber", "xxx", "INVALID_ACCESSION"),
            ("filingDate", "2026-02-30", "INVALID_DATE"),
        ):
            with self.subTest(field=field):
                poison = sample()
                poison["filings"]["recent"][field][0] = value
                with self.assertRaisesRegex(ValueError, error):
                    parsed(poison)

    def test_malformed_column_lengths_rejected(self):
        poison = sample()
        poison["filings"]["recent"]["form"].pop()
        with self.assertRaisesRegex(ValueError, "MISMATCHED_OR_OVERSIZED_COLUMNS"):
            parsed(poison)

    def test_duplicate_accession_rejected(self):
        poison = sample()
        poison["filings"]["recent"]["accessionNumber"][1] = poison["filings"]["recent"]["accessionNumber"][0]
        with self.assertRaisesRegex(ValueError, "DUPLICATED_ACCESSION"):
            parsed(poison)

    def test_not_json_and_nonbytes_rejected(self):
        with self.assertRaisesRegex(ValueError, "INVALID_SUBMISSIONS_JSON"):
            parse_submissions(b"{broken", cik=CIK, collected_at=COLLECTED, as_of=AS_OF)
        with self.assertRaises(ValueError):
            parse_submissions("not-bytes", cik=CIK, collected_at=COLLECTED, as_of=AS_OF)

    def test_offline_cli_roundtrip_and_symlink_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source = folder / "sample.json"
            source.write_bytes(raw())
            db = folder / "filings.sqlite"
            from unittest.mock import patch
            from contextlib import redirect_stdout
            from io import StringIO
            output = StringIO()
            args = ["--input", str(source), "--database", str(db),
                    "--cik", CIK, "--collected-at", COLLECTED, "--as-of", AS_OF]
            with redirect_stdout(output):
                code = main(args)
            self.assertEqual(code, 0)
            receipt = json.loads(output.getvalue())
            self.assertEqual(receipt["accepted_records"], 2)
            self.assertEqual(receipt["versions_added"], 2)
            self.assertFalse(receipt["live_api_called"])
            self.assertEqual(read_json_file(source), raw())
            link = folder / "alias.json"
            link.symlink_to(source)
            with self.assertRaises(ValueError):
                read_json_file(link)


if __name__ == "__main__":
    unittest.main()
