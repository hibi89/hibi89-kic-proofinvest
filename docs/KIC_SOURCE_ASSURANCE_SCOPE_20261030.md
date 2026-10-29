# KIC 출처·권리·수집시각 검증 경계 — 로컬 3원문 ZIP (2026-10-30)

## 판정 원칙

사용자가 로컬에 보관한 SEC **형식** ZIP에 저장된 URL, CIK, 접수번호, 수집시각, HTTP 요청 횟수, SHA-256 및 이용 권한 문구는 모두 **제출자 스스로 기록한 메타데이터**다. 이들이 정합적이라는 이유만으로 **SEC 제공기관 서명·출처 인증·적법한 재배포 라이선스·실제 발행시점**을 주장하지 않는다.

`proofinvest/source_assurance.py`는 `replay_local_capture()`의 **해시 일치 결과**와 출처 인증 부재를 확인하고 아래 고정 범위만 발급한다.

| 단계 | 로컬 판단 | 독립 인증 |
|---|---|---|
| ZIP 3개 원문 SHA-256 | 로컬 파일 무결성 `LOCAL_MATCH` | SEC 원본 증명 아님 |
| 발행기관·기업·접수번호 | 자기신고 메타데이터 | `NOT_ATTESTED` |
| 최초 수집시각·공시 당시 가용성 | ZIP 기록 시각 | `SELF_REPORTED_ONLY` |
| 원문 이용·재배포 권리 | 법무/라이선스 근거 없음 | `NOT_VERIFIED` |
| 재무 사실 | 로컬 숫자 계산 | `NOT_ATTESTED` |
| 감사 불변성 | 로컬 SQLite 해시 체인 | 외부 고정 `NOT_PRESENT` |

## 기능 적용

- `proofinvest.archived_sec_guard_report.run_archived_sec_guard_report`: **Guard/SQLite 쓰기 전에** 출처/권리 검증 범위가 비정상적으로 승격되지 않았는지 검사
- `decision_brief`: 보고서 판정과 함께 출처·권리·외부 공시 인증 미확인을 재검증
- `render_archived_sec_guard_markdown`: 판정 요약과 출처·재배포 제한을 출력하기 전에 증빙 범위 자체의 변조 여부를 독립 재검사
- `archived_sec_guard_ui`: 화면과 JSON 내보내기에 동일한 출처 게이트를 표시하고 위조된 재배포 허용이나 인증 완료 상태이면 결과/내보내기를 차단
- `tests/test_kic_source_assurance.py`: 합성 HOLD/REJECT, 출처·권리 허위 인증, 변조 해시, 허위 라이선스·수집시각, 사전 감사 DB 미생성 및 독립 복사본 안전성 검증
- Linux Python 전체 검사 / Windows 실제 SQLite+Streamlit 테스트 / Chromium 사용성 검사

**중요:** `software_scope_not_legal_permission`은 소프트웨어가 내부로 제한한 기능을 설명할 뿐 **이용허락이나 법률 자문이 아니다**. 원문 공개·재배포·투자 모델의 인증된 데이터 입력·실거래·주최 측 제출은 현재 경로에서 수행하거나 허용하지 않는다. 파생된 해시·상태 요약은 로컬 내부 사람 검토에 한정된다.

## 다음 단계의 외부 출처 검증 조건

실제 SEC 공시를 인증하려면 **공식 원본과의 독립 대조, 시점별 수집 증빙, 상이한 수정/정정 공시의 시점별 구분, 해당 자료의 사용·배포 권리 검토**를 별도로 설계하고 수행해야 한다. 인증되지 않은 ZIP에 사람이 `VERIFIED`라고 적는 입력을 허용하거나 기존 데이터의 인증 상태를 덮어쓰는 기능은 추가하지 않는다.

외부 SEC API, 주문, 원문 공개/업로드, DAKER 대회 제출은 실행하지 않았다. 디자인 변경은 내용·백엔드 안정화 후 별도 전면 재설계한다.
