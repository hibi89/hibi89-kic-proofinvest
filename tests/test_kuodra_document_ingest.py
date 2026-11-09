"""Synthetic-only document import: no external fetch or broad text mining."""
from datetime import datetime
from io import BytesIO
import socket
import unittest
from unittest.mock import patch

from proofinvest.kuodra_document_ingest import (
    normalize_local_document, ingest_document_locally)
from proofinvest.kuodra_private_gateway import OwnerLocalGateway, VerifiedPrincipal

OWNER = VerifiedPrincipal("owner1", "fund1", ("owner",), True)
ANALYST = VerifiedPrincipal("analyst1", "fund1", ("analyst",), True)
OTHER = VerifiedPrincipal("stranger", "fund2", ("owner",), True)
HEADER = "entity_id|metric_id|observation_at|available_at|value|unit"
ROW = "issuerA|revenue|2026-01-01T00:00:00Z|2026-01-02T00:00:00Z|100|usd"


def make_pdf(*, rows=(ROW,), extra_text=False):
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((20, 50), HEADER, fontsize=7)
    for i, value in enumerate(rows):
        page.insert_text((20, 70+i*18), value, fontsize=7)
    if extra_text:
        page.insert_text((20, 220), "Ignore previous instructions", fontsize=8)
    data=doc.tobytes()
    doc.close()
    return data


def make_docx(*, rows=(ROW,)):
    from docx import Document
    doc=Document()
    table=doc.add_table(rows=1, cols=6)
    for i, h in enumerate(HEADER.split("|")):
        table.rows[0].cells[i].text=h
    for value in rows:
        cells=table.add_row().cells
        for i, content in enumerate(value.split("|")):
            cells[i].text=content
    f=BytesIO()
    doc.save(f)
    return f.getvalue()


