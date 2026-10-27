> **2026-10-28 해총 최종 공통 개발·검증 지시 / 소유자 최신 결정:** [전 프로젝트 공식 운영 정본](https://github.com/hibi89/hackathon-command-center-2026/blob/main/docs/DEV_ACCELERATION_AND_VERIFICATION_20261028.md). **활성 슬롯=KIC(+DL), PayPal, UGREEN, LA 총 4개**, 일반 구현·검증은 GPT-6 **Instant**, 최초 설계/복잡한 고위험 문제·해총 독립 감독만 높은 추론. 기능 목표→구현+집중 테스트→실패 수정→기능 단위 커밋→필요 통합 CI→최소 문서. GitHub 파일별 호출·HEAD 반복·STATUS/HANDOFF 중복·동일 CI 반복 금지. 사용자 로컬 전용 검증은 안전한 한 명령 스크립트/로컬 Codex에 맡기고 **실제 실행 SHA/PASS·FAIL·SKIP**로 보고. `TO_HAECHONG.md` 재작성은 큰 개선이 있을 때만. 기존 설계·비공개 정보·외부 승인·보안·복구/대회 게이트 보존.
>
> **DL 03:19 실패 대응:** 검증 SHA `ae7c326d16c7a0c5a4e9d97af1c63d7739a5f838`. GitHub Actions `40553524573`: 412개 중 2 FAIL (`test_as_of_filter_excludes_future_and_historical_limit`, `test_utc_offset_timestamp_normalized_and_future_filing_filtered`); Windows Python 3.11.9 전체 로컬 395개 중 5 FAIL·49 ERROR·5 SKIP, 합성 CLI 6단계 PASS. 합성 원본 `acceptanceDateTime=2025-10-15T18:00:00Z`인데 00:00/08:00 UTC 관측에 1건을 기대한 **오류 테스트 기대값**을 먼저 수정: 접수 전 0건/후 1건, UTC 오프셋·미래 필터 경계까지 재확인. 실제 인과성 보안필터를 약화하지 않는다. Streamlit 등 의존성 부족과 순수 코드 FAIL을 구분해 CI에서 정확한 SHA 회귀를 통과시킨 뒤 KIC lead와 통합.

> **2026-10-28 사용자 최상위 개발 가속 지시 — 이 브랜치에서 기존 종료 문서 반복 의무에 우선:** `feature/disclosure-lightning` 개발은 **기능 목표 → 관련 소스·테스트 일괄 구현 → 핵심 테스트 → 오류 수정 → 기능 단위 커밋 → 통합 검증 → 최소 문서 갱신** 순서. 커밋/테스트/문서 개수가 아니라 실제 실행된 프로그램 완성으로 진도 판정. 루트 `STATUS.md`는 현재 상태, `HANDOFF.md`는 복원·다음 단계, README는 사용법 전용; 자잘한 수정 때마다 모두 갱신하지 말고 전환점에서만 필요한 문서 1개 수정. 사용자 새 지시와 충돌하는 2026-10-24의 매번 100점·시간·다중 문서 갱신 의무는 **DL 브랜치에는 적용하지 않음**. 다른 브랜치 책임자는 해당 브랜치의 규약·승인 경계를 유지.

> **DL 단일 검증 명령:** 저장소 루트 Windows/Linux에서 `python verify_local.py` (DL 핵심 테스트+합성 CLI 실사용 스모크) 또는 `python verify_local.py --full` (전체 unittest 추가). 출력은 임시 폴더의 `summary.json`/단계별 로그, git HEAD·dirty 플래그·PASS/FAIL/SKIP로 분리. 승인 없는 SEC 호출, 고객 DB 접근, 패키지 설치, 원본 덮어쓰기 없음. 정확한 원격 CI를 조회하지 못하면 *UNVERIFIED*, shim 테스트는 정확한 소스 통과로 보고 금지. 코어 검증을 자동화한 뒤 기능을 계속 개발하되 테스트 장애를 출시 완료로 승격하지 말 것.

> **DL 현재 병목 기록:** P10에서는 실제 기능 파일 2개 변경보다 5개 문서·PR 갱신 및 개별 API 파일 커밋이 반복돼 관리 호출을 소모함(시간 측정 없음). 또 GitHub push Actions 실행 내역을 현 도구로 조회할 수 없고 sandbox `git ls-remote`는 DNS 실패했음. 개선: 핵심 기능+검증 한 묶음, 일괄 수정, 인수인계 한 곳, 시작/종료 HEAD 확인만, 실제 환경에서 `verify_local.py`. 보안·공식 제출·고객 데이터·SEC 연락처·권한 승인 규칙은 생략 불가.

> **2026-10-25 조직 고정 — 해총/스총:** 해총은 [해커톤 상황실](https://github.com/hibi89/hackathon-command-center-2026) 통합감독, 스총은 Private SMAX² 제품총괄. 이 저장소 실개발은 기존 **KIC `lead/kic` 총괄**이 담당. [역할·최신 우선순위](docs/HAECHONG_STECHONG_ROLE_BOUNDARY_20261025.md)를 참고. 기존 한 줄 복원명령은 변경하지 않음.

> **상시 강제 규칙 (2026-10-24 14:44:22 KST)**: [KIC_HANDOFF_CONTRACT.md](KIC_HANDOFF_CONTRACT.md) — **모든 작업 종료·부분중단마다 GitHub 최신화+복원 상태+일일 100점 진도+남은 시간+다음 작업 갱신·원격 확인이 끝나야만 종료 가능**. 사용자 시작 명령은 오직 `[kic 해커톤 깃헙 레포지토리 확인하고 작업하셈]`; 추가 인수인계 프롬프트 요청 금지. 이 문구보다 오래된 종료 규칙은 본 강제 규약으로 대체.

> **2026-10-24 14:39:37 KST 새 채팅 고정 한 줄:** `[kic 해커톤 깃헙 레포지토리 확인하고 작업하셈]` → 루트 [KIC_RESUME_STATE.md](KIC_RESUME_STATE.md) + [CHAT_BOOTSTRAP.md](CHAT_BOOTSTRAP.md)를 최우선 읽기. 이전 역할별 작업자 지침/과거 Research 대기는 폐기된 이력이다. KIC 단일 총괄 겸 개발자가 최신 lead/kic HEAD에서 다음 과제를 직접 수행한다. 

> **KIC 한 줄 시작 명령 (사용자 원문):** `[kic 해커톤 깃헙 레포지토리 확인하고 작업하셈]` → [KIC CHAT_BOOTSTRAP.md](CHAT_BOOTSTRAP.md) → `lead/kic` 최신 HEAD/인수인계/활성 업무 조회 후 **총괄이 직접 다음 실작업 수행**. 아래의 `[해커톤총괄 ...]` 표현도 별칭으로만 인정. 실제 대회 구분이 명시된 이 문장은 KIC 저장소로 바로 연결한다.

> **새 채팅 고정 문구:** `[해커톤총괄 깃헙 레포지토리 확인하고 작업하셈]` → [KIC CHAT_BOOTSTRAP.md](CHAT_BOOTSTRAP.md) (반드시 `lead/kic`). 역할/원격 HEAD/직접 개발 중단점 자동 복원 규칙. **총괄=개발자**, 구형 작업자 READY는 이력일 뿐.

> **CURRENT POLICY — 2026-10-24 KST: KIC 총괄 = 유일한 설계자·개발자·테스터·검수자.** 별도 Research/Verification/Risk 작업자 채팅과 작업자용 READY 디스패치 체계는 종료. 현재 작업은 [LEAD_ACTIVE_WORK](docs/roles/lead/LEAD_ACTIVE_WORK.md), 실행 절차는 [LEAD_FULLSTACK_PROTOCOL](docs/roles/lead/LEAD_FULLSTACK_PROTOCOL.md)를 따른다. 기능 브랜치는 삭제하지 않는 이력·원본이며 기본 신규 작업은 `lead/kic`에서 직접 수행한다. 기존 문서의 '작업자에게 넘기라'는 문구는 역사 기록으로만 해석한다.

# ProofInvest — AI 작업자 공통 규칙

1. **기본 인수인계 순서**: docs/roles/lead/HANDOFF.md → STATUS.md → OPERATIONS.md → AGENTS.md → REQUIREMENTS.md → 소스. 각 브랜치 고유 역할의 최신 STATUS/HANDOFF와 실소스를 대조하고 원격 HEAD를 확인한다.
2. `main`은 최종 통합본, `lead/kic`는 KIC 총괄 감독, `feature/research`, `feature/verification`, `feature/risk`는 기능별 작업 담당. **역할별 소유 브랜치만 수정**.
3. 사용자: 자이언츠파크 1인. 전체 해커톤 총괄(세 대회 감독)은 KIC 총괄과 별도 역할이다. KIC 총괄은 KIC 제출과 기능 통합만 책임진다.
4. **한 제품, 세 기능**: 연구 → 공시 검증 → 위험 신호. 데이터 계약·기준일·연결/별도·통화·정확한 출처를 통제한다. 기능별 임의 재설계 금지.
5. 합성 수치는 항상 `SYNTHETIC_FIXTURE`로 표기. 누락·혼란·미검증 수치는 추정값으로 채우지 않는다.
6. 투자 권고·매매 실행·타인 계좌 접근은 하지 않는다.
7. Public 저장소이므로 키/토큰/`.env`/개인정보/비공개 기업자료/공식 기획서 비공개 초안 원본을 커밋하지 않는다.
8. 실제 OpenDART 호출은 사용자 승인, 라이선스/쿼터/비용 확인 후 실시. AI Plus 구독은 외부 API 무료 제공 근거가 아니다.
9. 정상 소스 보존; 최소 수정, 오프라인 테스트, PR 검수 후 통합. 무의미한 빈 커밋, 강제 push, Git 이력 강제 수정 금지.
10. 실제 GitHub SHA·CI·HTTP/브라우저 상태를 나누어 검증. CI 녹색이 배포 정상은 아니다.
11. 역할 문서는 각 브랜치의 `HANDOFF.md`와 `STATUS.md`를 종료 전에 갱신. 성공·부분·미검증을 분리.
12. 채팅 맥락은 문서보다 신뢰도가 낮다. 최신 GitHub 브랜치/코드/검증 근거를 우선.
