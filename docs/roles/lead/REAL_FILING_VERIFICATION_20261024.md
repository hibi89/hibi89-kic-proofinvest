# KIC ProofInvest — 실제 기업 공시자료 2개년 매출 수동 검산 영수증
> 2026-10-24 14:13:38 KST | 사용자 확정 예선 실증 10/30 작업의 **10/24 선행 착수**, `lead/kic` | 자동 OpenDART API **미호출**, 실제 DART 원문 화면 **미열람**.

## 실제 재무제표에서 직접 대조한 값

**기업:** 삼성전자주식회사 및 종속기업 (Samsung Electronics Co., Ltd. and its subsidiaries). **기준:** 연결 손익계산서(CFS), 한국 원화, **단위 백만원**, 전기/당기 모두 1월 1일~12월 31일의 연간 수치.

| 항목 | 2024년 | 2023년 |
|---|---:|---:|
| 연결 매출액 (백만원) | **300,870,903** | **258,935,494** |
| 적용 기간 | 2024-01-01~2024-12-31 | 2023-01-01~2023-12-31 |

- **1차 원본**: 삼성전자 공식 배포 [FY2024 연결재무제표 및 독립감사인 보고서](https://images.samsung.com/is/content/samsung/assets/global/ir/docs/2025_SEC_Consolidated_Financial_statements.pdf), **PDF 9쪽(내부 표기 7쪽)**, `CONSOLIDATED STATEMENTS OF PROFIT OR LOSS`. 실제 페이지를 렌더링해 매출액 행·2024/2023 열·KRW 백만원 단위 확인.
- **발행기관의 별도 사업보고서 게시**: [삼성전자 공식 2024 Business Report (2025-04-30 게시)](https://www.samsung.com/global/ir/reports-disclosures/public-disclosure-view.84359/). 사업보고서 PDF 자체는 도구 파일크기 제한으로 **본문 미열람**; 매출 수치의 실제 원문 검증은 위 **연결감사 재무제표 PDF**에서 수행.
- **DART 사업보고서 접수번호 후보:** `20250311001085` → [DART 공개 뷰어 주소](https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20250311001085). [별도 공개 색인](https://www.flashmemory.co.kr/companies/samsung/)의 연결공시 경로와 대조했지만 **이 환경의 DART 뷰어가 502 오류여서 접수번호↔사업보고서 원문을 직접 확인하지 못함**. 따라서 DART 원본 재확인은 `BLOCKED`이며 '공식 DART 접수 검증 완료'라고 표시하지 않음.

## Python Decimal 재현 계산

```python
from decimal import Decimal
current=Decimal("300870903")  # 2024 revenue, millions of KRW
previous=Decimal("258935494") # 2023 revenue, millions of KRW
delta=current-previous         # 41935409, millions of KRW
growth=(delta/previous*100).quantize(Decimal("0.01")) # 16.20%
```

- **매출액 순증가:** `41,935,409`백만원 = `41.935409`조원.
- **전년 대비 매출 증가율:** **+16.20%** (반올림, Decimal; 원문에 이 퍼센트가 인쇄됐다고 주장하지 않음).
- 기획서에는 '실제 삼성전자 연결 재무 원문 금액의 **수동 검산 증거**'로만 사용. 전체 ProofInvest 자동 연동·실 API 검증 성공으로 표현하지 않음.

## 재현 및 경계

- 기계 판독 가능한 최소 숫자/메타데이터 영수증: [samsung_2024_cfs_revenue.json](../evidence/samsung_2024_cfs_revenue.json).
- 합성 테스트/오프라인 자체 검산: `python -m unittest discover -s tests -v`. 숫자는 실제 공개된 금액을 사람이 옮긴 것이므로 출처 `MANUAL_PRIMARY_SOURCE_VERIFICATION`이며, 기존 `SYNTHETIC_FIXTURE`나 인증된 OpenDART 실 API 응답으로 분류하지 않는다.
- 원본 삼성 PDF의 원문 전체/스크린샷은 저장소에 복제하지 않음. 공개된 두 수치와 출처 메타데이터만 보존. 정정공시/최신년도 실적/공시 이용 약관은 별도 확인.
- 최종 DART 원문 대조 후에만 10/30 작업의 미완료 게이트 해제. 다음 11/02은 이 수동 영수증을 실제/틀린 주장/출처 미확인 Agent 시나리오에 **출처 진실성과 모델 출력을 구분해** 연결한다.

## 당일 100점 게이트

| 게이트 | 배점 | 현재 |
|---|---:|---|
| 공식 회사 원본 재무제표·연결/연간 기준 확인 | 20 | 20 |
| 2개년 원문 매출·단위·기간 비교 | 30 | 30 |
| Decimal 수동 검산·재현 가능 최소 JSON 기록 | 25 | 25 |
| 오프라인 회귀 테스트와 GitHub CI 검증 | 15 | **15** — [44/44 PASS](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40065436892) |
| DART 접수번호의 공식 뷰어 원문 직접 대조 | 10 | **0 BLOCKED** |
| **합계** | **100** | **최종 90/100=90% (DART 원문 뷰어 10점 차단)** |

**CI PASS로 90/100=90% 확정. 남은 DART 뷰어 10점은 인증·서버 접근 전제로 보수적 순작업 0.5h+예비 1h=최대 1.5h 추정**, 실제 서버 장애 대기시간 미지수. 실제 AI 수행 시간 **미계측**. 기존 10/25 DAKER 제출 접근 35%/예상 3h 차단은 별도.
## 2026-10-24 14:14:47 KST — 10/30 실제 공시 검산 CI 검증 완료 (90/100=90%)
- 삼성전자 발행 PDF 원본을 시각 대조한 **2024·2023 연결매출 300,870,903 / 258,935,494백만원**, `Decimal` 직접 검산 증감 **+41,935,409백만원, +16.20%**.
- GitHub Actions [40065436892](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40065436892), job `120787584893`, **44개 테스트 PASS**, 오프라인 합성 데모 PASS. 직접 컴파일/검증된 코드는 `916ac66eec7eb36669a477c22af4f54d5295bd13`. CI 영수증은 공시 원문 진위의 자동 재검증을 뜻하지 않으며 공개 원문은 작업자가 육안 확인.
- 10/30 가중 게이트: 발행자 연결재무 PDF 20/20, 연도·금액·단위 30/30, Decimal 재현 JSON 25/25, CI 15/15, DART 접수번호 공식 뷰어 직접 대조 **0/10 (502 접근 차단)** → **90/100=90%**.
- 남은 실제 업무: DART `20250311001085` 해당 기업 2024 사업보고서 원문 직접 열람 및 메타데이터 대조. 접근 가능한 이후 예상 순작업 **0.5h+접근·오류 예비 1h=상한 1.5h**, 서버 오류 대기시간 미지수. 실제 소요시간 **미계측**.
- 다른 날짜 작업은 별도: 10/24 계획 100%, 10/28 중복계정 100%, 10/29 기간·CFS/OFS 100%, 10/25 DAKER 제출권한/공식 PPTX **35%**(접근 시 추가 약 3h). 다음 11/02은 이미 확보된 실증 출처를 이용한 `verified/conflict/unavailable` 시나리오 구축. 신규 실 API/유료 호출 없음.
