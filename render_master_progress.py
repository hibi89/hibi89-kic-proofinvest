"""Compatibility facade. One canonical 60-day ledger and generated view.
Canonical: docs/roles/lead/MASTER_PROGRESS.json
"""
import subprocess
import sys
from pathlib import Path

if __name__=="__main__":
    root=Path(__file__).resolve().parent
    raise SystemExit(subprocess.call(
        [sys.executable,str(root/"scripts/master_progress.py"),*sys.argv[1:]],
        cwd=root))
