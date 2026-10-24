# HANDOFF — KIC ProofInvest main (통합 기준)

1. **목표·기술**: KIC 예선 상위 12팀 본선 목표. 자이언츠파크 1인. Python 3.10+, 합성 검산 스타터.
2. **완료·결정**: ProofInvest B안 선택; 연구/검증/위험 3기능 1제품. 스타터는 합성 수치 검증 및 위험 신호 계산만 구현.
3. **테스트**: `python -m unittest discover -s tests -v` — 이전 로컬에서 9 PASS /0 FAIL. `python -m proofinvest --claim-revenue-growth-pct 20` 출력은 합성. GitHub [main Actions 40050488506](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40050488506) `completed/success`를 2026-10-24 KST 직접 확인(합성/오프라인에 한정).
4. **상태·중단 지점**: Public 저장소 초기 등록 단계. 실 API, Agent, 웹 UI, 배포, 제출 미완료.
5. **실패·대안**: 확인된 런타임 실패 없음. 키 미제공 → 무단 API 요청 금지. 모호한 공시 계정·연결구분은 검증 강화.
6. **저장소·브랜치·SHA·경로**: `hibi89/hibi89-kic-proofinvest`; main, lead/kic, feature/research, feature/verification, feature/risk. SHA는 GitHub 조회를 통해 확인. `proofinvest/`, `tests/`, `fixtures/`.
7. **배포·실행**: Production URL/Vercel 미설정. Python 명령 README 참조. 현재 화면/브라우저/HTTP 검증 미실시.
8. **원본·보안**: KIC 공식 PPTX 원본과 작성 중 기획서/PDF는 사용자 대화 파일에서만 관리. GitHub 공개 금지(검토 전). API 키는 환경변수.
9. **다음 절차·승인**: GitHub SHA·CI 확인 → 브랜치 담당자 배정 → API 데이터 계약 승인 → 오프라인 테스트 → PR 검수. 실제 외부 API 호출은 사용자 승인.
10. **갱신·범위·기준**: 2026-10-24 KST, GitHub 초기화 시점 문서. 이후 브랜치 최신 HANDOFF/STATUS와 실제 commit/CI를 우선.

## 2026-10-24 KST — 브랜치 구조 검수 인수인계
- 대회 전체 총괄이 `main`·`lead/kic`·3 feature 원격 브랜치 5개와 역할별 문서·메시지함을 확인. 미발견 파일 0건, 현재 PR 0건.
- 현재 `main` 합성 기반 테스트 [CI 성공](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40050488506); KIC 총괄도 변경 이전 CI 성공. 이는 OpenDART 실제 조회·Production의 성공 증거가 아님.
- 새 채팅방은 [ROLE_COORDINATION](docs/ROLE_COORDINATION.md)의 **자기 브랜치 역할별 HANDOFF 경로**부터 읽는다. `main` 루트 HANDOFF가 기능 담당의 실 인수인계가 아님.
- 기존 코드/테스트/비밀값/배포/기획서 원본은 수정·이동하지 않음. 공식 PDF 제출 및 DAKER 팀 전환은 여전히 확인 필요. 기준 SHA는 이 변경 직후 원격 HEAD 재조회.
