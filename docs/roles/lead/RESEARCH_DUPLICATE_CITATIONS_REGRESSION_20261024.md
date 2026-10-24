# 2026-11-23 계획 Research 회귀·중복 근거 방어

## 업무 및 선행 실행
- 원래 2026-11-23 예정 / 실제 2026-10-24 KST. 저장소 `hibi89/hibi89-kic-proofinvest`, 단일 `lead/kic` 브랜치.
- **실제 결함**: `normalize_research`는 각 `source_id`의 중복만 검사하고, 서로 다른 ID를 같은 출처 HTTPS URL에 붙여 중복된 근거를 독립 자료인 것처럼 재사용 가능했다. 서로 다른 license/메타데이터가 동일 URL에 붙어도 별도 근거로 통과할 수 있었다.
- **선택한 수리 A**: 구조적으로 채택된 출처 중 **정확히 동일한 URL 문자열**에 여러 ID가 있으면 그 URL에 속한 ID들을 모두 제외하고 `duplicate_source_url` 경고 기록; 해당 ID에 의존하는 finding은 `unavailable_evidence`로 제외. 다른 독립 URL과 정당한 finding은 `partial`로 보존.
- **대안 B**: 동일 URL 첫 건만 살리고 alias ID 병합 — 어느 쪽 출처의 license/출판일이 맞는지 모르는 상태에서 임의 인증 가능, 출처 조작 위험으로 보류. 전체 웹 URL 정규화/실원문 조회는 현 오프라인 계약 범위를 넘으므로 미실시.
- **작동 범위**: 중복 제거는 *문자열 일치 URL*에만 적용. 쿼리 파라미터/리디렉션/경로 별칭/URL shortener 등 의미상 동일한 URL은 구별할 수 없음. 별도 원문 인증이 필요하며, 본 기능으로 사실·라이선스 적법성 검증 주장 불가.

## 파일과 CI
- 코드 최종 SHA `164d810855fd336526a45c5b85080980c0ec11bd`; `proofinvest/research.py`, `tests/test_research.py`, `tests/test_peers.py` 수정.
- 신규 **5건 회귀**: 서로 다른 ID·같은 URL 중복 차단; 다른 권리/라이선스 메타데이터의 URL 중복 차단; 서로 다른 URL 출처 정상 허용/순서독립; 독립 URL에 의존하는 finding만 partial 보존; Research→Peer 연결에서 같은 URL의 가짜 복수 출처 차단.
- **실패 후 수정 증거**: 최초 코드 `8a8b43d0a2664671ebaef10f0b6818bf83d64d32` [CI #40081158022](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40081158022) **110 PASS/111 중 1 FAIL**. 원인은 과거 `test_one_source_rights_status_does_not_certify_another`가 '독립 출처' 테스트에서 실제로 동일 URL을 사용한 fixture 오류. 코드를 약화하지 않고 두 번째 출처 URL을 독립 주소로 교정.
- **최종 재검증**: [GitHub CI #40081231968](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40081231968) `completed/success` **111/111 PASS**, FAIL0 ERROR0, 60일 상태 검사·합성 CLI·수동기록 오프라인 CLI 전부 SUCCESS. 별도 로컬 테스트·실 API/웹 요청·Production 검증 없음.
- **타 기능 간섭 없음**: `engine`·`risk` 및 frozen 후보 10p PDF/PPTX 바이너리·사용자 Library 6개 백업에 수정/공개/재검증 없음.
- **오프라인/사실/법적 제약**: 합성 fixture 중심. `Research success`는 오프라인 구조적 유효성일 뿐 실제 기업 공시 원문 진실성, 발행자 권한, 권리 범위, 실 투자 가치 등을 인증하지 않음.

## 완료 조건·차단·인수인계
- 11/23 작업 **100/100 DONE**: 원인 및 두 대안 비교20, URL 중복 안전 차단35, 회귀5건+CI 검증35, 60일 정본·GitHub 인수인계10. 남은 기본 **0h** + 예비 **0h**, 실제 투입시간 미계측.
- 60일 **21 DONE/3 BLOCKED/36 NOT_STARTED** 예정. P0 DAKER 참가·팀장 최종 제출 권한 10/25 및 11/09 **각60% BLOCKED**(실계정/로그인/버튼 미확인). DART 정식 뷰어 접수번호 대조 10/30 **90% BLOCKED**. 공식 11/10 제출 NOT_STARTED, 실제 접수 영수증 없음.
- 11/18·11/19 상호평가 인증·투표 영수증은 10/24 현재 미래 의존으로 NOT_STARTED 유지; 11/22는 기본0h+예비3h의 미사용 원래 예비일로 NOT_STARTED 유지.
- **다음 READY 2026-11-24** Risk 임계값과 코드 설명 일치 점검, 0/100, 기본1h+예비2h=3h. 실제 DAKER 인증 제출권한 확보 가능해지면 해당 P0 먼저 회수할 것.
- 원복 직전 저장소 SHA `f671074568070d7bd9b4c96d220a0f6dc15ea9d6`, 후속 정상 git revert 가능. force push/브랜치 변경/원본 PDF 재디자인 없음.
