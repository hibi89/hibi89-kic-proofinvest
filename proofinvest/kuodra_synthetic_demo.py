"""Deterministic, owner-local KUODRA synthetic end-to-end backend demonstrator.

Runs a PUBLIC CSV + PRIVATE SQLite -> canonical -> ACL -> group/time ML ->
restricted human-review HTML/JSON workflow. A second synthetic private DOCX
and public CSV exercise document extraction and cross-sectional FDR. It NEVER
reads real user documents and has no network/provider calls. Demo principals
are intentionally NOT real authentication. Do not use this as a confidential
institution data processor or distribute it as a production service.

Usage: python -m proofinvest.kuodra_synthetic_demo --output-dir ./demo-output
       python -m proofinvest.kuodra_synthetic_demo --verify-dir ./demo-output
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO, StringIO
import json
from pathlib import Path
import sqlite3
from typing import Any

from .kuodra_private_gateway import OwnerLocalGateway, VerifiedPrincipal
from .kuodra_document_ingest import ingest_document_locally
from .kuodra_hybrid import analyze_local_hybrid
from .kuodra_alias_hybrid import _prepare_owner_alias_view
from .kuodra_review_report import build_owner_group_review, render_restricted_review_html

_HEADER = ("entity_id", "metric_id", "observation_at", "available_at", "value", "unit")
_AS_OF = "2026-01-01T00:00:00Z"
_OWNER = VerifiedPrincipal("syntheticOwner", "syntheticInstitution", ("owner",), True)
_ANALYST = VerifiedPrincipal("syntheticAnalyst", "syntheticInstitution", ("analyst",), True)
_MAX_OUTPUT_SIZE = 250_000
_OUTPUT_FILES = ("review.json", "review.html", "manifest.json")


def _csv(rows: list[tuple[str, ...]]) -> bytes:
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(_HEADER)
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def _table_rows(*, issuers: int = 10, days: int = 62, metric: str) -> list[tuple[str, ...]]:
    """Exactly reproducible, explicitly fictional issuer series."""
    rows = []
    for j in range(issuers):
        for i in range(days):
            ts = (datetime(2025, 1, 1, tzinfo=timezone.utc)
                  + timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%SZ")
            if metric == "factor":
                value = str(round(i + j * 0.4, 3))
                unit = "count"
            elif metric == "outcome":
                value = str(i * 3 + j * 2 + 4)
                unit = "usd"
            else:
                raise ValueError("DEMO_METRIC_DENIED")
            rows.append((f"fictitiousIssuer{j}", metric, ts, ts, value, unit))
    return rows


def _sqlite_bytes(rows: list[tuple[str, ...]]) -> bytes:
    db = sqlite3.connect(":memory:")
    try:
        db.execute("CREATE TABLE measurements (entity_id TEXT,metric_id TEXT,"
                   "observation_at TEXT,available_at TEXT,value TEXT,unit TEXT)")
        db.executemany("INSERT INTO measurements VALUES (?,?,?,?,?,?)", rows)
        return db.serialize()
    finally:
        db.close()


def _synthetic_docx() -> bytes:
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("SYNTHETIC_DOCX_DEPENDENCY_MISSING") from exc
    doc = Document()
    table = doc.add_table(rows=1, cols=6)
    for cell, text in zip(table.rows[0].cells, _HEADER):
        cell.text = text
    for i in range(45):
        row = table.add_row()
        fields = (f"fictitiousIssuer{i}", "internalSignal", _AS_OF,
                  _AS_OF, str(i * 3 + 5), "count")
        for cell, text in zip(row.cells, fields):
            cell.text = text
    output = BytesIO()
    doc.save(output)
    return output.getvalue()


def _safe_stats(source: dict[str, Any]) -> dict[str, Any]:
    """Only allow aggregated analysis evidence, never copy issuer/source names."""
    analysis = source["analysis"]
    permitted = ("schema", "status", "multiple_testing_method", "pairs_evaluated",
                 "hypotheses_planned", "eligible_entities", "independence_assumption",
                 "insights", "guard", "model_trained")
    return {key: analysis[key] for key in permitted if key in analysis}


def run_synthetic_demo() -> tuple[dict[str, Any], str]:
    """No input files/paths. Only synthetic data enters the in-memory vault."""
    vault = OwnerLocalGateway("syntheticInstitution")
    pub = _csv(_table_rows(metric="factor"))
    private_db = _sqlite_bytes(_table_rows(metric="outcome"))
    vault.ingest_csv(_OWNER, raw=pub, dataset_id="fictionalPublic",
                     source_id="fictionalCSV", access_level="PUBLIC")
    vault.ingest_sqlite(_OWNER, raw_db=private_db, table="measurements",
                        dataset_id="fictionalPrivate", source_id="fictionalSQLite",
                        access_level="PRIVATE")
    first_view, _ = _prepare_owner_alias_view(
        vault, _OWNER, public_dataset_id="fictionalPublic",
        private_dataset_id="fictionalPrivate",
        public_sha256=vault._datasets["fictionalPublic"]["source_sha256"],
        private_sha256=vault._datasets["fictionalPrivate"]["source_sha256"],
        aliases={r["entity_id"]: r["entity_id"]
                 for r in vault._datasets["fictionalPublic"]["records"]},
        as_of=_AS_OF)
    restricted = build_owner_group_review(
        first_view, _ANALYST, private_dataset_id="fictionalPrivate",
        public_dataset_id="fictionalPublic", target_metric="private.outcome",
        feature_metrics=("public.factor",), as_of=_AS_OF)
    if (restricted["decision"] != "HOLD"
            or restricted["analysis"].get("status")
               != "EXPLORATORY_GROUP_TIME_HOLDOUT_MEASURED"
            or restricted["public_export_allowed"] is not False):
        raise RuntimeError("DEMO_GROUP_TIME_EVIDENCE_NOT_MET")
    html = render_restricted_review_html(restricted)

    # A distinct one-day document/table path, kept restricted and never exported.
    public_doc_rows = []
    for i in range(45):
        public_doc_rows.append((f"fictitiousIssuer{i}", "publicSignal",
                                _AS_OF, _AS_OF, str(i + 1), "count"))
    vault.ingest_csv(_OWNER, raw=_csv(public_doc_rows),
                     dataset_id="fictionalDocPublic", source_id="fictionalDocCSV",
                     access_level="PUBLIC")
    doc_raw = _synthetic_docx()
    ingest_document_locally(vault, _OWNER, raw=doc_raw, format="DOCX",
                            dataset_id="fictionalDocPrivate",
                            source_id="fictionalDocx", access_level="PRIVATE")
    doc_view, _ = _prepare_owner_alias_view(
        vault, _OWNER, public_dataset_id="fictionalDocPublic",
        private_dataset_id="fictionalDocPrivate",
        public_sha256=vault._datasets["fictionalDocPublic"]["source_sha256"],
        private_sha256=vault._datasets["fictionalDocPrivate"]["source_sha256"],
        aliases={r["entity_id"]: r["entity_id"]
                 for r in vault._datasets["fictionalDocPublic"]["records"]},
        as_of="2026-02-01T00:00:00Z")
    doc_analysis = analyze_local_hybrid(
        doc_view, _ANALYST, public_dataset_id="fictionalDocPublic",
        private_dataset_id="fictionalDocPrivate", mode="cross_section",
        as_of="2026-02-01T00:00:00Z", observation_at=_AS_OF,
        metrics=("public.publicSignal", "private.internalSignal"))
    if (doc_analysis.get("guard") != "HOLD"
            or doc_analysis["analysis"].get("status")
               != "EXPLORATORY_INDEPENDENCE_UNVERIFIED"):
        raise RuntimeError("DEMO_DOC_STATISTICS_NOT_MET")
    result = {
        "schema": "kuodra.synthetic-backend-demo.v1",
        "synthetic_only": True,
        "institution_data_used": False,
        "rights_or_publisher_verified": False,
        "host_iam_verified": False,
        "os_egress_deny_verified": False,
        "production_ready": False,
        "guard": "HOLD",
        "workflow": "PUBLIC_CSV_PRIVATE_SQLITE_GROUP_TIME_ML_AND_DOCX_FDR",
        "group_time_review": restricted,
        "document_statistical_review": _safe_stats(doc_analysis),
    }
    return result, html


def _canonical(data: dict) -> bytes:
    return (json.dumps(data, ensure_ascii=True, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _output_path(directory: Path, name: str) -> Path:
    candidate = directory / name
    if candidate.is_symlink() or (candidate.exists() and not candidate.is_file()):
        raise ValueError("DEMO_OUTPUT_TARGET_DENIED")
    return candidate


def write_synthetic_demo(directory: Path) -> dict:
    """Writes synthetic-only output, refusing to overwrite or follow symlinks."""
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("DEMO_OUTPUT_DIRECTORY_NOT_EXISTING_LOCAL_DIRECTORY")
    paths = [_output_path(directory, name) for name in _OUTPUT_FILES]
    if any(path.exists() for path in paths):
        raise FileExistsError("DEMO_NO_OVERWRITE")
    report, html = run_synthetic_demo()
    bodies = {"review.json": _canonical(report),
              "review.html": html.encode("utf-8")}
    manifest = {
        "schema": "kuodra.synthetic-demo-manifest.v1",
        "synthetic_only": True, "guard": "HOLD", "network_requests": 0,
        "files": {name: {"sha256": sha256(body).hexdigest(), "size": len(body)}
                  for name, body in bodies.items()},
    }
    bodies["manifest.json"] = _canonical(manifest)
    if any(len(body) > _MAX_OUTPUT_SIZE for body in bodies.values()):
        raise ValueError("DEMO_OUTPUT_TOO_LARGE")
    # exclusive create avoids accidentally replacing an existing file.
    created = []
    try:
        for path in paths:
            with path.open("xb") as stream:
                created.append(path)
                stream.write(bodies[path.name])
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return manifest


def verify_synthetic_demo(directory: Path) -> dict:
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("DEMO_VERIFY_DIRECTORY_DENIED")
    paths = [_output_path(directory, name) for name in _OUTPUT_FILES]
    if any(not p.is_file() or p.stat().st_size > _MAX_OUTPUT_SIZE for p in paths):
        raise ValueError("DEMO_VERIFY_FILE_INVALID")
    manifest = json.loads(paths[-1].read_bytes())
    if (type(manifest) is not dict
            or manifest.get("schema") != "kuodra.synthetic-demo-manifest.v1"
            or manifest.get("synthetic_only") is not True
            or manifest.get("guard") != "HOLD"
            or manifest.get("network_requests") != 0
            or set(manifest.get("files", {})) != set(_OUTPUT_FILES[:2])):
        raise ValueError("DEMO_VERIFY_MANIFEST_INVALID")
    for path in paths[:2]:
        metadata = manifest["files"].get(path.name)
        payload = path.read_bytes()
        if (type(metadata) is not dict or type(metadata.get("sha256")) is not str
                or type(metadata.get("size")) is not int
                or len(payload) != metadata["size"]
                or sha256(payload).hexdigest() != metadata["sha256"]):
            raise ValueError("DEMO_VERIFY_CHECKSUM_MISMATCH")
    report = json.loads(paths[0].read_bytes())
    if (report.get("schema") != "kuodra.synthetic-backend-demo.v1"
            or report.get("synthetic_only") is not True
            or report.get("guard") != "HOLD"
            or report.get("production_ready") is not False
            or report.get("institution_data_used") is not False
            or report.get("os_egress_deny_verified") is not False):
        raise ValueError("DEMO_VERIFY_REPORT_INVALID")
    # Re-validate signed local receipt, not just manifest hashes. No browser/network.
    if paths[1].read_text("utf-8") != render_restricted_review_html(report["group_time_review"]):
        raise ValueError("DEMO_VERIFY_HTML_CHANGED")
    return {"status": "SYNTHETIC_ONLY_RECEIPT_VERIFIED", "guard": "HOLD",
            "network_requests": 0, "production_ready": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline KUODRA synthetic backend smoke run")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output-dir", type=Path)
    group.add_argument("--verify-dir", type=Path)
    args = parser.parse_args(argv)
    if args.output_dir is not None:
        result = write_synthetic_demo(args.output_dir)
        print(json.dumps({"status": "SYNTHETIC_ONLY_DEMO_WRITTEN", "guard": "HOLD",
                          "manifest_sha256": sha256(_canonical(result)).hexdigest()},
                         sort_keys=True))
    else:
        print(json.dumps(verify_synthetic_demo(args.verify_dir), sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
