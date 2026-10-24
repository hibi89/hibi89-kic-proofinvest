# KIC 예선 — 동결 PDF 동일파일 검사와 실제 제출 절차 (2026-10-24 KST)

## 목적·제약
- 공식 PDF 사전검사 P0 보강. 기존 60일 일정표 29 DONE / 3 BLOCKED / 28 NOT_STARTED는 변하지 않음.
- 동결 후보 KIC_ProofInvest_FROZEN_CANDIDATE_20261024.pdf (513,113 bytes, SHA-256: 0bdbbf04f374a7ccb39cd15e1aa700a006514278b094d32bb05ac7db610e034e). 기존 Private Library 검수 당시 10쪽 확인. 비공개 PDF/PPTX 6개 GitHub 업로드 금지.
- 새 검사는 크기·헤더·SHA-256 byte identity만 확인. 새 페이지 시각검사, DAKER 팀장 업로드권한, 공식 최종 접수 인증 불가.

## 접근방식 비교
- A: 파일명과 눈검사만 사용 → 비용·구현 0, 동일 파일명 다른 버전 오제출 위험.
- B (채택): Python 표준 라이브러리 파일 지문 + 합성-only 8개 테스트 → 별도 의존/서버 호출/유료비용 0, 바이트 불일치 시 DO_NOT_UPLOAD.
- 정식 승인으로 PDF가 바뀌면 검수된 새 비공개 파일의 크기·해시를 업데이트해야 하며 기존 지문 검사 결과를 억지로 성공 처리하지 않는다.

## 사용 방법 — 로컬 PC로 제출할 때에만 선택 실행
작업 저장소에서 로컬에 준비한 동결 후보를 대상으로 실행한다. 현재 모바일 상태에서 할 필요 없음.
```powershell
python scripts/kic_submission_preflight.py "C:\PRIVATE_PATH\KIC_ProofInvest_FROZEN_CANDIDATE_20261024.pdf"
```
- 정상: exit=0 / READY_FOR_USER_REVIEW_NOT_SUBMITTED / PINNED_FROZEN_PDF_MATCH
- 실패: exit=2 / DO_NOT_UPLOAD. 파일 내용·경로·이름을 stdout에 출력하거나 GitHub로 전송하지 않음.
- 실제 동결 PDF에 새 명령을 실행한 사실은 아직 없음. 163개 CI는 합성 fixture 테스트이며 실제 업로드 권한 및 접수까지 검증한 증거가 아님.

## DAKER 실 제출 안전 순서
1. 현재 브라우저에서 로그인·참가 신청·1인 팀 구성 완료·결과물 제출 내비게이션 버튼 표시는 관찰했으나, 휴대폰 인증 요구와 팀장 최종 PDF 권한은 미검증. 본인 세션에서 직접 확인.
2. DAKER 작전실의 '해커톤 동기화'는 기존 제출물의 제목/내용/링크를 덮어쓸 수 있고 실제 PDF는 자동으로 전달하지 않는다고 안내됨. 기존 비공개 동결 PDF 자체가 대회 제출 화면에 붙었는지 별도 검증. 기존 작성 내용 덮어쓰기 금지.
3. 공식 페이지 https://daker.ai/public/hackathons/kic-ai-agent-competition → 제출 탭 → 예선 기획서 제출 → 선택 PDF의 버전·용량·쪽수 확인.
4. 팀장 계정에서 '제출 완료' 수행은 사용자 별도 명시 승인 후에만. PDF 업로드/임시저장만으로 예선 접수 완료가 아님.
5. 제출 내역의 '최종' 표시 및 영수증 확인 후에만 실제 제출 DONE. 목표 11/10, 공식 마감 2026-11-12 10:00 KST. 11/11은 장애 대비일.
참조: https://daker.ai/community/daker-strategy-room-proposal-competition-submissio 및 https://daker.ai/community/kic-ai-agent-preliminary-proposal-final-submission (DAKER 커뮤니티 설명, 실제 공식 화면이 우선).

## 회귀·복구·현재 차단
- 코드 scripts/kic_submission_preflight.py, 테스트 tests/test_kic_submission_preflight.py.
- 최초 로컬 실행에서 디렉터리 file descriptor 처리 1 ERROR를 발견하고 순서 수정 → 신규 8/8 PASS; GitHub Actions https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40093484806: 163/163 PASS / 0 FAIL.
- 코드 커밋: 1be86030bccc5e6a5a71597788adae058e8c9c8a; 복구 전 코드 HEAD aa5dc9c175d1d97b40ebd54d80aacdc7366e9f3b. 강제 push 필요 없음.
- 이 부가 작업 자체 100/100(검토20, 구현35, 신규 및 전체회귀30, 문서·인계15), 잔여 기본 0h + 예비 0h; 실제 작업시간 미계측. DOC 상태는 후속 CI 확인.
- DAKER 10/25 60/100 BLOCKED, DART 10/30 90/100 BLOCKED, DAKER 11/09 60/100 BLOCKED 그대로. 11/10 제출 NOT_STARTED. 다음 원장 포인터 12/03 발표 확인은 미래 WAIT.
- 외부 API 호출·계정 변경·실제 제출·비공개 산출물 변경 없음. 기존 Streamlit 및 합성 복원 경로는 CI 성공했지만 Production 서비스는 미검증.
