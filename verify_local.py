"""Offline DL verification: python verify_local.py [--full].

Does not fetch SEC, install packages, modify user data, or save under the repo.
Detailed PASS/FAIL/SKIP logs and JSON are written to a fresh temp folder.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

CIK = "0000320193"


def execute(argv: list[str], *, root: Path, log: Path, timeout: int = 300) -> dict:
    try:
        with log.open("w", encoding="utf-8", errors="replace") as handle:
            process = subprocess.run(
                argv, cwd=root, stdin=subprocess.DEVNULL,
                stdout=handle, stderr=subprocess.STDOUT,
                timeout=timeout, check=False,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
        return {"status": "PASS" if process.returncode == 0 else "FAIL",
                "exit_code": process.returncode, "log": str(log)}
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.write_text("EXECUTION_ERROR: " + type(exc).__name__, encoding="utf-8")
        return {"status": "FAIL", "error": type(exc).__name__, "log": str(log)}


def git_info(root: Path) -> dict:
    result = {"head": None, "branch": None, "tracked_changes": None}
    for key, argv in (
        ("head", ["git", "rev-parse", "HEAD"]),
        ("branch", ["git", "branch", "--show-current"]),
        ("tracked_changes", ["git", "status", "--porcelain", "--untracked-files=no"]),
    ):
        try:
            proc = subprocess.run(argv, cwd=root, capture_output=True, text=True,
                                  stdin=subprocess.DEVNULL, timeout=5, check=False)
            if proc.returncode == 0:
                result[key] = (bool(proc.stdout.strip()) if key == "tracked_changes"
                               else proc.stdout.strip())
        except (OSError, subprocess.TimeoutExpired):
            pass
    return result


def smoke(root: Path, log: Path) -> dict:
    """Exercise real CLI ingest → read-only list → amendment review in a temp DB."""
    fixture = root / "disclosure_lightning/fixtures/sec_submissions_synthetic.json"
    if not fixture.is_file():
        return {"status": "FAIL", "error": "MISSING_SYNTHETIC_FIXTURE", "log": str(log)}
    try:
        with tempfile.TemporaryDirectory(prefix="dl-offline-smoke-") as temp:
            db = Path(temp) / "test.sqlite3"
            common = [sys.executable, "-B", "-m", "disclosure_lightning",
                      "--cik", CIK, "--as-of", "2026-10-27", "--db", str(db)]
            steps = [
                ("ingest", common + ["--input-json", str(fixture),
                                     "--collected-at", "2026-10-27T00:00:00Z"],
                 "SAVED", 3),
                ("list", common + ["--list"], "READ_ONLY", 3),
                ("amendments", [sys.executable, "-B", "-m", "disclosure_lightning.history",
                                "--db", str(db), "--cik", CIK, "--as-of",
                                "2026-10-27", "--review-amendments"],
                 "READ_ONLY_UNVERIFIED_AMENDMENT_REVIEW", None),
            ]
            with log.open("w", encoding="utf-8") as handle:
                for name, argv, status, count in steps:
                    proc = subprocess.run(
                        argv, cwd=root, capture_output=True, text=True,
                        stdin=subprocess.DEVNULL, timeout=30, check=False,
                        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                    )
                    handle.write("STEP " + name + " exit=" + str(proc.returncode) + "\n")
                    handle.write((proc.stdout + proc.stderr)[:12000] + "\n")
                    if proc.returncode != 0:
                        return {"status": "FAIL", "step": name, "log": str(log)}
                    result = json.loads(proc.stdout)
                    if result.get("status") != status:
                        return {"status": "FAIL", "step": name,
                                "error": "UNEXPECTED_STATUS", "log": str(log)}
                    if name == "ingest" and result.get("new_filings") != count:
                        return {"status": "FAIL", "step": name,
                                "error": "BAD_INGEST_COUNT", "log": str(log)}
                    if name == "list" and len(result.get("filings", [])) != count:
                        return {"status": "FAIL", "step": name,
                                "error": "BAD_LIST_COUNT", "log": str(log)}
            # P11 integration: real CLI calls against a disposable historical
            # SEC-shaped synthetic manifest and continuation, never a customer DB.
            import hashlib
            history_db = Path(temp) / "history.sqlite3"
            history_dir = Path(temp) / "history-pages"
            history_dir.mkdir()
            basename = "CIK0000320193-submissions-001.json"
            manifest = {
                "cik": 320193, "name": "SYNTHETIC P11 HISTORY",
                "filings": {
                    "recent": {
                        "accessionNumber": [], "form": [],
                        "filingDate": [], "primaryDocument": [],
                    },
                    "files": [{
                        "name": basename, "filingCount": 1,
                        "filingFrom": "2014-01-01",
                        "filingTo": "2014-12-31",
                    }],
                },
            }
            raw_manifest = json.dumps(manifest, sort_keys=True).encode("utf-8")
            manifest_path = Path(temp) / "base-submissions.json"
            manifest_path.write_bytes(raw_manifest)
            (history_dir / basename).write_bytes(json.dumps({
                "accessionNumber": ["0000320193-14-000001"],
                "form": ["10-K"], "filingDate": ["2014-09-15"],
                "primaryDocument": ["synthetic-history.htm"],
                "acceptanceDateTime": ["2014-09-15T18:30:00Z"],
            }).encode("utf-8"))
            historical_base = [
                sys.executable, "-B", "-m", "disclosure_lightning",
                "--db", str(history_db), "--cik", CIK,
                "--as-of", "2026-10-27",
                "--input-json", str(manifest_path),
                "--collected-at", "2026-10-27T00:00:00Z",
            ]
            historical_import = [
                sys.executable, "-B", "-m", "disclosure_lightning.history",
                "--db", str(history_db), "--cik", CIK,
                "--manifest-sha256", hashlib.sha256(raw_manifest).hexdigest(),
                "--batch-dir", str(history_dir),
                "--as-of", "2026-10-27",
                "--collected-at", "2026-10-27T00:05:00Z",
            ]
            for label, argv, expected, added in (
                ("history-base", historical_base, "SAVED", 0),
                ("history-batch", historical_import, "SAVED_BATCH", 1),
                ("history-replay", historical_import, "REUSED_BATCH", 0),
            ):
                proc = subprocess.run(
                    argv, cwd=root, capture_output=True, text=True,
                    stdin=subprocess.DEVNULL, timeout=30, check=False,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                )
                with log.open("a", encoding="utf-8") as handle:
                    handle.write("STEP " + label + " exit=" +
                                 str(proc.returncode) + "\n")
                    handle.write((proc.stdout + proc.stderr)[:12000] + "\n")
                if proc.returncode != 0:
                    return {"status": "FAIL", "step": label, "log": str(log)}
                found = json.loads(proc.stdout)
                if (found.get("status") != expected or
                        found.get("new_filings") != added):
                    return {"status": "FAIL", "step": label,
                            "error": "UNEXPECTED_RESULT", "log": str(log)}
                if label != "history-base" and (
                        found.get("selected_batch_missing_manifest_pages") != []
                        or found.get("selected_batch_covers_eligible_manifest") is not True
                        or found.get("issuer_history_authenticity_verified") is not False):
                    return {"status": "FAIL", "step": label,
                            "error": "UNEXPECTED_HISTORY_COMPLETENESS_FLAGS",
                            "log": str(log)}
            return {"status": "PASS", "steps": len(steps) + 3,
                    "log": str(log)}
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        return {"status": "FAIL", "error": type(exc).__name__, "log": str(log)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local offline DL verifier")
    parser.add_argument("--full", action="store_true",
                        help="Run all repository unittest modules in addition to DL checks")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parent
    log_dir = Path(tempfile.mkdtemp(prefix="dl-verify-"))
    identity = git_info(root)
    results: dict[str, dict] = {}
    files = [root / "disclosure_lightning" / name
             for name in ("core.py", "history.py", "originals.py", "extract.py")]
    files.append(root / "verify_local.py")
    try:
        for path in files:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        results["syntax"] = {"status": "PASS", "files": len(files)}
    except (OSError, SyntaxError, UnicodeError) as exc:
        results["syntax"] = {"status": "FAIL", "error": type(exc).__name__}
    if results["syntax"]["status"] == "PASS":
        results["core_tests"] = execute(
            [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests",
             "-p", "test_disclosure_lightning*.py", "-v"],
            root=root, log=log_dir / "core_tests.log", timeout=180)
        results["offline_cli_smoke"] = smoke(root, log_dir / "offline_cli_smoke.log")
        results["full_tests"] = (execute(
            [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"],
            root=root, log=log_dir / "full_tests.log", timeout=600)
            if args.full else {"status": "SKIP", "reason": "CORE_MODE"})
    else:
        for name in ("core_tests", "offline_cli_smoke", "full_tests"):
            results[name] = {"status": "SKIP", "reason": "SYNTAX_ERROR"}
    results["git_identity"] = {"status": "PASS" if identity["head"] else "FAIL",
                               "reason": None if identity["head"] else "NO_GIT_CHECKOUT"}
    passed = not any(r["status"] == "FAIL" for r in results.values())
    if args.full and results["full_tests"]["status"] != "PASS":
        passed = False
    summary = {
        "schema": "dl-offline-verifier.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "git": identity,
        "mode": "FULL" if args.full else "CORE",
        "network_requests_by_verifier": 0,
        "child_test_network_calls_instrumented": False,
        "customer_data_intentionally_accessed_by_verifier": False,
        "results": results,
        "overall": "PASS" if passed else "FAIL",
    }
    destination = log_dir / "summary.json"
    destination.write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                           encoding="utf-8")
    print(json.dumps({
        "overall": summary["overall"], "git": identity,
        "results": {key: item["status"] for key, item in results.items()},
        "summary": str(destination),
    }, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
