# ProofInvest KIC — AI 역할·브랜치·인수인계 연결

이 저장소는 **사용자 1인 + AI 역할 4개(KIC 총괄 1, 기능 담당 3)** 운영을 위한 기록이다. 세 대회 전체 총괄은 별도 채팅/역할이며 여기의 KIC 총괄은 KIC만 관리한다.

| 역할 | 전담 브랜치 | 첫 필독 파일 | 총괄에게 남기는 메시지 |
|---|---|---|---|
| KIC 총괄 | [lead/kic](https://github.com/hibi89/hibi89-kic-proofinvest/tree/lead/kic) | [총괄 인수인계](https://github.com/hibi89/hibi89-kic-proofinvest/blob/lead/kic/docs/roles/lead/HANDOFF.md) | [검토 기록](https://github.com/hibi89/hibi89-kic-proofinvest/blob/lead/kic/docs/roles/lead/MESSAGE_REVIEW.md) |
| 기업·산업 리서치 | [feature/research](https://github.com/hibi89/hibi89-kic-proofinvest/tree/feature/research) | [작업 설명서](https://github.com/hibi89/hibi89-kic-proofinvest/blob/feature/research/docs/roles/research/OPERATIONS.md) | [총괄에게 전하는 말](https://github.com/hibi89/hibi89-kic-proofinvest/blob/feature/research/docs/roles/research/TO_KIC_LEAD.md) |
| 재무 공시 교차 검증 | [feature/verification](https://github.com/hibi89/hibi89-kic-proofinvest/tree/feature/verification) | [작업 설명서](https://github.com/hibi89/hibi89-kic-proofinvest/blob/feature/verification/docs/roles/verification/OPERATIONS.md) | [총괄에게 전하는 말](https://github.com/hibi89/hibi89-kic-proofinvest/blob/feature/verification/docs/roles/verification/TO_KIC_LEAD.md) |
| 위험 신호 탐지 | [feature/risk](https://github.com/hibi89/hibi89-kic-proofinvest/tree/feature/risk) | [작업 설명서](https://github.com/hibi89/hibi89-kic-proofinvest/blob/feature/risk/docs/roles/risk/OPERATIONS.md) | [총괄에게 전하는 말](https://github.com/hibi89/hibi89-kic-proofinvest/blob/feature/risk/docs/roles/risk/TO_KIC_LEAD.md) |

**기능별 새 채팅에 전달할 한 줄**: "GitHub `hibi89/hibi89-kic-proofinvest`의 `feature/research` (또는 verification/risk) 브랜치 확인하고 해당 `docs/roles/<역할>/HANDOFF.md`부터 읽어서 작업 이어가." 

## 기능 담당자가 할 일
- 반드시 자신의 원격 브랜치 SHA부터 확인하고 `HANDOFF.md → STATUS.md → OPERATIONS.md → AGENTS.md → REQUIREMENTS.md → 소스` 순서로 읽기
- 해당 브랜치에서만 개발·테스트·커밋
- **작업 종료 시 `docs/roles/<역할>/STATUS.md`와 `HANDOFF.md` 최신화**
- 총괄에게 할 말/차단/결정 요청은 `TO_KIC_LEAD.md`에 적고 같은 브랜치에 커밋
- 자동 메시지 연동은 없다. 총괄이 세 브랜치를 직접 확인해야 한다.

## KIC 총괄의 기본값 (지시 전 의무)
새 지시를 내리기 전에 **세 브랜치의 최신 원격 `TO_KIC_LEAD.md`를 전수 확인**한다. 각 메시지의 확인 여부와 최신 SHA 및 판단을 `lead/kic`의 `docs/roles/lead/MESSAGE_REVIEW.md`에 기록·커밋한 다음 지시한다. 실행 근거가 없는 주장과 확인되지 않은 메시지를 검토한 것으로 보고하지 않는다.

## 저장소 단일 기준
`main`: 통합된 코드와 CI 기준. 기능 담당자 채팅의 최신 작업·메시지는 **각자의 브랜치가 기준**이며 자동으로 main에 반영되지 않는다. 작업 완료 후 검증된 PR만 main에 병합한다.

대회 자료와 API Key/개인정보는 공개 저장소에 넣지 않는다. PDF 기획서·실제 OpenDART 호출·Production은 별도로 검증해야 한다.

## 2026-10-24 KST — 구조 검수 결과
- 이 라우터 문서는 **KIC `main`**에 있으며, 각 담당의 실제 보고·인수인계는 위 표의 **해당 브랜치**에만 있다.
- 5개 브랜치, 기능 메시지함 3개, 총괄 메시지 검토·상위 보고 창구 원격 실조회 확인. 역할별 STATUS/HANDOFF 경로를 루트의 공통 통합 문서와 혼동하지 않는다.
- 코딩·PR·API/서비스 배포는 별개 작업이다. 문서 점검만으로 프로그램 완료로 표시하지 않는다.
