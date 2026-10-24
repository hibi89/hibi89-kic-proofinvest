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
