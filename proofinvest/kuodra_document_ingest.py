"""Conservative local PDF/DOCX canonical-measurement table ingestion.

ONLY machine-readable, explicitly formatted six-column numeric measurement
rows. Does not run OCR, macros, embedded code, outbound requests, or remote AI.
File parsing is NOT a hardened sandbox; handle actual confidential documents
only in institution-approved isolated workers with verified authentication.
"""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO, StringIO
import csv
import zipfile
from xml.etree import ElementTree
from xml.parsers import expat
from typing import Any

from .kuodra_private_gateway import OwnerLocalGateway, VerifiedPrincipal
from .kuodra_unified_core import HEADER, _id, normalize_local_csv

_MAX_RAW = 1_048_576
_MAX_ROWS = 200
_MAX_PAGES = 10
_MAX_ZIP_ITEMS = 100
_MAX_ZIP_EXPANDED = 8_388_608


def _safe_docx_table(raw: bytes) -> tuple[list[list[str]], list[str]]:
    if not raw.startswith(b"PK\x03\x04"):
        raise ValueError("DOCUMENT_DOCX_SIGNATURE_INVALID")
    try:
        with zipfile.ZipFile(BytesIO(raw)) as z:
            info = z.infolist()
            if (not 1 <= len(info) <= _MAX_ZIP_ITEMS
                    # Duplicate OPC package parts are ambiguous: zipfile and
                    # python-docx may resolve different-looking originals to
                    # the last copy. Never interpret such financial evidence.
                    or len({x.filename for x in info}) != len(info)
                    or sum(x.file_size for x in info) > _MAX_ZIP_EXPANDED
                    or any(x.flag_bits & 1 for x in info)
                    or any(x.filename.startswith("/") or ".." in x.filename.split("/")
                           or "\\" in x.filename for x in info)
                    or any("vbaProject" in x.filename or "embeddings/" in x.filename
                           or "activeX/" in x.filename for x in info)
                    or "word/document.xml" not in z.namelist()):
                raise ValueError("DOCUMENT_DOCX_PACKAGE_DENIED")
            # Reject external resource relationships. No network resolver should
            # be used even if a future document library changes behavior.
            for x in info:
                if x.filename.endswith(".rels"):
                    rel = z.read(x)
                    # A raw-byte DTD scan misses UTF-16/other XML encodings.
                    # Deny DTD/entity declarations in the encoding-aware XML
                    # parser before python-docx handles any package part.
                    parser = expat.ParserCreate()
                    def _deny_declaration(*_args: object) -> None:
                        raise ValueError("DOCUMENT_DOCX_RELATIONSHIP_XML_DENIED")
                    parser.StartDoctypeDeclHandler = _deny_declaration
                    parser.EntityDeclHandler = _deny_declaration
                    parser.ExternalEntityRefHandler = _deny_declaration
                    try:
                        parser.Parse(rel, True)
                        root = ElementTree.fromstring(rel)
                    except (expat.ExpatError, ElementTree.ParseError) as exc:
                        raise ValueError("DOCUMENT_DOCX_RELATIONSHIP_XML_DENIED") from exc
                    if any((part.get("TargetMode") or "Internal").strip().casefold()
                           != "internal" for part in root.iter()):
                        raise ValueError("DOCUMENT_EXTERNAL_RELATIONSHIP_DENIED")
    except (zipfile.BadZipFile, OSError, RuntimeError) as exc:
        raise ValueError("DOCUMENT_DOCX_PACKAGE_DENIED") from exc
    try:
        from docx import Document
    except ImportError as exc:
        raise ValueError("DOCUMENT_DOCX_PARSER_NOT_INSTALLED") from exc
    try:
        doc = Document(BytesIO(raw))
        if len(doc.tables) != 1:
            raise ValueError("DOCUMENT_EXACTLY_ONE_TABLE_REQUIRED")
        table = doc.tables[0]
        if not 2 <= len(table.rows) <= _MAX_ROWS + 1:
            raise ValueError("DOCUMENT_ROW_COUNT_INVALID")
        lines = [[cell.text.strip() for cell in row.cells] for row in table.rows]
    except (KeyError, OSError, ValueError) as exc:
        raise ValueError("DOCUMENT_TABLE_PARSE_DENIED") from exc
    return lines, [f"table:1:row:{i}" for i in range(2, len(lines)+1)]


