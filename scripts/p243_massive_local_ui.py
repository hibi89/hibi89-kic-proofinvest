"""P243: opt-in localhost Massive Basic session, masked key and no persistence.

This script DOES NOT call Massive or SEC. The UI separately requires a
per-ticker explicit click after local SEC evidence replay. Personal research
only; not an authorization for public demos, commercial/AI redistribution.
Run: python -m scripts.p243_massive_local_ui
"""
from __future__ import annotations

import getpass
import os
from pathlib import Path
import re
import subprocess
import sys

_CONFIRM = "ENABLE MASSIVE PERSONAL RESEARCH"
_KEY = re.compile(r"[A-Za-z0-9_-]{8,128}\Z", re.ASCII)


def main() -> int:
    # Never allow a CI/noninteractive/background runner to start network UI.
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("BLOCKED: INTERACTIVE_LOCAL_TERMINAL_REQUIRED")
        return 2
    print("Local 127.0.0.1 only. Massive free Individual account is NOT")
    print("commercial, redistributable or public judge-display permission.")
    print("No provider request occurs until a separate explicit UI click.")
    if input("Type ENABLE MASSIVE PERSONAL RESEARCH to proceed: ").strip() != _CONFIRM:
        print("BLOCKED: OWNER_CONFIRMATION_REQUIRED")
        return 2
    key = getpass.getpass("Massive API Key (hidden; not stored): ")
    if _KEY.fullmatch(key) is None:
        print("BLOCKED: INVALID_API_KEY_SHAPE")
        return 2
    project = Path(__file__).resolve().parent.parent
    if not (project / "streamlit_app.py").is_file():
        print("BLOCKED: APP_SOURCE_MISSING")
        return 2
    env = os.environ.copy()
    # No SEC/old Alpha Vantage provider enables are set by this launcher.
    env.update({
        "MASSIVE_API_KEY": key,
        "KUODRA_ENABLE_LOCAL_SOURCE_UI": "1",
        "KUODRA_ENABLE_MASSIVE_PAIR": "1",
        "KUODRA_MASSIVE_PERSONAL_RESEARCH_APPROVED": "1",
    })
    key = None
    cmd = [sys.executable, "-m", "streamlit", "run", "streamlit_app.py",
           "--server.address", "127.0.0.1", "--server.port", "8765",
           "--browser.gatherUsageStats", "false"]
    try:
        return subprocess.run(cmd, cwd=project, env=env, check=False).returncode
    except (OSError, ValueError):
        print("BLOCKED: LOCAL_STREAMLIT_LAUNCH_FAILED")
        return 2
    finally:
        env.pop("MASSIVE_API_KEY", None)


if __name__ == "__main__":
    raise SystemExit(main())
