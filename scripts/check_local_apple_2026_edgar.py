"""P237 operator-only Apple FY2026 SEC HTML offline inspection, no SEC GET."""
from __future__ import annotations

import argparse
import json

from proofinvest.apple_2026_local_edgar_replay import (
    verify_operator_apple_2026_edgar_html,
)
from scripts.local_originals_review_cli import _read_original

MAX_SOURCE = 1650003


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="OFFLINE verify Apple FY2026 local 10-K iXBRL; NOT SEC-origin authentication"
    )
    parser.add_argument("--file", required=True, help="Local aapl-20260926.htm file")
    args = parser.parse_args(argv)
    try:
        source = _read_original(args.file, MAX_SOURCE)
        name = __import__("pathlib").Path(args.file).name
        result = verify_operator_apple_2026_edgar_html(source, filename=name)
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        result = {
            "schema": "kuodra.p237-offline-aapl-2026-sec-filing-ixbrl.v1",
            "status": "BLOCKED", "reason_code": "LOCAL_FILE_OPEN_OR_VERIFY_BLOCKED",
            "sec_edgar_original_byte_identical_authenticated": False,
            "source_commercial_or_ai_rights_verified": False,
            "licensed_stock_ndx_peer_data": False,
            "guard_policy_preview": "HOLD", "trades": 0,
            "sec_http_requests": 0,
        }
    # Only fixed metric labels/digests; never echo raw HTML, local paths or keys.
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0 if result["status"] == "LOCAL_SEC_2026_HTML_6_GAAP_FACTS_MATCH_UNAUTHENTICATED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
