#!/usr/bin/env python3
"""Offline KIC 60-day master-progress integrity guard.

Only the JSON is manually editable.
python scripts/master_progress.py --write
python scripts/master_progress.py --check
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "docs" / "roles" / "lead"
DATA = D / "MASTER_PROGRESS.json"
VIEW = D / "MASTER_PROGRESS.md"
PLAN = D / "DAILY_CAPACITY_PLAN_20261024.md"
PHASES = ("PRELIMINARY", "AWAITING_RESULT", "FINALIST_ONLY")
STATUSES = ("DONE", "PARTIAL", "BLOCKED", "NOT_STARTED")
DATE_RE = re.compile(r"^\| (2026-\d\d-\d\d) \|.*$", re.M)
SOURCE_RE = re.compile(r"^\|\s*(\d\d/\d\d)\([월화수목금토일]\)\s*\|")


def fmt(x):
    return str(float(x)).removesuffix(".0") + "h"


def source_plan():
    result = {}
    for line in PLAN.read_text(encoding="utf-8").splitlines():
        m = SOURCE_RE.match(line)
        if not m:
            continue
        parts = [v.strip() for v in line.strip().strip("|").split("|")]
        if len(parts) != 6:
            raise ValueError("Malformed original schedule row: " + line)
        date = "2026-" + m.group(1).replace("/", "-")
        result[date] = (parts[1], float(parts[2][:-1]), float(parts[3][:-1]), parts[5])
    if len(result) != 60:
        raise ValueError("Canonical source schedule must contain exactly 60 days")
    return result


def check_data(data):
    plan = source_plan()
    rows = data.get("rows", [])
    if len(rows) != 60 or len({r["date"] for r in rows}) != 60 or [r["date"] for r in rows] != list(plan):
        raise ValueError("Date coverage/order differs from the 60-day schedule")
    counts = Counter()
    for i, row in enumerate(rows):
        day = row["date"]
        datetime.date.fromisoformat(day)
        if row["phase"] != PHASES[0 if i < 20 else 1 if i < 41 else 2]:
            raise ValueError("Wrong schedule phase: " + day)
        task, planned_base, planned_reserve, gate = plan[day]
        if (
            row["task"] != task or row["gate"] != gate
            or float(row["planned_base_h"]) != planned_base
            or float(row["planned_reserve_h"]) != planned_reserve
        ):
            raise ValueError("Canonical plan title/hour/gate mismatch: " + day)
        status, pct = row["status"], row["percent"]
        remaining = (float(row["remaining_base_h"]), float(row["remaining_reserve_h"]))
        if status not in STATUSES or type(pct) is not int or not 0 <= pct <= 100:
            raise ValueError("Invalid status/percent: " + day)
        if min(remaining) < 0 or remaining[0] > planned_base or remaining[1] > planned_reserve:
            raise ValueError("Invalid remaining hours: " + day)
        if row["actual_hours"] != "미계측" and not isinstance(row["actual_hours"], (int, float)):
            raise ValueError("Actual time must be measured or marked unmeasured: " + day)
        if status == "DONE":
            if (pct != 100 or any(remaining) or not row.get("actual_completed_date")
                or not row.get("evidence_path") or not row.get("evidence_sha")):
                raise ValueError("DONE requires completion date, evidence SHA, 100%, zero hours: " + day)
        if status in ("PARTIAL", "BLOCKED"):
            if pct in (0, 100) or not row.get("evidence_path"):
                raise ValueError("Partial or blocked without proportionate proof: " + day)
            if status == "BLOCKED" and not row.get("blocker"):
                raise ValueError("BLOCKED must explain the access dependency: " + day)
        if status == "NOT_STARTED":
            if (pct != 0 or row.get("actual_completed_date") is not None
                or remaining != (planned_base, planned_reserve) or row.get("evidence_path")):
                raise ValueError("NOT_STARTED improperly changed: " + day)
        if row.get("evidence_path"):
            target = (ROOT / row["evidence_path"]).resolve()
            if not target.is_relative_to(ROOT.resolve()) or not target.is_file():
                raise ValueError("Missing or unsafe evidence path: " + day)
        if row.get("actual_completed_date"):
            datetime.date.fromisoformat(row["actual_completed_date"])
        counts[status] += 1
    next_day = data["next_task_date"]
    rr = next((r for r in rows if r["date"] == next_day), None)
    if rr is None or rr["status"] != "NOT_STARTED" or rr["phase"] == "FINALIST_ONLY":
        raise ValueError("Next ready task must be an unstarted non-finalist day")
    for name in ("KIC_RESUME_STATE.md", "CHAT_BOOTSTRAP.md", "docs/roles/lead/LEAD_ACTIVE_WORK.md"):
        if next_day not in (ROOT / name).read_text(encoding="utf-8")[:2500]:
            raise ValueError("Current handoff pointer not synchronized: " + name)
    backup = data["backup"]
    if backup.get("type") == "USER_PRIVATE_LIBRARY":
        if len(backup.get("files", [])) != backup.get("verified_count", 0):
            raise ValueError("Library backup claims do not match uploads")
    return counts


def row_line(x):
    proof = x.get("evidence_path")
    if not proof:
        source = "—"
    else:
        source = "[근거](../../../" + proof + ")"
        if x.get("evidence_sha"):
            source += " · " + chr(96) + str(x["evidence_sha"])[:10] + chr(96)
        if x.get("ci_run"):
            n = x["ci_run"]
            source += " · [CI " + str(n) + "](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/" + str(n) + ")"
    if x["status"] == "BLOCKED":
        source += " · 차단"
    return (
        "| " + x["date"] + " | " + x["task"].replace("|", "／")
        + " | **" + x["status"] + "** | " + str(x["percent"]) + "% | "
        + (x["actual_completed_date"] or "—") + " | "
        + fmt(x["planned_base_h"]) + "+" + fmt(x["planned_reserve_h"]) + " | "
        + fmt(x["remaining_base_h"]) + "+" + fmt(x["remaining_reserve_h"]) + " | "
        + str(x["actual_hours"]) + " | " + source + " |"
    )


def render(template, data, counts):
    rows = data["rows"]
    records = {r["date"]: r for r in rows}
    dates_in_view = DATE_RE.findall(template)
    if dates_in_view != [r["date"] for r in rows]:
        raise ValueError("Master markdown missing/duplicated/reordered 60 plan dates")

    def update_row(m):
        return row_line(records[m.group(1)])

    text = DATE_RE.sub(update_row, template)
    summary_pattern = r"^> 스냅샷 .*$"
    summary = (
        "> 스냅샷 " + data["snapshot_date"] + " KST · DONE **"
        + str(counts["DONE"]) + "** / BLOCKED **" + str(counts["BLOCKED"])
        + "** / NOT_STARTED **" + str(counts["NOT_STARTED"])
        + "** / PARTIAL **" + str(counts["PARTIAL"])
        + "**. 전체 개발 완성률이 아닌 **날짜별 작업 판정**입니다."
    )
    text, n = re.subn(summary_pattern, lambda _: summary, text, flags=re.M)
    if n != 1:
        raise ValueError("Snapshot metadata missing")
    early = [r for r in rows[:41] if r["status"] != "DONE"]
    base = sum(float(r["remaining_base_h"]) for r in early)
    reserve = sum(float(r["remaining_reserve_h"]) for r in early)
    next_row = next(r for r in rows if r["date"] == data["next_task_date"])
    next_paragraph = (
        "**다음 READY: " + next_row["date"] + "** " + data["next_task"]
        + " " + str(next_row["percent"]) + "%, 기본 " + fmt(next_row["remaining_base_h"])
        + " + 예비 " + fmt(next_row["remaining_reserve_h"])
        + " = " + fmt(next_row["remaining_base_h"] + next_row["remaining_reserve_h"])
        + ". 미완료 초기 41일 일정 잔여 계획 합계 기본 **" + fmt(base)
        + "** + 예비 **" + fmt(reserve) + "** = **" + fmt(base + reserve)
        + "**(외부 접근대기 불명). 본선 19일은 결과에 따라 조건부이며 포함하지 않았습니다."
    )
    text, n = re.subn(r"^\*\*다음 READY:.*$", lambda _: next_paragraph, text, flags=re.M)
    if n != 1:
        raise ValueError("Next task metadata missing")
    blocked = [r for r in rows if r["status"] == "BLOCKED"]
    if blocked:
        blocks = []
        for r in blocked:
            blocks.append(r["date"][5:] + " " + r["task"].split(" ")[0] + " **" + str(r["percent"]) + "%**"
                + "(접근 후 기본" + fmt(r["remaining_base_h"]) + "+예비" + fmt(r["remaining_reserve_h"]) + ")")
        block_text = "**차단:** " + ", ".join(blocks) + ". 완료 처리 금지."
    else:
        block_text = "**차단:** 없음. 신규 외부 접근 이슈 발생 시 JSON과 영수증 갱신."
    text, n = re.subn(r"^\*\*차단:.*$", lambda _: block_text, text, flags=re.M)
    if n != 1:
        raise ValueError("Blocked work metadata missing")
    back = data["backup"]
    back_text = (
        "**비공개 산출물:** " + back["type"] + " / "
        + back["folder"] + " / " + str(back["verified_count"])
        + "개 저장 성공. 공개 GitHub 비게시. "
        + ("공식 제출 완료." if back.get("officially_submitted") else "공식 DAKER 제출 완료 아님.")
    )
    text, n = re.subn(r"^\*\*비공개 산출물:.*$", lambda _: back_text, text, flags=re.M)
    if n != 1:
        raise ValueError("Private artifact metadata missing")
    return text


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--write", action="store_true")
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    if args.write == args.check:
        p.error("Select exactly one of --write or --check")
    data = json.loads(DATA.read_text(encoding="utf-8"))
    counts = check_data(data)
    current = VIEW.read_text(encoding="utf-8")
    generated = render(current, data, counts)
    if args.write:
        VIEW.write_text(generated, encoding="utf-8")
    elif current != generated:
        raise SystemExit("MASTER_PROGRESS.md drift detected. Run: python scripts/master_progress.py --write")
    print("KIC 60-day progress valid: " + ", ".join(k + "=" + str(counts[k]) for k in STATUSES))


if __name__ == "__main__":
    main()
