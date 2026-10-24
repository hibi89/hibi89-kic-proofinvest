# Streamlit 오프라인 합성 화면 검수 — 11/28 계획 / 10/24 선행

## 범위·실제 구현
- GitHub: hibi89/hibi89-kic-proofinvest lead/kic, 코드 b9d3d9ff12e4a7151b8efaed4acc203d34b84752. 실제 외부 OpenDART API 호출·계정인증·파일 업로드·운영 배포 없음.
- 신규 streamlit_app.py, proofinvest/offline_view.py, requirements-ui.txt, tests/test_streamlit_ui.py. README와 CI 작업 변경.
- 버전관리 중인 fixtures/synthetic_annual.json 하나만 읽는 read-only 화면. 재무행 CFS/OFS, 합성 매출증가 산술 검증, 시연용 부채/자본 비율 표시. 외부 원본 미인증, 합성/투자 권고 아님을 화면에 명시.
- A안 CLI 파일 출력만 유지(실제 UI 미검증), B안 Streamlit 실제 UI + AppTest 헤드리스 검사 채택. Core CLI Python3.10+ 외부 무의존 유지, 선택 UI Python3.11+.
- 실행: python -m pip install -r requirements-ui.txt ; python -m streamlit run streamlit_app.py. 선택 Streamlit >=1.66.0,<1.67.0.
- 이 화면에는 외부 데이터 선택/실계정/비밀키/원문 링크/DAKER 제출 버튼이 없음. 저장·재조회 캐시는 11/30 별도 과제.

## 검증/실패 이력
- 최초 UI 코드 bd423a0656f84deed24895ea9b9c290572845bb1: CI #40085201505에서 새 테스트 3 ERROR (PosixPath 인스턴스 메서드 직접 모킹 2건, Streamlit warning .message 접근 1건).
- 교정 코드 b9d3d9ff12e4a7151b8efaed4acc203d34b84752: fake fixture 모듈 binding으로 모킹, warning .value 참조.
- 최종 CI https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40085362379 SUCCESS, Python unittest 135/135 PASS, Streamlit AppTest.from_file 실제 헤드리스 렌더/경고/미인증 검사 PASS, master progress 2종·합성 및 수동 근거 offline CLI PASS.
- Headless 검증은 실제 브라우저 스크린샷/수동 접근성 검사/배포가 아님. Streamlit 공식 AppTest https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest 참조.

## 차단·인계·날짜별 점수
- 11/28 업무 100/100 DONE: 설계20, 화면35, 테스트/CI35, 인계10. 남은 기본0h+예비0h, 실제 소요 미계측. 정본 26 DONE/3 BLOCKED/31 NOT_STARTED.
- P0 통합 총괄 19:12 KST 지시 ACCEPTED / BLOCKED_EXTERNAL. DAKER 실계정 참가유형, 개인/팀 및 팀장, 최종 1개 PDF 업로드 권한·버튼 확인 필요. 인증 및 제출 승인은 사용자 직접. 공개 GitHub에 frozen 비공개 PDF/PPTX/6백업 업로드·디자인 변경 금지.
- 사용자 DAKER 브라우저 로그인 → KIC 참가 유형/팀장 표시 확인 → 최종 제안서 PDF 한 파일 제출 페이지의 권한/형식/제출 버튼 확인 → 승인 전 실제 제출·계정변경 금지. 비밀번호/토큰/세션·민감 PDF 내용은 요구하지 않음.
- P0 DAKER 10/25·11/09 각60% BLOCKED, 공식 11/10 제출 미착수, P1 DART 10/30 공식 원문90% BLOCKED. 11/18·19 평가 및 11/22·29 예비일 NOT_STARTED 그대로.
- NEXT 11/30 저장/재조회 1경로, 0/100 기본1h+예비2h=3h. 11/29 예비일은 미사용 미완료. 이전 HEAD baa86739d45f286a9ecad83cb1c41466267e1b62로 Git revert 가능.
