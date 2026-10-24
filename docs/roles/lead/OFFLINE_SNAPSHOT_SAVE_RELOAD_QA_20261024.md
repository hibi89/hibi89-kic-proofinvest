# KIC 2026-11-30 예정 저장·재조회 분리 1경로 — 2026-10-24 선행

## 구현 및 의사결정
- 실제 코드 69bd4efdf648a399d10bf29788a0fcb9a6f0bf26 on lead/kic; Python 표준 라이브러리 기반 신규 proofinvest/snapshot_store.py, tests/test_snapshot_store.py, README 명령/CI smoke 추가.
- 목표: bundled 합성 fixture만 사용하여 display snapshot을 **명시적 save 1회** 계산·파일 저장하고, read 명령은 **저장된 결과만 검증 후 반환**, Risk 및 매출 검증 재계산 금지. 반복 save는 정상 기존 기록 재사용(별도 계산 없음).
- 대안 A: Streamlit 화면의 매 렌더 시 계산 (중복 계산 문제 지속). 대안 B: 별도 버전 명시 JSON 스냅샷과 저장/조회 함수를 분리, 읽기 검증(채택). UI 연결은 다음 12/01 일정이며 이번 작업에서 UI 기존 동작을 바꾸지 않음.
- 명령: python -m proofinvest.snapshot_store --save / --read (서로 별도 실행). 사용자가 save를 호출할 때만 사용자 홈의 .proofinvest-synthetic-cache 디렉터리에 파일 1개 저장. 읽기는 저장 파일 없으면 실패, 새 계산 불가.
- 디스크 JSON에는 format ID, 입력 fixture SHA-256, payload SHA-256, SYNTHETIC_FIXTURE 뷰모델만 존재. 재조회는 해시, fixture 변경, 합성/미인증 구조 필드를 확인. SHA-256은 **오류/손상 감지**용이며 공격자에 대한 서명, 실제 기업 출처 인증이 아님.
- 기본 보호: 공개 GitHub 저장소 내부 저장 거부; 심볼릭 링크 캐시 디렉터리/파일 거부; 사용자 파일 덮어쓰기 거부(O_EXCL); 기존 파일 오염/fixture 변경 시 자동 수정·재계산 금지.

## 검증 근거
- 신규 단위테스트 9개: 최초 저장/읽기 중 계산 미호출, 반복 저장 재사용, 파일 없음, checksum 훼손, 변조된 인증 플래그와 재계산된 checksum도 거부, fixture 구버전 거부, 공개 repo 경로 저장 거부, symlink 캐시 거부, 필드 최소화.
- [GitHub Actions #40086307653](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40086307653) **completed/success, unittest 144/144 PASS**, master_progress.py/render_master_progress.py 동기화 PASS; 임시 HOME에서 독립 파이썬 프로세스 --save/--save/--read 실행해 CREATED, REUSED_NO_RECALCULATION, READ_NO_RECALCULATION과 동일 266.67 수치 확인. 기존 Streamlit AppTest/합성 CLI/수동 공시기록 **오프라인** CLI 모두 PASS.
- 실제 브라우저 시각 검증/Production 웹 배포, 실제 OpenDART/API, 실재 기업 공시 원문 인증, DAKER 제출은 이 저장·재조회 기능으로 수행하지 않았음. 실제 기기 Windows 독립 실행은 별도 미검증.
- 에러 처리/제약: 파일 저장 중 프로그램/전원이 중단돼 불완전 JSON이 남으면 다음 read는 안전 보류하고 사용자 판단 없이 자동 삭제/재계산 안 함. 과거 캐시 데이터 보안은 로컬 디렉터리 권한에 의존; 합성자료만 저장. 조회 전 입력 fixture 파일 읽기/해시는 수행하지만 계산함수 호출하지 않음.

## 계획·상위 지시·복원
- 11/30 계획 업무 선행 **100/100 DONE**: 저장·재조회 계약/권한 경계 25, 구현 35, 9개 회귀+CI CLI 재현 30, 근거·HANDOFF·통합총괄 회신 10. 잔여 기본0h+예비0h, 실제 투입 시간 미계측. 60일 날짜별 27 DONE/3 BLOCKED/30 NOT_STARTED, 이는 제품 완성률 수치 아님.
- P0 DAKER 실제 참가자 개인/팀, 팀장 권한/단일 PDF 업로드 버튼은 계정 로그인 없이 알 수 없어 10/25, 11/09 각60% BLOCKED_EXTERNAL, 내부11/10 공식 제출 NOT_STARTED. 사용자는 본인 브라우저에서 DAKER 로그인→대회 참가유형·팀장 여부→한 파일 PDF 최종 제출 페이지 접근·버튼 권한 확인만 공유. 실제 버튼 클릭·비공개 파일 공개·계정 변경은 사용자 명시 승인 전 금지. 인증쿠키·비밀번호·토큰 제출 요청 금지.
- DART 10/30 공식 원문 뷰어 접수번호 대조 90% BLOCKED; 11/18~19 실제 상호평가, 11/22·11/29 예비일 미완료로 유지. frozen 비공개 10p PDF/PPTX·Private Library 6개 백업 무변경.
- 다음 READY 2026-12-01 합성 결과→화면→출처 1경로 검수 0/100, 기본1h+예비2h=3h. 이전 GitHub HEAD 19817e59d6edc306e3098872352c35072b76db6d 기준 revert 가능, force push/main/feature 무변경.
