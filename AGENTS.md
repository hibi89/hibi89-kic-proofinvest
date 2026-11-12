> **[OWNER-FINAL-BLUEPRINT-100 | 2026-11-13 KST | 사용자 확정·전체 저장소 최우선]** 제품 공식 **최종완성률은 사용자 확정 최종설계도 전체 100%**를 분모로 한다. 총괄·작업자는 임의로 설계를 축소하거나, 해커톤용 MVP·합성 테스트·CI PASS·85/95% 내부 마일스톤을 최종완성률로 혼용할 수 없다. 최종설계 요구사항 ID→코드→정확 SHA 실제 검증→미구현/미검증 및 사용자 승인 가중치를 추적해 계산한다. 근거·가중치가 미비하면 **최종설계 기준 UNASSESSED(재산정 대기)**로 표시하고 종전 수치는 **과거 내부 마일스톤**으로 보존한다. 크몽 관련 완성률은 해총 `kmong-productization` 원장에 동기화한다. [작업중]/등록완료/RELEASE HOLD 등 기존 별도 상태는 보존한다. 상충하는 구형 진척률 산정 지시보다 우선. [공통 전체 규칙](https://github.com/hibi89/hackathon-command-center-2026/blob/kmong-productization/docs/strategy/FINAL_BLUEPRINT_COMPLETION_STANDARD_20261113.md). 정책 커밋은 코드 수정·성공 테스트·제품 출시·재산정 완료를 의미하지 않는다.

> **[KMONG_WORK_TARGET_GATE_20261112 | 사용자 최신 확정 | 필수 작업 규칙]** 이 저장소에서 크몽 상품·육성 후보를 작업하는 모든 AI 담당자는 새 채팅·`ㄱ` 시작 시 이 문구를 읽고 적용한다.
> - 실제 개발/수정/테스트 착수 즉시 [해총 크몽 최종완성률·후보 상태표](https://github.com/hibi89/hackathon-command-center-2026/blob/kmong-productization/docs/audits/KMONG_16_CURRENT_20261111.md)의 **해당 상품명 옆에 `**[작업중]**`을 표시하고 GitHub 커밋**한다. 확정 단계 목표(예: 95%)와 검증 기준을 제품 STATUS/HANDOFF에 남긴다.
> - **목표 완성률 달성 전에는 [작업중]을 삭제하지 않는다.** 일시중단·종료·보류·다른 제품 전환·담당 채팅 변경도 삭제 사유가 아니다. 예전 '전환·중단 시 삭제' 지시는 폐기한다.
> - **검증된 목표치에 도달한 뒤에만** 기능 SHA·PASS/FAIL/SKIP·미검증을 기록하고 자기 표시를 제거·커밋한다. 목표 하향/변경으로 표식 제거 시 사용자 명시 승인 필요. 다른 담당자 표시·기존 수치·RELEASE HOLD 보존.
> - 표식은 목표 미달 상태를 의미하며 **실시간 실행 증명은 아니다**. 허브 최신 HEAD 확인 후 안전하게 반영, 실패 시 `KMONG_HUB_SYNC_PENDING` 기록. 자동 동기화 없음. 크몽 외 작업에는 표시 불필요.

> **2026-10-28 해총 전 저장소 최상위 공통 운영 공지 (소유자 승인):** [개발 가속·로컬검증·병목제거 통합 정본](https://github.com/hibi89/hackathon-command-center-2026/blob/main/docs/DEV_ACCELERATION_AND_VERIFICATION_20261028.md)을 새 채팅 시작 시 먼저 적용한다. **활성 개발 4개 슬롯은 KIC(+Disclosure Lightning)·PayPal·UGREEN·LA만**, 합의된 구현/테스트는 **GPT-6 Instant**, 최초 설계·고위험 난제·해총 독립검수는 높은 추론. 이 저장소의 활성 개발은 각 총괄의 지정 개발 브랜치에 한한다. GitHub 파일별 왕복·중복 문서 갱신을 줄이고, 기능 단위 커밋·실행된 테스트의 SHA/PASS/FAIL/SKIP·단일 안전한 로컬 검증을 우선한다. 이전 지시의 사소한 변경마다 STATUS/HANDOFF/README 전량 갱신 의무보다 본 공통 프로세스를 우선한다. **기존 설계 동결·보안·외부 호출/결제/고객정보·제출 승인 요건은 절대 완화하지 않는다.** 본 문구는 운영 공지이며 기능 검증이나 배포 승인이 아니다.

> **KIC 새 채팅방에서는 아래 한 줄만 입력하면 됨:** `[kic 해커톤 깃헙 레포지토리 확인하고 작업하셈]`
>
> **본 `main`은 구형 안정 코드**. 새 채팅은 `lead/kic`의 [실제 시작 절차](https://github.com/hibi89/hibi89-kic-proofinvest/blob/lead/kic/CHAT_BOOTSTRAP.md) → [KIC 최신 복원·다음 작업](https://github.com/hibi89/hibi89-kic-proofinvest/blob/lead/kic/KIC_RESUME_STATE.md) → [실제 완료율](https://github.com/hibi89/hibi89-kic-proofinvest/blob/lead/kic/docs/roles/lead/DAILY_PROGRESS.md)을 원격 최신 HEAD 기준으로 직접 읽고 **하나의 KIC 총괄 채팅에서 바로 개발 재개**한다. 과거 Research/Verification/Risk 별도 작업자 READY·`main`의 역사 기록은 실행 지시가 아니다.
>
> 2026-10-24 14:39 KST까지 확인된 마지막 검증: `lead/kic` Risk 입력 게이트 100%, 67/67 테스트 성공; 다음은 11/01 결측·0분모·음수자본 안전 계산. DAKER 제출권한 35%, DART 직접 뷰어 확인 90% 차단. **항상 위 링크에서 최신치를 다시 읽어야 한다.**

# ProofInvest — AI 작업자 공통 규칙

1. **기본 인수인계 순서**: docs/ROLE_COORDINATION.md → 통합 HANDOFF.md → STATUS.md → AGENTS.md → 소스. 각 브랜치 고유 역할의 최신 STATUS/HANDOFF와 실소스를 대조하고 원격 HEAD를 확인한다.
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
