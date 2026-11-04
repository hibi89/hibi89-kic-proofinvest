"""Offline one-command local original SEC+stock+NDX+peer evidence generator.

No network, vendor use, SEC 403 retry, live LLM, trade or approval. Existing
P167 strict replay engine validates sources; this CLI provides a bounded,
fail-closed file path entrypoint and creates ONLY new redacted evidence files.
Neither source bytes nor private paths are printed or placed in the reports.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any

from proofinvest.market_provider_alpha_vantage import _MAX_BODY as STOCK_MAX
from proofinvest.market_provider_alpha_vantage_index import _MAX_RESPONSE as NDX_MAX
from proofinvest.ticker_sec_financial_bridge import _LIMITS as SEC_LIMITS
from proofinvest.ticker_offline_review_builder import build_offline_initial_review
from proofinvest.ticker_review_packet import inspect_review_packet_bytes
from proofinvest.ticker_source_clearance_packet import inspect_source_clearance_packet

_MARKET_MAX = 131072
_PEERS_MAX = 65536
_REVIEW_NAME = "kuodra-offline-a-b-c-review-UNVERIFIED.json"
_RIGHTS_NAME = "kuodra-source-rights-GAPS-UNVERIFIED.json"


def _read_original(value: str, maximum: int) -> bytes:
    """Read an explicitly named regular file without following symlinks.

    Refuse directories, pipes, device files, giant files and changed identities.
    Windows does not expose O_NOFOLLOW on every Python build, but lstat and
    fstat checks still prevent accidentally treating an intentional symlink as
    a source. No file names or input contents are printed on failure.
    """
    path = Path(value)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= maximum:
        raise ValueError("ORIGINAL_FILE_TYPE_OR_SIZE_INVALID")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        after = os.fstat(fd)
        if (not stat.S_ISREG(after.st_mode) or after.st_dev != before.st_dev
                or after.st_ino != before.st_ino
                or not 0 < after.st_size <= maximum):
            raise ValueError("ORIGINAL_FILE_CHANGED")
        with os.fdopen(fd, "rb", closefd=False) as fp:
            raw = fp.read(maximum + 1)
        if len(raw) != after.st_size or not 0 < len(raw) <= maximum:
            raise ValueError("ORIGINAL_SOURCE_BYTES_CHANGED")
        return raw
    finally:
        os.close(fd)


def _write_one(path: Path, raw: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=False) as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
    finally:
        os.close(fd)


def generate(*, ticker: str, as_of: str, originals: dict[str, str],
             stock_path: str, index_path: str, output_dir: str,
             market_path: str | None = None,
             industry_path: str | None = None) -> dict[str, Any]:
    """Recompute exact originals, then write two strictly redacted new files.

    The output directory must not yet exist; rollback deletes only files this
    run itself created. Never overwrite a user's original or report.
    """
    if type(originals) is not dict or set(originals) != set(SEC_LIMITS):
        raise ValueError("ORIGINAL_SOURCE_SET_INVALID")
    sources = {
        role: _read_original(originals[role], ceiling)
        for role, ceiling in SEC_LIMITS.items()
    }
    stock = _read_original(stock_path, STOCK_MAX)
    index = _read_original(index_path, NDX_MAX)
    market = _read_original(market_path, _MARKET_MAX) if market_path else None
    industry = _read_original(industry_path, _PEERS_MAX) if industry_path else None
    built = build_offline_initial_review(
        ticker=ticker, as_of=as_of, sources=sources,
        stock_raw=stock, index_raw=index,
        market_json=market, industry_json=industry,
    )
    if (built.get("status") != "LOCAL_INITIAL_REVIEW_READY_UNVERIFIED"
            or built.get("source_authenticated") is not False
            or built.get("source_rights_verified") is not False
            or built.get("external_sharing_allowed") is not False
            or built.get("local_replay_verified") is not True
            or built.get("market_math_recomputed") is not True
            or built.get("guard_policy_preview") != "HOLD"
            or built.get("network_requests") != 0
            or built.get("paid_requests") != 0):
        raise ValueError("LOCAL_ORIGINALS_INDEPENDENT_REPLAY_BLOCKED")
    review, rights = built["review_packet"], built["source_clearance_report"]
    if (type(review) is not bytes or type(rights) is not bytes
            or inspect_review_packet_bytes(review).get("status")
            != "LOCAL_PACKET_INTERNAL_INTEGRITY_PASS_UNVERIFIED"
            or inspect_source_clearance_packet(rights, review_packet=review).get(
                "status") != "MATCHED_REPORT_EXTERNAL_CLEARANCES_STILL_PENDING"):
        raise ValueError("LOCAL_EVIDENCE_INTEGRITY_FAILED")
    target = Path(output_dir)
    if (not target.name or target.is_symlink()
            or not target.parent.is_dir() or target.parent.is_symlink()
            or target.exists()):
        raise ValueError("OUTPUT_DIRECTORY_MUST_BE_NEW")
    os.mkdir(target, 0o700)
    created: list[Path] = []
    try:
        for name, raw in ((_REVIEW_NAME, review), (_RIGHTS_NAME, rights)):
            file = target / name
            created.append(file)  # cleanup even if write or fsync fails
            _write_one(file, raw)
    except (OSError, ValueError):
        for path in created:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        try:
            target.rmdir()
        except OSError:
            pass
        raise
    return {
        "schema": "kuodra.one-ticker-local-originals-cli.v1",
        "status": "LOCAL_ORIGINALS_REPLAYED_UNVERIFIED",
        "ticker": ticker, "as_of": as_of,
        "review_filename": _REVIEW_NAME,
        "review_sha256": sha256(review).hexdigest(),
        "rights_filename": _RIGHTS_NAME,
        "rights_sha256": sha256(rights).hexdigest(),
        "source_authenticated": False,
        "source_rights_verified": False,
        "external_sharing_allowed": False,
        "guard_policy_preview": "HOLD",
        "guard_executed": False,
        "trade_executed": False,
        "official_contest_submission": False,
        "network_requests": 0,
        "paid_requests": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Local SEC/stock/NDX review; ORIGINAL AUTHENTICITY AND RIGHTS UNVERIFIED")
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--as-of", required=True)
    for role in SEC_LIMITS:
        parser.add_argument("--" + role.replace("_", "-"), required=True)
    parser.add_argument("--stock-daily", required=True)
    parser.add_argument("--ndx-daily", required=True)
    parser.add_argument("--market-json")
    parser.add_argument("--industry-json")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    try:
        report = generate(
            ticker=args.ticker, as_of=args.as_of,
            originals={role: getattr(args, role) for role in SEC_LIMITS},
            stock_path=args.stock_daily, index_path=args.ndx_daily,
            output_dir=args.output_dir,
            market_path=args.market_json, industry_path=args.industry_json,
        )
    except (ValueError, OSError, TypeError, KeyError, OverflowError):
        print(json.dumps({
            "status": "BLOCKED", "reason_code": "LOCAL_SOURCE_OR_OUTPUT_INVALID",
            "source_authenticated": False, "source_rights_verified": False,
            "external_sharing_allowed": False, "guard_policy_preview": "HOLD",
            "network_requests": 0, "paid_requests": 0,
        }, sort_keys=True))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
