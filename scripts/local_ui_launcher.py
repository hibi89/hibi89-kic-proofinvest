"""KUODRA P177: local-host-native, opt-in Streamlit launch for Windows/Linux.

No Docker bridge or cloud deployment. This starts the checked-in application
only on 127.0.0.1; no upload, provider request, API credential, license grant
or network egress is claimed by this launcher.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
PORT = 18651
_KEEP_ENV = frozenset({
    "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "HOME",
    "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "COMSPEC",
    "LANG", "LANGUAGE", "LC_ALL", "VIRTUAL_ENV", "PYTHONUTF8",
    "PYTHONIOENCODING", "SSL_CERT_FILE", "SSL_CERT_DIR",
})


def child_environment(*, local_review: bool = False) -> dict[str, str]:
    """Explicit allowlist prevents inherited KUODRA/API secrets and opt-ins."""
    clean = {key: value for key, value in os.environ.items()
             if key.upper() in _KEEP_ENV}
    clean["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    clean["KUODRA_ENABLE_LOCAL_SOURCE_UI"] = "1" if local_review else "0"
    clean["KUODRA_ENABLE_SEC_FETCH_UI"] = "0"
    return clean


def command(port: int) -> list[str]:
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("LOCAL_PORT_INVALID")
    if not APP.is_file():
        raise ValueError("KUODRA_APP_NOT_FOUND")
    return [
        sys.executable, "-B", "-m", "streamlit", "run", str(APP),
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--server.headless=true",
        "--server.enableCORS=true",
        "--server.enableXsrfProtection=true",
        "--server.enableStaticServing=false",
        "--server.fileWatcherType=none",
        "--server.maxUploadSize=24",
        "--browser.gatherUsageStats=false",
    ]


def _port_free(port: int) -> bool:
    # Do not terminate or reuse another already running local service.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _health(port: int) -> bool:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(
            f"http://127.0.0.1:{port}/_stcore/health", timeout=1.5
        ) as response:
            if response.status != 200:
                return False
        with opener.open(f"http://127.0.0.1:{port}/", timeout=1.5) as response:
            return response.status == 200 and b"streamlit" in response.read(
                256_000).lower()
    except (OSError, TimeoutError, ValueError):
        return False


def run(*, port: int = PORT, smoke: bool = False,
        local_review: bool = False) -> dict[str, object]:
    """Run until interrupted (or check real HTTP then shut down for CI)."""
    args = command(port)
    if not _port_free(port):
        return {"status": "BLOCKED", "reason": "LOCAL_PORT_OCCUPIED",
                "actual_http_passed": False, "network_requests": 0}
    process = subprocess.Popen(
        args, cwd=APP.parent, env=child_environment(local_review=local_review),
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    started = False
    try:
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if process.poll() is not None:
                break
            if _health(port):
                started = True
                break
            time.sleep(0.25)
        if not started:
            return {"status": "BLOCKED", "reason": "LOCAL_HTTP_NOT_READY",
                    "actual_http_passed": False, "network_requests": 0}
        if smoke:
            return {
                "status": "LOCAL_HOST_HTTP_PASS_NOT_PRODUCTION",
                "address": "127.0.0.1", "port": port,
                "actual_http_passed": True,
                "source_authenticated": False,
                "source_rights_verified": False,
                "official_submission": False,
                "trade_executed": False,
                "network_requests": 0,  # Launcher itself does not call APIs.
            }
        print(f"KUODRA_LOCAL_ONLY http://127.0.0.1:{port}", flush=True)
        print("Press Ctrl+C to stop; not a Production or SEC data server.",
              flush=True)
        process.wait()
        return {"status": "LOCAL_SERVER_STOPPED",
                "actual_http_passed": True}
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=8)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Start KUODRA only on local 127.0.0.1 without API secrets")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--smoke", action="store_true",
                        help="CI: verify local HTTP then shut down")
    parser.add_argument("--enable-local-review", action="store_true",
                        help="Show explicit operator-supplied local file review")
    args = parser.parse_args(argv)
    try:
        result = run(port=args.port, smoke=args.smoke,
                     local_review=args.enable_local_review)
    except (ValueError, OSError, FileNotFoundError):
        result = {"status": "BLOCKED", "reason": "LOCAL_LAUNCH_UNAVAILABLE",
                  "actual_http_passed": False, "network_requests": 0}
    except KeyboardInterrupt:
        result = {"status": "LOCAL_SERVER_STOPPED",
                  "actual_http_passed": False}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] in (
        "LOCAL_HOST_HTTP_PASS_NOT_PRODUCTION", "LOCAL_SERVER_STOPPED"
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