def _safe_pdf_table(raw: bytes) -> tuple[list[list[str]], list[str]]:
    if not raw.startswith(b"%PDF-"):
        raise ValueError("DOCUMENT_PDF_SIGNATURE_INVALID")
    try:
        import fitz
    except ImportError as exc:
        raise ValueError("DOCUMENT_PDF_PARSER_NOT_INSTALLED") from exc
    rows: list[list[str]] = []
    spans: list[str] = []
    try:
        with fitz.open(stream=raw, filetype="pdf") as doc:
            if (doc.is_encrypted or not 1 <= len(doc) <= _MAX_PAGES
                    or doc.embfile_count() != 0):
                raise ValueError("DOCUMENT_PDF_POLICY_DENIED")
            for i, page in enumerate(doc, 1):
                text = page.get_text("text", sort=True)
                if len(text) > 100_000:
                    raise ValueError("DOCUMENT_PAGE_TEXT_TOO_LARGE")
                for line, raw_line in enumerate(text.splitlines(), 1):
                    cleaned = raw_line.strip()
                    if not cleaned:
                        continue
                    if "|" not in cleaned:
                        # No inferred values from ordinary narrative prose.
                        raise ValueError("DOCUMENT_NONCANONICAL_PDF_TEXT")
                    cells = [part.strip() for part in cleaned.split("|")]
                    rows.append(cells)
                    if len(rows) > _MAX_ROWS+1:
                        raise ValueError("DOCUMENT_ROW_COUNT_INVALID")
                    if len(rows) > 1:
                        spans.append(f"page:{i}:line:{line}")
    except (RuntimeError, OSError, TypeError) as exc:
        raise ValueError("DOCUMENT_PDF_PARSE_DENIED") from exc
    return rows, spans


def normalize_local_document(raw: bytes, *, format: str, dataset_id: str,
                             source_id: str, access_level: str,
                             consent: bool = False) -> dict[str, Any]:
    """Strict, local-only document-to-canonical mapping, no guessed numbers."""
    if (type(raw) is not bytes or not 0 < len(raw) <= _MAX_RAW
            or format not in ("PDF", "DOCX") or not _id(dataset_id)
            or not _id(source_id) or access_level not in ("PUBLIC", "PRIVATE")
            or type(consent) is not bool
            or (access_level == "PRIVATE" and not consent)):
        raise ValueError("DOCUMENT_SOURCE_POLICY_DENIED")
    rows, spans = (_safe_pdf_table(raw) if format == "PDF"
                   else _safe_docx_table(raw))
    if (not 2 <= len(rows) <= _MAX_ROWS+1
            or tuple(rows[0]) != HEADER
            or len(spans) != len(rows)-1
            or any(len(row) != 6 for row in rows)):
        raise ValueError("DOCUMENT_EXACT_CANONICAL_TABLE_REQUIRED")
    out = StringIO(newline="")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerows(rows)
    normalized = normalize_local_csv(out.getvalue().encode("utf-8"),
        dataset_id=dataset_id, source_id=source_id,
        access_level=access_level, consent=consent)
    source_hash = sha256(raw).hexdigest()
    normalized["normalized_csv_sha256"] = normalized["source_sha256"]
    normalized["source_sha256"] = source_hash
    normalized["source_type"] = "LOCAL_" + format + "_CANONICAL_TABLE"
    normalized["source_spans"] = spans
    normalized["document_parser_sandbox_verified"] = False
    for row in normalized["records"]:
        row["evidence_sha256"] = source_hash
    return normalized


def ingest_document_locally(vault: OwnerLocalGateway, principal: VerifiedPrincipal, *,
                            raw: bytes, format: str, dataset_id: str,
                            source_id: str, access_level: str,
                            allowed_roles: tuple[str, ...] = ("analyst",)) -> dict:
    """Owner-scoped document adapter for existing in-memory local gateway.

    Preserves existing gateway API; credentials and host egress policy are not
    implemented here. Ingest receipts include no document text or identifier.
    """
    if type(vault) is not OwnerLocalGateway:
        raise ValueError("DOCUMENT_GATEWAY_INVALID")
    vault._check(principal, write=True)
    vault._check_roles(allowed_roles)
    if not _id(dataset_id):
        raise ValueError("DOCUMENT_SOURCE_POLICY_DENIED")
    if dataset_id in vault._datasets:
        raise ValueError("GATEWAY_DATASET_ALREADY_REGISTERED")
    data = normalize_local_document(raw, format=format, dataset_id=dataset_id,
        source_id=source_id, access_level=access_level,
        consent=access_level == "PRIVATE")
    vault._register(dataset_id, data, allowed_roles)
    return vault._receipt(data)
