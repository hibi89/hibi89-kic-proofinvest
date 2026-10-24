"""Deterministic full-schedule dashboard. Standard library only.
Usage: python render_master_progress.py --check|--write
The project JSON is the ONLY mutable status source; Markdown is generated.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / ("data/paypal_daily_progress.json" if
    (ROOT / "data/paypal_daily_progress.json").is_file() else "data/master_progress.json")
OUTPUT = ROOT / "MASTER_PROGRESS.md"
STATES = {"DONE", "PARTIAL", "BLOCKED", "NOT_STARTED"}

def clean(value):
    return str(value).replace("|", "/").replace("\n", " ").replace("\r", " ").strip()

def number(value):
    return str(int(value)) if float(value).is_integer() else format(value, "g")

def render(doc):
    days = doc["days"]
    if doc.get("expected_days") != len(days):
        raise ValueError("Whole project schedule must have exactly expected_days")
    if len({d["day_id"] for d in days}) != len(days):
        raise ValueError("Duplicate day IDs")
    if len({d["scheduled_date_kst"] for d in days}) != len(days):
        raise ValueError("Duplicate calendar dates")
    dates = [d["scheduled_date_kst"] for d in days]
    if dates != sorted(dates):
        raise ValueError("Plan dates not sorted")
    from datetime import date, timedelta
    for index in range(1, len(dates)):
        if date.fromisoformat(dates[index]) - date.fromisoformat(dates[index - 1]) != timedelta(days=1):
            raise ValueError("Missing date in full plan")
    if doc["active_day_id"] not in {d["day_id"] for d in days}:
        raise ValueError("Missing active day")
    counts = {s: 0 for s in STATES}
    rows, outstanding = [], []
    for d in days:
        state = d["progress_state"]
        pct = d["percent_complete"]
        if state not in STATES or not isinstance(pct, int) or not 0 <= pct <= 100:
            raise ValueError("Invalid progress state or percentage")
        if (state == "DONE") != (pct == 100) or (state == "NOT_STARTED" and pct != 0):
            raise ValueError("Status contradicts percent")
        for field in ("estimated_total_hours", "safe_total_hours",
                      "estimated_remaining_hours", "safe_remaining_hours"):
            if not isinstance(d[field], (int, float)) or d[field] < 0:
                raise ValueError("Missing or negative hour field")
        if d["estimated_remaining_hours"] > d["estimated_total_hours"] or d["safe_remaining_hours"] > d["safe_total_hours"]:
            raise ValueError("Remaining hours exceed original allocation")
        if state == "DONE":
            if d["estimated_remaining_hours"] != 0 or d["safe_remaining_hours"] != 0:
                raise ValueError("Done day still has remaining time")
            if not d.get("evidence") or not d.get("executed_date_kst"):
                raise ValueError("Done day must have real evidence and execution date")
        if state == "BLOCKED" and not d.get("blocker"):
            raise ValueError("Blocked day missing blocker")
        counts[state] += 1
        status = {"DONE":"DONE","PARTIAL":"PARTIAL","BLOCKED":"BLOCKED","NOT_STARTED":"NOT_STARTED"}[state]
        ev = d.get("evidence") or []
        proof = clean(ev[0]) if ev else "—"
        sha = clean(d.get("verified_sha") or "—")
        recover = clean(d.get("recovery_date_kst") or "—")
        if d.get("blocker"):
            outstanding.append("- **" + clean(d["day_id"]) + " (" + clean(d["scheduled_date_kst"]) +
                ", " + str(pct) + "%):** " + clean(d["blocker"]) + " / 재검토: " +
                clean(d.get("recovery_condition") or "권한 또는 외부 조건 해결 시") +
                " / 회수일: " + recover)
        rows.append("| " + " | ".join([
            clean(d["day_id"]), clean(d["scheduled_date_kst"]), clean(d.get("scope") or d.get("task")),
            status, str(pct) + "%", number(d["estimated_remaining_hours"]) + "h",
            number(d["safe_remaining_hours"] - d["estimated_remaining_hours"] if SOURCE.name == "paypal_daily_progress.json" else d["safe_remaining_hours"]) + "h",
            clean(d.get("executed_date_kst") or "—"), proof, sha, recover
        ]) + " |")
    lines = [
        "# MASTER_PROGRESS — " + clean(doc["project_name"]), "",
        "> **자동 생성 파일입니다. 직접 수정 금지.** 단일 JSON 정본: `" +
        clean(SOURCE.relative_to(ROOT)) + "`. 갱신: `python render_master_progress.py --write`; 검증: `python render_master_progress.py --check`.",
        "> 예정일과 실제 수행일은 별개. DONE은 **그날 정한 검증 범위만** 완료했음을 의미하며 실제 외부 API/운영/제출 성공과 다릅니다.",
        "> 시간은 예상 작업·별도 안전 예비의 **미사용 작업 배정량**입니다. 외부 승인 대기 및 미계측 실투입시간은 포함하지 않습니다.",
        "",
        "**전체 " + str(len(days)) + "일 / 완료 " + str(counts["DONE"]) +
        " / 부분 " + str(counts["PARTIAL"]) + " / 차단 " + str(counts["BLOCKED"]) +
        " / 미착수 " + str(counts["NOT_STARTED"]) + "**",
        "",
        "**다음 실행 포인터: `" + clean(doc["active_day_id"]) + "`** · 원래 일정: `" +
        clean(doc["original_plan"]) + "`", "",
        "| ID | 예정일(KST) | 원래 작업 | 상태 | 해당 일 완료율 | 남은 기본 | 남은 예비 | 실제 수행일 | 증거(경로·CI) | 검증 SHA | 회수 목표일 |",
        "|---|---|---|---|---:|---:|---:|---|---|---|---|",
        *rows, "",
        "## 보류·차단 / 다시 확인할 일", "",
        *(outstanding or ["차단으로 기록된 작업 없음."]), "",
        "## 이미 선행한 작업과 검증 경계", ""
    ]
    for d in days:
        if d.get("advance_note"):
            lines.append("- " + clean(d["day_id"]) + " (" + clean(d["scheduled_date_kst"]) + "): " + clean(d["advance_note"]))
    if not any(d.get("advance_note") for d in days):
        lines.append("앞당긴 작업은 각 행의 '실제 수행일'에 표시합니다.")
    lines += [
        "", "## 운영 의무", "",
        "1. 모든 예정일을 JSON에서 보존하고 날짜를 건너뛰어 삭제하지 않습니다. 선행 수행은 실제 수행일을 기록하되 다음 미완료 날짜를 자동 완료 처리하지 않습니다.",
        "2. 작업 완료·부분중단·차단 변경 때 **JSON 정본 → 이 Markdown 재생성 → CI --check**를 같은 GitHub 커밋으로 반영합니다. 과거 운영문서는 이력이며 충돌하면 JSON·실제 테스트 증거를 확인합니다.",
        "3. DONE/100%는 해당 날짜 범위만 뜻합니다. 실제 PayPal/DAKER/NAS 접근·실고객·운영 배포·Devpost는 별도 외부 영수증 없으면 NOT_TESTED로 유지합니다.",
        "4. 예비시간을 기본시간에 합쳐 '실제 사용시간'이라고 주장하지 않습니다. 조건이 충족되지 않은 BLOCKED 행은 새 날짜가 와도 DONE으로 바뀌지 않습니다.",
        ""
    ]
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()
    doc = json.loads(SOURCE.read_text(encoding="utf-8"))
    rendered = render(doc)
    if args.write:
        OUTPUT.write_text(rendered, encoding="utf-8")
        print("MASTER_PROGRESS generated")
        return 0
    if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != rendered:
        print("MASTER_PROGRESS OUT OF SYNC: run python render_master_progress.py --write")
        return 1
    print("MASTER_PROGRESS CHECK PASS", len(doc["days"]), "calendar entries")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
