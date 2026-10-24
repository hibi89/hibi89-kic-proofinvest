# ProofInvest PDF 10쪽 전수 팩트·구현 경계 검수
> KIC-PDF-FACT-20261106; 원래 계획 2026-11-06, 실제 선행 2026-10-24. `lead/kic`. 공개 GitHub에는 개인정보 포함 원본 기획서 바이너리를 올리지 않음.

## 확인한 근거
- [KIC/DAKER 공식 대회 규정](https://daker.ai/public/hackathons/kic-ai-agent-competition): 예선 제공 양식 기반 PDF 10페이지 이내, Summary·문제 정의·서비스 제안·Agent 구성·데이터·MVP·기대효과 7개 필수 항목, **2026-11-12 10:00 KST** 마감. 사용자 보관 PPTX와 실제 PDF는 **10장/10쪽** 및 7항목 충족.
- [삼성전자 FY2024 연결감사 재무제표 PDF](https://images.samsung.com/is/content/samsung/assets/global/ir/docs/2025_SEC_Consolidated_Financial_statements.pdf) PDF 페이지 인덱스 8(인쇄 7쪽), 연결 손익계산서 Revenue (KRW 백만원) **2024 300,870,903 / 2023 258,935,494** 직접 재대조. `Decimal((300870903-258935494)/258935494*100).quantize(0.01)=16.20%`. 제안서 30%는 공식 실적 주장이 아니라 **검산 대상인 가상 반례**. DART 공식 접수번호 뷰어 대조는 별도 **90% BLOCKED**, 검증 성공 주장 금지.
- 오프라인 `proofinvest` Research/Verification/Risk 구현 상태와 기존 [CI 40074125319](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40074125319) 82개 Python unittest PASS, 합성/수동 공시데이터 CLI PASS. 단, 자동 Agent orchestration·LLM·웹 UI·Production 및 인증된 OpenDART 실수집 **미구현/미검증**. 원문 데이터 사용권/외부 API 재전송도 별도 조건 확인 필수.
- 9쪽 효과지표(처리시간, 추적률, 근거 없는 verified 0건)는 미래 **측정 목표**일 뿐 실측 결과 아님. 10쪽 출처 링크 4개(KIC 공식, 삼성전자, [금감원 OpenDART](https://opendart.fss.or.kr/intro/main.do), GitHub) 확인. AI 문안/설계 지원 및 참가자 책임을 구분.

## 발견·수정한 오류 2건
1. **1쪽 표지**: 전체 PPTX/PDF v1인데 v0.2로 남은 과거 버전 표시 → **v1 사실검수본**으로 수정.
2. **5쪽 Agent Workflow**: “4·5번 오프라인 검증 완료”를 실제 Agent Tool 통합 완료로 오해할 위험 → **“4·5번 오프라인 핵심함수 검증 완료. Agent 자동 연결 및 실 API 호출은 미구현.”**으로 변경.

## 실제 QA·보존 검증
- 비공개 사용자 Library의 v0.4 원본 PPTX/PDF 2개를 현재 세션에서 내려받아 직접 열람. python-pptx로 원본 사본에서 **1쪽/5쪽 텍스트 런 2개만** 수정; 기타 페이지의 PPTX 텍스트 그대로.
- LibreOffice PDF 변환 결과 **10장/10쪽**, 2·3·4·6·7·8·9쪽은 이전 PDF와 **픽셀 완전 일치**, 10쪽은 링크 렌더 차이 **316/2,630,394 색채널(약 0.012%)**만 달라 텍스트/링크/배치 불변 확인. 모든 페이지 text bbox 내부, PDF 하이퍼링크 4개 PASS. 변경한 1·5쪽과 10쪽 이미지를 직접 검토해 잘림 미발견.
- 새 PPTX/PDF를 **개인 Library** `/KIC ProofInvest/Private Drafts/`에 새 버전으로 각각 업로드 성공, 재다운로드 파일로 **SHA256 실제 검증**. 이전 원본 2개 포함 **영구보존 총 4개**. 공개 GitHub에는 민감 원본 미업로드. 실제 DAKER 참가 형태/팀장 제출권한 및 최종 제출 영수증 없음.
- `KIC_ProofInvest_v1_factchecked_20261024.pptx`: **122,787 B**, SHA256 `751da2379801691f2e3a1b6e865e3d9e7c6f2dde727bbb371d99988e55eae76d`.
- `KIC_ProofInvest_v1_factchecked_20261024.pdf`: **513,113 B**, SHA256 `0bdbbf04f374a7ccb39cd15e1aa700a006514278b094d32bb05ac7db610e034e`. PDF 변환 재실행 시 바이트는 달라질 수 있어 **Library 실제 스냅샷 해시**를 정본으로 표시.

## 11/06 일일 완료 100점
| 조건 | 가중치 | 확인 |
|---|---:|---:|
| 공식 규정/필수 7항목·10쪽·마감 확인 | 15 | 15 |
| 실제 삼성전자 원문·Decimal 16.20%·코드/실측 경계·AI 고지 검토 | 35 | 35 |
| 표지/Agent 구현 오해 2건 수정 | 20 | 20 |
| PPTX/PDF 재출력·10쪽 QA·Private Library 2건 추가 보존 | 20 | 20 |
| 60일 정본·중앙/상위 인수인계·GitHub CI 확인 | 10 | 10 |
| **계획 11/06 업무만** | **100** | **100/100** |

- 실제 선행 수행 2026-10-24, **잔여 기본0h+검수 예비0h=0h, 실투입 미계측**. 원래 계획 기본1.5h+예비3.5h=5h는 실제 소요시간이 아님.
- 별도 10/25 DAKER 최종제출 권한 **60/100 BLOCKED**(접근 후 기본0.5h+예비1.5h=2h), 10/30 DART 공식 뷰어 **90/100 BLOCKED**(접근 후 기본0.5h+예비1h=1.5h) 그대로. 임의 완료 처리 금지.
- **다음 2026-11-07 READY**: PDF 전체 10쪽 최종 시각 품질·이미지·링크·폰트·페이지 QA, 시작 0/100, 기본1.5h+예비3.5h=5h. 11/08 최종 동결 / 11/09 계정 접근 / 11/10 조기접수 목표, 11/12 10:00 KST 공식 마감 유지. 사용자의 승인 없이 공식 제출 금지.
