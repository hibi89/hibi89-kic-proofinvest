> **2026-10-24 추가 검증:** 공개 ZIP은 여전히 합성 데이터만 포함합니다. `streamlit_app.py`는 원본 저장소에서만 삼성전자 수동검산 옵션을 노출하고, 합성 전용 ZIP을 복원한 별도 폴더에서는 합성 옵션만 표시합니다. [CI 40099102467](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40099102467)에서 **별도 subprocess Streamlit AppTest**로 복원 앱을 실행해 오류가 없음을 확인했습니다. 실제 브라우저/Production 검증은 하지 않았습니다. [상세](roles/lead/MANUAL_ISSUER_STREAMLIT_UI_QA_20261024.md).

# KIC ProofInvest — 공개 합성 데모 복원 절차

이 경로는 **코드와 합성 fixture의 재현 가능한 CI 백업**을 위한 것이다. 실제 DAKER 제출 PDF/PPTX, 비공개 Library 원본, 실제 기업 공시, 로그인/인증 정보는 백업에 포함하지 않는다.

## 재현 가능한 백업

저장소 `lead/kic` GitHub Actions `offline-tests` 성공 실행에서 `proofinvest-synthetic-demo-recovery` 아티팩트를 받을 수 있다. 공개 소스/가상 fixture만 포함한다. 아티팩트 보존기간은 CI 설정을 따르며 영구 저장 보장은 아니다. 소스 자체는 Git 커밋으로 이력을 보존한다.

로컬 Python 3.10 이상:

```bash
python scripts/synthetic_demo_bundle.py build /tmp/proofinvest-synthetic-demo.zip
python scripts/synthetic_demo_bundle.py verify /tmp/proofinvest-synthetic-demo.zip
python scripts/synthetic_demo_bundle.py extract /tmp/proofinvest-synthetic-demo.zip /tmp/proofinvest-restore-fresh
cd /tmp/proofinvest-restore-fresh
python -m proofinvest --claim-revenue-growth-pct 20
python -m proofinvest.snapshot_store --save
python -m proofinvest.snapshot_store --read
```

윈도우에서는 `/tmp` 경로 대신 사용자가 지정한 빈 로컬 폴더를 사용한다. 추출 대상 폴더는 **존재하지 않아야** 하며 기존 자료 덮어쓰기를 하지 않는다. `--save`는 사용자 홈 아래 합성 캐시에만 기록한다. Streamlit UI는 `pip install -r requirements-ui.txt` 이후 `python -m streamlit run streamlit_app.py`으로 로컬 구동할 수 있지만 실제 브라우저/운영 배포 검증에 포함되지 않는다.

아카이브의 `SYNTHETIC_DEMO_MANIFEST.json`은 정확히 허용된 공개 코드/합성 파일만 묶는다. 모든 SHA-256과 파일 크기를 확인하고 아카이브 내 임의 경로, 중복 경로, 링크 및 예상 외 바이너리를 거부한다. 이것은 **실공시 진실성·법적 권리·독립 감사·실제 제출 승인**을 보증하지 않는다.

## 외부 차단

- P0 DAKER: 사용자 본인이 로그인해 KIC 개인/팀 참가 형태, 팀장 권한 및 단일 최종 PDF 제출 버튼/파일 양식을 확인해야 한다. 비밀번호·쿠키·세션 키 요구 없음. 최종 제출 또는 팀 상태 변경은 명시 승인 전 진행 금지.
- P1 공식 DART 접수번호 원문 대조는 실제 열람 근거가 없어 차단 상태다.
- 12월 3일 선발 결과 확인은 실제 공식 발표 이후에만 수행한다.
