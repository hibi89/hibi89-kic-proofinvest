# ProofInvest KIC: 심사위원용 판단 근거 요약 계약 (2026-10-30)

## 목표

저장된 SEC **형식**의 로컬 ZIP에 대해 실제로 검증된 범위만 설명하는 **결정 요약(Decision Brief)**을 만드는 것이 이번 작업의 목적이다. 실제 SEC 진본 여부, 수집 시각, 저작/재배포 권리, 투자 성과, 위험 점수는 독립 인증되지 않았다.

`proofinvest/decision_brief.py`는 데이터/저장 경로/사용자 텍스트를 자유형 문장으로 옮기지 않는다. **고정된 허용 문구**와 교차 검증된 내부 코드만 이용한다.

## 출력의 4단계

1. **판정:** 내부 계산이 일치하지만 출처 미인증이면 `HOLD`, 주장과 로컬 재계산이 충돌하면 `REJECT`. `APPROVE`는 불허
2. **검증 범위:** 로컬 ZIP 3원문 SHA, 해당 ZIP의 산술 재계산, 로컬 위험 검토, SQLite 감사 이벤트의 정확한 근거 해시 결합
3. **미인증 범위:** 발행기관 SEC 원본, 수집시각 실증, 콘텐츠 재배포 권리, 재무/기간/단위의 독립 인증, 외부 고정 감사 로그
4. **담당자 후속 작업:** 공식 원본/권리 검증, 회계 주장 충돌 조정, 위험 누락 항목 점검, iXBRL 기간/단위 및 원문 숫자 확인 중 **실제 근거 상태로 필요한 작업만**

## 데이터 계약

- JSON 보고서의 `decision_brief.schema = proofinvest.archived-decision-brief.v1`
- `decision_brief.decision`은 `guard.decision`, `verification.status`, `audit.bound_guard_decision`과 일치
- `decision_brief.priority`는 `review_summary.review_priority`와 일치
- `next_actions`는 후속 검토 코드의 화이트리스트와 일치, 충돌 없을 때 주장의 재검토를 강제로 추가하지 않음
- `audit.verified_against_persisted_request = true` 및 근거 SHA 일치가 있어야 요약 생성 가능
- Markdown 렌더러는 **요약을 독립 재생성 후 원본과 동일함을 확인**, 불일치 시 출력/다운로드 중단
- Streamlit UI도 동일한 검증을 사용. 요약은 기술용 SHA 테이블보다 위에 표시됨

## 검증

`tests/test_kic_decision_brief.py`는 합성 로컬 HOLD/REJECT, 원문 경로/HTML 내용 누출 방지, 허위 인증·허위 우선순위·허위 후속 작업·임의 문구 삽입 탐지, 사람 검토의 비승인 상태를 검증한다. CI는 Linux 전체 테스트와 Windows 오프라인 SQLite/AppTest를 모두 수행한다.

## 명시적 미완료

현재 결과는 **합성 및 이용자 로컬 자료의 오프라인 검증**이며 심사위원에게 실제 공시를 인증했다고 주장해서는 안 된다. 전체 프론트엔드/브랜드/공식 10쪽 PDF 디자인은 사용자 기준으로 전면 재설계가 남았다. V7 PDF는 내부 콘텐츠 초안이고 공식 제출 금지. 디자인 개선은 기능 안정성·콘텐츠 품질 이후 수행한다.
