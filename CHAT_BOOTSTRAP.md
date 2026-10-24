# KIC ProofInvest — 새 채팅 **한 줄만**으로 복원

> **최우선 불변 종료 규칙:** [KIC_HANDOFF_CONTRACT.md](KIC_HANDOFF_CONTRACT.md). **매 작업 종료마다 복원 상태·진척률·남은 시간·인계·원격 SHA/CI가 GitHub에 있어야 종료 완료**. 새 채팅은 항상 이 최신 상태를 기반으로 일한다.

> **유일한 KIC 시작 문구 (사용자가 그대로 입력):** `[kic 해커톤 깃헙 레포지토리 확인하고 작업하셈]`

이 문장은 **KIC 해커톤 총괄 겸 직접 개발자 역할**, 저장소 **`hibi89/hibi89-kic-proofinvest`**, 작업 브랜치 **`lead/kic`**를 자동 선택하는 지시다. 별도 장문의 인수인계 텍스트를 사용자에게 요구하지 않는다. GitHub 연결의 최신 원격 상태를 읽고, 그 채팅에서 실제 다음 작업을 수행한다.

## 반드시 실행할 시작 순서 (사용자 추가 질문 없이)
1. 연결된 **GitHub**에서 저장소 `hibi89/hibi89-kic-proofinvest`의 **`lead/kic` 최신 원격 HEAD SHA**를 먼저 조회한다. `main`은 오래된 안정 코드이므로 현행 작업 포인터로 사용하지 않는다.
2. 해당 HEAD의 루트 [**KIC_RESUME_STATE.md**](KIC_RESUME_STATE.md)를 **최우선 정본**으로 읽는다. 여기에 완료·부분완료·중단·다음 실제 코딩 작업·잔여시간·CI 증거가 한곳에 있다. 이 파일 자체에 적힌 SHA는 관측 당시 증거이며, **최신 원격 HEAD를 계속 확인한다**.
3. [LEAD_ACTIVE_WORK.md](docs/roles/lead/LEAD_ACTIVE_WORK.md) → [DAILY_PROGRESS.md](docs/roles/lead/DAILY_PROGRESS.md) → [BLOCKED_WORK_RECOVERY_20261024.md](docs/roles/lead/BLOCKED_WORK_RECOVERY_20261024.md) → [DAILY_CAPACITY_PLAN_20261024.md](docs/roles/lead/DAILY_CAPACITY_PLAN_20261024.md) → [WORK_ORDER_FLEX_POLICY_20261024.md](docs/WORK_ORDER_FLEX_POLICY_20261024.md) → [LEAD_FULLSTACK_PROTOCOL.md](docs/roles/lead/LEAD_FULLSTACK_PROTOCOL.md) 순서로 확인한다. 그 뒤 해당 코드·테스트와 최신 CI를 직접 확인한다.
4. **한 줄 문장은 실행 지시이기도 하다**: `KIC_RESUME_STATE.md`의 다음 개발 작업이 이미 완료되지 않았고 접근 가능한 상태라면, 과거 조사/코딩을 반복하지 말고 바로 착수·테스트·GitHub 커밋한다. 두 번 이상 동일 실패 시 다른 경로를 선택하거나 BLOCKED로 남긴다. **추가 인수인계 프롬프트 요청 금지**.
5. 완료 또는 부분중단 시 [KIC_RESUME_STATE.md](KIC_RESUME_STATE.md)·`LEAD_ACTIVE_WORK.md`·`DAILY_PROGRESS.md`·`STATUS.md`·`HANDOFF.md`·`TO_HACKATHON_LEAD.md`를 최신화하고 **일일 100점 기준 완료율 및 남은 순작업/오류 예비시간**, 실제 작업시간(미계측 가능), 코드 SHA/CI/외부 미검증 사항을 기록한다. 원격 HEAD와 CI 재확인 후 사용자에게 동일 수치 보고. 다음 새 채팅에도 **이 한 줄만** 재사용한다.

## 현재 복원 관문 (변경되면 정본 상태 파일을 반드시 최신화)
- **2026-10-24 마지막 구현 검증**: 10/31 Risk verified-only **100%, 잔여 0h**, [67/67 CI PASS](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40066732288).
- **다음 즉시 개발:** 11/01 Risk 결측·0분모·음수자본의 안전 중단/계산. 기본 1.5h+예비 3.5h=최대 5h (아직 미착수). Risk 게이트와 기존 엔진의 우회경로를 대조.
- **차단 유지:** 10/25 DAKER 팀권한/공식 양식 **35%**, 10/30 DART 공식 사업보고서 접수 원문 대조 **90%**. 외부 인증 없이 완료 처리하지 않는다. 다음 재확인 목표 각각 10/25~26, 10/27.
- **프로젝트 미완료:** 전체 Agent 통합, 공식 양식 PDF 최종화·실제 제출, 실 OpenDART API·Production 데모, `main` 통합. 최종 접수 목표 **11/10**, 공식 예선 마감 **11/12 10:00 KST**.

## 충돌/안전 규칙
- **최신성 우선순위:** 최신 GitHub 소스·CI의 실제 영수증 ＞ `KIC_RESUME_STATE.md`/현행 작업포인터 ＞ 날짜별 마지막 확정 진척 기록 ＞ 긴 `HANDOFF.md`·`STATUS.md`의 오래된 문단 ＞ 과거 채팅. 예전 문서의 `Research 수용 대기`, `READY 작업자 채팅 실행`, `하루 1건만` 같은 구형 규칙은 **폐기된 이력**.
- KIC 총괄이 **하나의 채팅방에서 직접 설계·개발·테스트·검수**한다. 별도 Research/Verification/Risk 작업자 채팅이나 옛 `WORKER_ROUTER.md`/`NEXT_TASK.md` 사용 금지. 기능 구분은 코드 모듈만.
- 앞당겨 완료한 다른 날짜 작업을 같은 날짜 완료율에 합산하지 않는다. 미검증/차단된 날을 100%로 꾸미지 않는다. 실제 투입 시간 미계측이면 `미계측`.
- `lead/kic`에서만 개발, `main`·`feature/*`를 승인 없이 변경/강제 푸시하지 않는다. public GitHub 비공개 기획서/토큰 저장 금지. 실 API/돈 지출/팀 전환·접수는 별도 승인과 증거 필요.
