# KIC 2026-11-17 예정 Verification 전체 CI·장애 목록 감사

## 목적·범위
- **예정일 / 실제 선행일**: 2026-11-17 / 2026-10-24 KST.
- **저장소/브랜치**: `hibi89/hibi89-kic-proofinvest` / `lead/kic`.
- **실제 검증 코드 SHA**: `53cdecdc5777ecefbb9977ed32ecf9cbffee29c8`; 이전 정상 기준 `fa51b0f8eb6025b9155a8888fd21e4e007ce9f9d`.
- **이번 실작업**: README에 현재 아닌 `KIC-R-001`·구 인력체계·오래된 11/2/47 숫자가 노출되던 문제 수정, `tests/test_current_readme.py`로 2개 정적 경로 회귀 검증 추가. 금융 계산 원본·비공개 10쪽 PDF/PPTX 변경 없음.
- **설계 비교**: A README 문구만 바꾸기(즉시 비용 낮으나 드리프트 재발 감시 부재) vs B README 소규모 수정 + CI 정적 회귀 검사(추가 테스트 2건·실행 비용 거의 없음·장기 유지 품질 우수). **B 선택**, 신규 인프라·계정 권한·API 비용 변경 없음.

## 실측 GitHub Actions 결과
- [CI #40079648079](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40079648079), `completed/success` on `53cdecdc5777ecefbb9977ed32ecf9cbffee29c8`.
- `python scripts/master_progress.py --check`: **PASS**, 변경 전 17 DONE/3 BLOCKED/40 NOT_STARTED. 인수인계 최신화 후 18/3/39 별도 최종 CI 확인 필수.
- `python render_master_progress.py --check`: **PASS**.
- `python -m unittest discover -s tests -v`: **Ran 96 tests / OK** (기존 94 + 신규 README 경로 2), **0 FAIL / 0 ERROR**.
- `python -m proofinvest --claim-revenue-growth-pct 20`: synthetic CLI **PASS**.
- `python -m proofinvest.evidence_scenarios`: 삼성 FY2024/2023 수동 기록 기반 3상태 오프라인 CLI **PASS**.
- **WARN(테스트 실패 아님)**: GitHub runner에서 Node.js 20 deprecated, `actions/checkout@v4`·`actions/setup-python@v5`가 Node.js 24 강제 실행; `punycode` deprecation. 현재 CI 차단 없음. 추후 호환성 평가·버전 변경은 회귀 검토 후 별도 승인/과제.
- **미실시**: 독립 로컬/브라우저 E2E/실 OpenDART API/공식 제출 계정/Production HTTP. CLI 오프라인 통과를 서비스 배포 성공으로 해석 금지.

## 잔여 장애·위험 (중복 날짜는 같은 외부 원인)
| 우선 | 장애·미완성 | 확인 상태 | 회복 조건/책임 | 잘못된 완료 주장 금지 |
|---|---|---|---|---|
| **P0** | DAKER 개인/팀·팀장 최종 업로드 권한 (10/25, 11/09 동일 인증 원인) | 각 **60/100 BLOCKED** | 사용자 인증 DAKER 화면에서 권한·제출 탭/버튼과 동결 단일 PDF 대응 확인, 상태별 각 접근 후 기본0.5h+예비1.5h (같은 원인을 두 번 수행하지 않음) | 공식 제출권한 확보 아님 |
| **P0** | 11/10 실제 PDF 업로드와 최종 접수 영수증 | **NOT_STARTED 0/100** | 참가자 명시적 최종 제출 승인 후 실제 제출, '최종' 영수증 확인. 공식 11/12 10:00 마감 유지 | 사용자 승인/영수증 없이 제출 DONE 금지 |
| **P1** | DART 공식 원문 뷰어의 접수번호 대조 | **90/100 BLOCKED** | 공식 뷰어 접속 후 수동 보고서/실제 접수번호 교차 대조, 접근 후 기본0.5h+예비1h | 수동 PDF 검산=OpenDART 인증 아님 |
| **P1** | 비합성 `engine.calculate`의 14자리 접수번호는 **형식만** 확인 | **미검증 원본 진위 위험** | 공식 원문/인증 API 증빙 가능한 경우에만 provenance 신뢰 수준 추가 분리, 별도 설계·승인 | `verified`는 내부 산술 합치만 의미 |
| **P1** | 레거시 `engine.calculate` 위험신호 경로는 verified-only Risk gate 미경유 | **기능 격리 필요** | 실제 연동은 `calculate_verified_debt_to_equity`만 사용; 통합 시 E2E 회귀 | 데모 Risk 값을 운영 위험평가로 표시 금지 |
| **P1** | 실 OpenDART 수집·자율 Agent·웹/Production 미구현 | **NOT_VERIFIED / NOT_DEPLOYED** | 외부 API 승인/키·비용·한도·라이선스 확인, 저장/조회·실 화면·브라우저 점검 | 오프라인 96 PASS가 실 API·Production 성공은 아님 |
| **P2** | GitHub Actions Node.js 20 종료 경고 | **WARN, CI 성공** | 추후 actions runner 버전 호환성 시험 후 승인받아 변경 | WARN를 CI FAIL로 표시하지 않음 |
| **P2** | `main`과 `lead/kic` 불일치 | **2026-10-24 관측: ahead 93 / behind 7** | 통합 시 main 비교·검수·사용자 승인, 단순 fast-forward 추정 금지 | main에 현재 개발 완성본 반영됐다고 주장 금지 |
| **P2 해결** | README 옛 READY 업무와 진도 수치 | **IMPLEMENTED_VERIFIED** | README 단일 실행 경로 및 정적 CI 검사 유지 | 구 `NEXT_TASK`를 실행 포인터로 재활성화 금지 |

## 선행 순서·미완료 의존성
- 11/18 상호평가 마감 전 의무·11/19 상호평가 종료 영수증은 **2026-10-24 현재 미래 사건**이며 사용자의 인증된 계정·실제 참여 기록이 없어 **각 NOT_STARTED** 그대로 둔다. 시점 도달/제출 후 실제 근거가 생겼을 때 검증한다.
- 다음 **독립 READY는 2026-11-20 'Research 출처·라이선스 근거 한 가지'**, 0/100, 기본1h+예비2h=3h. 사용자 승인 없는 외부 데이터 재배포·유료 API 사용 금지.
- P0 DAKER 접근 가능해지면 위 선행 과제보다 공식 제출권한 검증을 먼저 회수한다. PDF 시각 QA 재실행·새 디자인 작업·동결본 이름 바꾸기 금지.

## 완료 판정/롤백
- **이번 11/17 업무** 100/100: 기존 CI/테스트 단계 실증20, README 구형 경로·2개 회귀 개선30, PASS/FAIL/WARN·P0/P1/P2 잔여 장애 구분 및 회복조건30, 정본·인수인계/원격 CI 검증20. **남은 기본0h+예비0h, 실제 투입시간 미계측**.
- README 수정 전 기준 `fa51b0f8eb6025b9155a8888fd21e4e007ce9f9d`에서 Git 역커밋 가능. 원본 금융 코드·비공개 자료 미수정. force-push·권한 변경 없음.
- 60일 원장은 **18 DONE/3 BLOCKED/39 NOT_STARTED 예정**으로 갱신하며, *신규 문서 커밋의 CI 재확인 전까지 완료 선언 보류*.
