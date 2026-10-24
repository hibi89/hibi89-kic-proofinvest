# KIC ProofInvest — MASTER_PROGRESS

**전체 60일 상세표:** [docs/roles/lead/MASTER_PROGRESS.md](docs/roles/lead/MASTER_PROGRESS.md)

**유일한 상태 JSON 정본:** [docs/roles/lead/MASTER_PROGRESS.json](docs/roles/lead/MASTER_PROGRESS.json)

전체 예정일·일별 DONE/PARTIAL/BLOCKED/NOT_STARTED·선행 완료일·기본/예비 잔여시간·차단 회수·테스트 SHA는 위 상세표가 정본입니다. 이 루트 파일은 **링크 안내만** 하며 상태를 중복 기록하지 않습니다.

검증: `python scripts/master_progress.py --check` 또는 `python render_master_progress.py --check`. 갱신: JSON 원장 → `python scripts/master_progress.py --write` → CI 검사 → 같은 커밋으로 인수인계.

**현재 상태 숫자는 이 파일에 별도로 유지하지 않습니다.** 상세 JSON과 자동생성 표를 확인하세요. 공식 접수·실 OpenDART/API·Production 결과는 별도 증빙이 필요합니다.