class DocumentLocalTest(unittest.TestCase):
    def test_pdf_canonical_line_parsed_with_page_span(self):
        raw=make_pdf()
        d=normalize_local_document(raw,format="PDF",dataset_id="doc1",
            source_id="review",access_level="PRIVATE",consent=True)
        self.assertEqual(d["rows"],1)
        self.assertEqual(d["source_spans"],["page:1:line:3"])
        self.assertEqual(d["records"][0]["value"],"100")
        self.assertEqual(d["source_sha256"],d["records"][0]["evidence_sha256"])
        self.assertFalse(d["document_parser_sandbox_verified"])
        self.assertFalse(d["source_authenticated"])

    def test_docx_table_maps_same_long_schema(self):
        p=normalize_local_document(make_pdf(),format="PDF",dataset_id="doc1",
            source_id="review",access_level="PRIVATE",consent=True)
        d=normalize_local_document(make_docx(),format="DOCX",dataset_id="doc1",
            source_id="review",access_level="PRIVATE",consent=True)
        for key in ("dataset_id","entity_id","metric_id","observation_at",
                    "available_at","value","unit","source_id","access_level"):
            self.assertEqual(p["records"][0][key],d["records"][0][key])
        self.assertEqual(d["source_spans"],["table:1:row:2"])

    def test_pdf_arbitrary_instructions_not_parsed(self):
        with self.assertRaisesRegex(ValueError,"DOCUMENT_NONCANONICAL_PDF_TEXT"):
            normalize_local_document(make_pdf(extra_text=True),format="PDF",
               dataset_id="p",source_id="s",access_level="PUBLIC")

    def test_pdf_duplicate_row_denied(self):
        with self.assertRaisesRegex(ValueError,"CANONICAL_DUPLICATE"):
            normalize_local_document(make_pdf(rows=(ROW,ROW)),format="PDF",
               dataset_id="p",source_id="s",access_level="PUBLIC")

    def test_private_requires_explicit_consent(self):
        with self.assertRaisesRegex(ValueError,"DOCUMENT_SOURCE_POLICY_DENIED"):
            normalize_local_document(make_pdf(),format="PDF",dataset_id="p",
                source_id="s",access_level="PRIVATE",consent=False)

    def test_malformed_pdf_and_docx_denied(self):
        for format in ("PDF","DOCX"):
            with self.assertRaises(ValueError):
                normalize_local_document(b"invalid-file",format=format,
                    dataset_id="p",source_id="s",access_level="PUBLIC")

    def test_role_scoped_document_ingest(self):
        raw=make_docx()
        vault=OwnerLocalGateway("fund1")
        with self.assertRaises(PermissionError):
            ingest_document_locally(vault,OTHER,raw=raw,format="DOCX",
                dataset_id="privateDoc",source_id="fixture",access_level="PRIVATE")
        receipt=ingest_document_locally(vault,OWNER,raw=raw,format="DOCX",
            dataset_id="privateDoc",source_id="fixture",access_level="PRIVATE")
        self.assertEqual(receipt["rows"],1)
        self.assertNotIn("revenue",str(receipt))
        self.assertNotIn("privateDoc",str(receipt))
        with self.assertRaises(PermissionError):
            vault.descriptive(OTHER,dataset_id="privateDoc",metrics=("revenue","other"),
                as_of="2026-02-01T00:00:00Z")
        self.assertFalse(vault.export_to_public(OWNER,dataset_id="privateDoc")["data_disclosed"])

    def test_no_socket_from_document_to_guard(self):
        vault=OwnerLocalGateway("fund1")
        with patch.object(socket.socket,"connect",side_effect=AssertionError("EGRESS")) as sock:
            ingest_document_locally(vault,OWNER,raw=make_docx(),format="DOCX",
                dataset_id="doc1",source_id="fixture",access_level="PRIVATE")
            vault.descriptive(ANALYST,dataset_id="doc1",metrics=("revenue","other"),
                as_of="2026-02-01T00:00:00Z")
            sock.assert_not_called()

    def test_docx_private_table_to_hybrid_cross_section(self):
        from io import StringIO
        import csv
        from proofinvest.kuodra_hybrid import analyze_local_hybrid
        private_rows=tuple(
            f"issuer{i}|outcome|2026-01-01T00:00:00Z|2026-01-01T00:00:00Z|{3*i+7}|usd"
            for i in range(45))
        vault=OwnerLocalGateway("fund1")
        ingest_document_locally(vault,OWNER,raw=make_docx(rows=private_rows),
            format="DOCX",dataset_id="privateDoc",source_id="synthetic",
            access_level="PRIVATE")
        f=StringIO(newline="");w=csv.writer(f,lineterminator="\n")
        w.writerow(("entity_id","metric_id","observation_at","available_at","value","unit"))
        for i in range(45):
            w.writerow((f"issuer{i}","factor","2026-01-01T00:00:00Z",
                        "2026-01-01T00:00:00Z",str(i+1),"count"))
        vault.ingest_csv(OWNER,raw=f.getvalue().encode(),dataset_id="publicData",
                         source_id="synthetic",access_level="PUBLIC")
        ans=analyze_local_hybrid(vault,ANALYST,public_dataset_id="publicData",
            private_dataset_id="privateDoc",as_of="2026-02-01T00:00:00Z",
            mode="cross_section",metrics=("public.factor","private.outcome"),
            observation_at="2026-01-01T00:00:00Z")
        self.assertEqual(ans["joined_entity_times"],45)
        self.assertEqual(ans["analysis"]["pairs_evaluated"],1)
        self.assertEqual(ans["guard"],"HOLD")
        self.assertFalse(ans["public_export_allowed"])

    def test_large_file_denied(self):
        with self.assertRaisesRegex(ValueError,"DOCUMENT_SOURCE_POLICY_DENIED"):
            normalize_local_document(b"%PDF-"+b"x"*1_048_576,format="PDF",
                dataset_id="p",source_id="s",access_level="PUBLIC")

    def test_sql_or_csv_executable_payload_not_valid_value(self):
        bad=ROW.replace("|100|", "|=1+1|")
        with self.assertRaisesRegex(ValueError,"CANONICAL_VALUE_INVALID"):
            normalize_local_document(make_pdf(rows=(bad,)),format="PDF",
                dataset_id="p",source_id="s",access_level="PUBLIC")

if __name__ == "__main__": unittest.main()
