# TASK KIC-R-001 — Research 오프라인 근거 정규화 및 테스트

| 항목 | 내용 |
|---|---|
| Task ID | `KIC-R-001` |
| 상태 | `READY` (총괄 발행, 사용자 작업자 채팅 시작 전) |
| 담당 기능 / 실행 채팅 | Research / **단 하나의 범용 KIC 작업자 채팅** |
| 코드 수정 브랜치 | **`feature/research`** |
| 총괄 지시 브랜치 | `lead/kic` (읽기만) |
| 사용자 승인 범위 | 오프라인 코드·합성 fixture·테스트·해당 브랜치 역할 문서. **공통 데이터 계약 최종 동결이나 외부 API 호출 승인은 포함하지 않음** |
| 목표 일자 | 2026-10-28 KST 내부 마일스톤 |
| 수신·완료 보고 | `docs/roles/research/TO_KIC_LEAD.md` (**feature/research에 커밋**) |

## 목적

ProofInvest가 단순히 기업을 요약하는 것이 아니라, **검증 가능한 근거가 있는 산업/기업 발견사항**만 다음 Verification 단계에 넘길 수 있도록 `Research`의 **오프라인 근거 처리 최소 기능**을 구현한다. 실 데이터 조사·공식 API 접근·LLM 호출이 없이도 입출력 검증과 안전한 실패를 테스트 가능해야 한다.

## 먼저 확인

- `lead/kic` 최신 `NEXT_TASK.md`가 `READY / KIC-R-001 / feature/research`인지 확인. 다른 TASK/상태이면 **지시된 작업 실행 금지**.
- `feature/research` 원격 HEAD 및 `docs/roles/research/HANDOFF.md` → `STATUS.md` → `OPERATIONS.md` → `TO_KIC_LEAD.md` → `AGENTS.md` → `REQUIREMENTS.md` → `proofinvest/` 와 기존 테스트 확인.
- 같은 Task ID의 완료/진행 영수증이 있다면 중복 작업 방지 및 이전 실행 커밋 조사.
- 시작 시 `[IN_PROGRESS] KIC-R-001` 영수증을 `TO_KIC_LEAD.md`에 커밋하고 실 작업 착수.
- 이 단계에서는 **Research 독립 내부 구조만** 구현하고 *다른 모듈과의 최종 공통 데이터 계약* 변경은 총괄 승인 요청 상태로 남긴다.

## 허용된 코드 변경

1. `proofinvest/research.py` 신규: **호출자가 제공한 합성/외부에서 이미 합법적으로 확보된 기록 리스트**만 받아 근거를 정규화하는 **순수 결정론적 함수**. `requests`/HTTP/SDK/외부 Agent·Gemini·OpenDART 호출을 넣지 않는다.
2. `tests/test_research.py` 신규: 적어도 6개 의미 있는 단위 테스트. 원본 9개 테스트 회귀 유지.
3. 필요한 경우 `fixtures/research_*.json`처럼 명확히 **`SYNTHETIC_FIXTURE` 표기된** 합성 테스트 파일.
4. `docs/roles/research/STATUS.md`, `HANDOFF.md`, `TO_KIC_LEAD.md` 종료 기록. 필요하면 `docs/roles/research/OPERATIONS.md`에 **이 과제의 실제 검증**에 한해서 메모.
5. 기존 공통 `proofinvest/engine.py`, `dart_adapter.py`, `__main__.py`, `main`, 다른 feature 브랜치 또는 `lead/kic` 파일 **수정 금지**.

## 세부 기능 요구

- 출처 `id/title/url/published_at/collected_at/license`, 발견사항 `claim/source_ids/as_of`, 타깃 `target_name/target_id(optional)` 등 최소 내부 레코드 필드를 제안. 다른 모듈과 강결합하지 않고 최종 필드 계약 제안은 총괄 메시지에 기록.
- `https` 원문 URL·자료 기준일·수집시각·중복된 `source_id`/출처 ID의 충돌 등 입력 검증. 유효하지 않으면 실 출처로 거짓 정규화하지 않고 `unavailable` 또는 명시적 오류를 반환. 빈/공백 claim은 확인된 근거라고 간주하지 않음.
- claim에 연결된 `source_ids`가 없거나 등록 근거에 존재하지 않으면 그 finding은 **안전하게 제외하거나 `unavailable` 표기**. 없는 출처/기업/재무숫자를 창작하지 않는다.
- `as_of`를 따르지 않는 미래 발행 자료(기준일 이후 published_at)를 사용하는 실수를 막고, 불일치 근거/경고를 사용자에게 설명 가능한 형태로 남긴다.
- 기능은 **형식/추적 가능성/자료 존재 여부만 검증**하며 실제 산업 주장 진위·출처 라이선스 적법성을 증명한다고 **주장하지 않는다**.
- `status` = `success|partial|unavailable` 수준의 모듈 내부 결과를 제안하되, 추후 시스템 전역 `verified|conflict|unavailable` 판정과 혼동하지 않는다.
- 표준 라이브러리와 기존 프로젝트 Python/CI로 재현 가능해야 한다. 불필요한 의존성 추가 금지.

## 오프라인 테스트 수용 조건 (최소)

- 올바른 출처+연결된 발견사항 정상 처리.
- 출처 URL 부정확·빈 값이면 허위 성공 차단.
- 참조되지 않는 `source_id`가 있는 주장 차단.
- 같은 ID에 다른 URL/문구를 가진 출처가 들어오면 충돌 탐지.
- `as_of` 이후 발행된 근거를 과거 시점 분석에 끼우지 않음.
- 아예 출처/발견사항이 없으면 `unavailable`.
- 기존 `python -m unittest discover -s tests -v` **기존 9개 + 신규 6개 이상 PASS**.
- `python -m proofinvest --claim-revenue-growth-pct 20` 기존 합성 데모 유지.
- GitHub Actions가 아직 실행 중이면 `CI pending`으로 기록; 성공이라고 선보고하지 않음.

## 끝나면 반드시 보고

`feature/research:docs/roles/research/TO_KIC_LEAD.md`에 다음 필드로 `[DONE] KIC-R-001` 또는 `[BLOCKED]`:

`task_id, branch, final HEAD SHA, 수정 파일, 테스트 명령/통과 개수/실패, CI run 링크/상태, 구현 계약 제안, 확인된 제한, 남은 위험/승인 요청, 총괄 검수 필요 항목`.

`STATUS.md`, `HANDOFF.md` 동시 갱신. **다른 기능 브랜치로 자동 이동하거나 `NEXT_TASK.md`를 스스로 수정하지 말고 중지**.

**KIC 총괄이 Review & Accept 후에만 `KIC-V-001`을 발행할 수 있다.**
