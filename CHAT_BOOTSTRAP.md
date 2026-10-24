# KIC ProofInvest — 새 채팅 한 줄 인수인계 진입점

**사용자 요청 KIC 전용 고정 문구(우선)**: `[kic 해커톤 깃헙 레포지토리 확인하고 작업하셈]`

**통합 범용 별칭(보조)**: `[해커톤총괄 깃헙 레포지토리 확인하고 작업하셈]` — 대회 이름이 명시되지 않으면 상위 총괄에서 구분한다.

**이 저장소의 실 작업 소유자:** KIC 총괄 겸 유일한 직접 개발자. GitHub `hibi89/hibi89-kic-proofinvest`, **`lead/kic`**. 전체 4채팅 운영 중 KIC 전담 채팅 1개. [상위 통합 진입점](https://github.com/hibi89/hackathon-command-center-2026/blob/main/CHAT_BOOTSTRAP.md).

## 한 줄 입력 후 실제 실행 순서
1. **최신 원격 HEAD**를 조회하고 `CHAT_BOOTSTRAP.md → docs/roles/lead/HANDOFF.md → docs/roles/lead/STATUS.md → docs/roles/lead/LEAD_ACTIVE_WORK.md → docs/roles/lead/LEAD_FULLSTACK_PROTOCOL.md → docs/roles/lead/TO_HACKATHON_LEAD.md → AGENTS.md → REQUIREMENTS.md → 실제 소스/테스트/CI` 순서로 확인한다. `main` 기본 브랜치의 낡은 문서와 혼동하지 않는다.
2. 현행 `LEAD_ACTIVE_WORK.md`의 **승인된 첫 미완료 업무를 이 채팅에서 직접 개발·검수**한다. 별도 Research/Verification/Risk AI 채팅/구형 `NEXT_TASK.md` READY 실행은 금지. 종전 기능별 브랜치는 원본 이력/증거로 보존하며, 검증된 내용만 `lead/kic`에 안전하게 이관한다.
3. **새 채팅 이전 기록(현재 시점 참고)**: `feature/research`의 KIC-R-001 완료 및 오프라인 26 테스트 PASS는 **구 작업자 보고**. 총괄 독립 코드/테스트 검증·병합 대기. 현재 실행 지시 상세/증거의 최신본은 반드시 `LEAD_ACTIVE_WORK.md`에서 새로 읽는다. OpenDART 실 API, Production, DAKER 팀 전환/공식 PDF 제출은 별도 실증 전 성공 주장이 불가.
4. 정당한 필요 승인: 공통 스키마 동결·실 API/외부데이터, 유료 지출, 원본/보안/권한 변경. 신규 현금 지출 0원. 기능·원본 보존, GitHub 커밋 신원/HEAD 검증, 가능한 CI/로컬 테스트 진행.
5. **작업 종료/채팅 이동 전 갱신**: `LEAD_ACTIVE_WORK.md`, `docs/roles/lead/STATUS.md`, `HANDOFF.md`, `TO_HACKATHON_LEAD.md`, 실제 변경 코드/테스트/오류 근거를 동일 작업 안에 최신화·커밋하고 원격 SHA를 확인한다. 이 진입 문서는 역할·파일 경로가 바뀌지 않는 한 굳이 매번 고치지 않는다.

**공식 기한:** KIC 2026-11-12 10:00 KST 예선 PDF; 내부 목표 11/10. 실제 제출 영수증 및 팀 전환 확인 필수.

**역할 식별:** `[kic 해커톤 깃헙 레포지토리 확인하고 작업하셈]`에는 KIC가 명시되어 있으므로 새 채팅에서 KIC 총괄 겸 개발자 역할과 이 저장소 `lead/kic`를 직접 선택한다. 대회를 특정하지 않은 범용 별칭만 입력하면 상위 통합 총괄 또는 기존 채팅의 명시적 역할을 확인한다.

## 2026-10-24 13:21:02 KST — 일별 안전 작업량 자동 복원
- 새 KIC 총괄 채팅은 LEAD_ACTIVE_WORK와 함께 docs/roles/lead/DAILY_CAPACITY_PLAN_20261024.md의 **해당 날짜·예상시간·복구예비·이월 기준**을 확인해야 한다. 하루 작업 1건만 수행하며 실제 시간은 원장에 업데이트한다.
