# KIC 12월 2일 대비 코드·데모 점검 및 복원 백업 (10월 24일 선행)

## 구현·선택
- KIC ProofInvest lead/kic, 코드 SHA b1297a45e8cb29fe814cd7ce719e250a4fbbf96e. 원래 2026-12-02 예정, 실제 2026-10-24 KST 선행.
- 기존 표준 라이브러리 CLI/Streamlit 헤드리스/합성 스냅샷은 검증됐으나 타 환경 복원 가능한 고정 파일 목록 아카이브 및 신설 디렉터리 CLI 복원이 없었다. 공식 선정/DAKER 계정 인증이 필요한 업무와 분리해 독립 수행.
- A: GitHub 코드만 믿고 README의 명령 문서화(실제 복원 검증 없음). B: 엄격한 allowlist 아카이브 + 각 파일 SHA-256 manifest + CI 신규 경로 복원·CLI 테스트 + 공개 합성 ZIP 아티팩트 백업(채택).
- 신규 scripts/synthetic_demo_bundle.py, tests/test_synthetic_demo_bundle.py, docs/DEMO_OFFLINE_RESTORE.md, CI workflow. 허용 파일14개: Python 소스, streamlit_app.py, requirements-ui.txt, README.md, fixtures/synthetic_annual.json. 비공개 10p PDF/PPTX, 사용자 Private Library 파일, DB·캐시·토큰·.env·계정 정보는 **포함하지 않음**.
- 아카이브는 고정 ZIP 타임스탬프/정렬/명확한 FILES manifest로 재현 가능. 검증 시 중복/추가 파일·상위 디렉터리 경로·심볼릭 링크·체크섬 불일치 거절. 빈 추출 디렉터리 외 덮어쓰기 금지. SHA는 파일 손상 탐지이며 실제 DART 원문 인증이 아님.
- 사용: python scripts/synthetic_demo_bundle.py build /tmp/proofinvest-synthetic-demo.zip ; verify ; extract /tmp/proofinvest-synthetic-demo.zip /tmp/proofinvest-restore-fresh ; 복원 경로에서 python -m proofinvest --claim-revenue-growth-pct 20 후 python -m proofinvest.snapshot_store --save/--read. 로컬 PC 별도 실행 강요 없음.

## 실제 테스트 및 GitHub 백업
- 신규 회귀 6개: 동일 입력 ZIP byte-for-byte 결정성, 공개 가상자료 allowlist, checksum 위조/변조, ../private.pdf 같은 archive 경로 유출 차단, 신규 경로 추출 후 표준 라이브러리 CLI 실행, 기존 대상 폴더 덮어쓰기 거부.
- 첫 코드 SHA 6807e9dc16c9d610cf716d8647186eb185c652ec, CI #40088761217: 테스트 총155 중 1 FAIL(합성 fixture 원문에 원래 존재하지 않는 SYNTHETIC_FIXTURE 문자열을 검증한 **테스트 가정 오류**). 실제 fixture JSON 구조 및 manifest source_kind를 검증하도록 테스트 수정, 코드/실제 경로 검증 약화 없음.
- 수정 SHA b1297a45e8cb29fe814cd7ce719e250a4fbbf96e, [GitHub Actions #40088827748](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40088827748) SUCCESS **155/155 PASS**. progress 검증 2종·Streamlit headless AppTest·snapshot CLI·synthetic 및 수동실공시 기재 오프라인 CLI 모두 PASS.
- 동일 CI에서 archive build→verify 14개 공개 파일→새 임시 디렉터리 extract→복원 위치에서 python -m proofinvest 실행→별도 HOME에 save/read 실행 성공. 실행 로그 CREATED_PUBLIC_SYNTHETIC_ARCHIVE / VERIFIED_PUBLIC_SYNTHETIC_ARCHIVE 14 / EXTRACTED_VERIFIED_SYNTHETIC_ARCHIVE.
- GitHub Actions **실제 업로드 아티팩트 ID 12558286763** 이름 proofinvest-synthetic-demo-recovery, ZIP 크기 GitHub 보고 약 26,504 bytes, 보존기간 14일 설정. 다운로드는 성공한 GitHub Actions run UI에서, 다운로드/유효기간은 GitHub 권한·유지 정책에 따름. 아티팩트의 ZIP은 공개 합성 코드/fixture만, 공식 제출 파일 백업과는 별개.
- 비공개 10페이지 PDF/PPTX/Private Library 6개 백업에 **이번 작업으로 어떤 변경도 가하지 않음**. 원래 이력 유지. Git에 원본 업로드 없음, main/feature/force push 없음.
- 미검증: 실제 브라우저 육안, Windows 실PC에서 복원, 운영 배포, 실 DART 원본 진위/원문 사용권, Agent E2E, DAKER 실제 팀장·업로드 권한, DAKER 최종 접수. CI 아티팩트와 합성 복원 성공만 인정.

## 점수·다음 조건·P0
- 원래 12/02 날짜 과제 **100/100 DONE**: 코드/데모 복원 범위20, allowlist+checksum 구현35, 단위6+복원 CLI+CI 아티팩트35, 진행정본/QA/총괄10. 해당 과제 잔여 기본0h+예비0h, 실제 소요시간 미계측. 60일 원장 **29 DONE / 3 BLOCKED / 28 NOT_STARTED** (제품 완성도와 다름).
- 통합 총괄 P0 지시 ACCEPTED/BLOCKED_EXTERNAL: DAKER 10/25·11/09 실제 개인/팀 참가자·팀장 최종 PDF 업로드 권한 각60% BLOCKED, 사용자 본인의 DAKER 브라우저 로그인·권한/단일 PDF 버튼 확인 필요. 11/10 내부 제출 및 공식 접수 영수증 NOT_STARTED, 11/12 공식 예선 마감은 사용자 실계정 승인 의존. 사용자 허가 없이 팀 변경/업로드/제출 금지.
- DART 10/30 공식 뷰어 접수번호 대조 90% BLOCKED, 11/18·19 상호평가 결과/영수증·11/22·29 예비일 NOT_STARTED 유지. 해당 과제 완료가 외부 블로커를 해결한 건 아님.
- 다음 포인터 **2026-12-03** 10:00 본선 결과 실제 확인 및 일정 전면 재산정, 0/100 기본0.5h+예비2.5h=3h. **2026-10-24 현재 공식 발표가 아직 발생하지 않았으므로 즉시 실행 가능한 개발과제가 아니라 미래 이벤트 대기**. 선정 여부·MVP 의무·일정 모두 사전 확정 금지.
- 원복 기준 이전 remote SHA 6e0a896b19154b41a1197b7420f2cb43e7d53a70. 최신 docs/head SHA는 다음 성공 CI로 확인.
