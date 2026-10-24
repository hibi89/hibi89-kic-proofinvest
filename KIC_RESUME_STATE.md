# KIC ProofInvest — 단일 새 채팅 복원 기준 (LIVE SNAPSHOT)
> 스냅샷 2026-10-24 14:39:37 KST KST. 저장소 `hibi89/hibi89-kic-proofinvest`, 코드·업무의 단일 활성 브랜치 `lead/kic`. **채팅 대화·과거 HANDOFF보다 GitHub 최신 원격 HEAD와 이 문서의 최신본을 우선한다. 이 문서의 SHA는 스냅샷 증거이지 영구 고정 HEAD가 아니다.**

## 사용자가 입력하는 것은 단 한 줄
`[kic 해커톤 깃헙 레포지토리 확인하고 작업하셈]`

새 KIC 총괄은 별도의 복원 프롬프트, 사용자 설명, 복사본, 확인 질문 없이 GitHub 연결을 통해 이 저장소의 `lead/kic` 최신 HEAD를 조회하고 [CHAT_BOOTSTRAP.md](CHAT_BOOTSTRAP.md)에 기재된 **실제 개발 재개 절차**를 실행한다. **KIC 총괄 = 같은 채팅의 설계자+개발자+테스터+검수자**. 상위 3대회 총괄이나 옛 작업자 READY는 아니다.

## 최근 신뢰 가능한 검사 영수증
- 최신 업무 증거: `lead/kic`에서 Risk verified-only 안전입력 기능 `proofinvest/risk.py` + `tests/test_risk.py` 구현(최종 코드 SHA `5f05a0bb237ebfbe4837a21c2aaa37fb276a82b9`). [GitHub Actions 40066732288](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40066732288) 는 인수 기록 반영 후까지 포함한 **67/67 단위테스트 + 기존 합성 CLI + 실기업 수동기록 CLI 성공**. 구체 로그 확인은 해당 run 참조.
- 10/24 계획표 등록 **100%**; 10/26 Research 소스 검수 **100%**, 10/27 Research `lead/kic` 이관 **100%**; 10/28 중복 재무계정 보호 **100%**, 10/29 기간·CFS/OFS 혼합 차단 **100%**, 10/31 Risk verified-only 입력 게이트 **100%**, 11/02 삼성 수동증거 `verified/conflict/unavailable` 3상태 실행 **100%**. 모두 **각기 다른 원래 날짜의 100점 작업 단위**를 10/24에 선행 완료한 것. 실제 수행 시간은 **미계측**.
- 10/30 실제 기업 2년 연결매출 검산은 **90%**: 삼성전자 발행 연결 감사재무제표 FY2024 **300,870,903백만원**, FY2023 **258,935,494백만원**, 전년 성장 **16.20%**(수동/Decimal); **DART 접수번호를 공식 뷰어에서 직접 대조하는 10점은 502 오류로 BLOCKED**. 인증된 OpenDART API 수집이라고 말하면 안 됨.
- 10/25 DAKER 공식 PDF 양식·실 계정 제출권한 확인 **35%**: 공개 규정/사용자 기존 10쪽 초안 직접 점검 35점, 실제 참가 형태·팀장 제출권한 40점 및 공식 PPTX 원본 25점은 **BLOCKED**. 팀 전환/최종 제출 조작한 적 없음.
- 현재 **총 67개 테스트 PASS**는 `lead/kic` *오프라인* 테스트 결과이며 **실 서비스, 공식 문서 원본 인증, 자동 에이전트 전체 구현, 공식 DAKER 접수 성공을 뜻하지 않는다**. `main`에는 아직 전체 개발코드를 통합하지 않았다.

## 다음 `ㄱ` 또는 위 고정 한 줄 입력 시 바로 수행할 단일 개발 작업
**11/01 예정 Risk 결측·0분모·음수자본 fail-closed 검증/안전 계산 (선행 실행 가능, 현재 미착수 0%)**.
1. `proofinvest/risk.py`의 `gate_verified_risk_inputs`(입력 자격 확인만 수행) 및 `tests/test_risk.py`의 마지막 검증 근거 읽기.
2. 검증 실패한 수치는 Risk로 넘기지 않는다. 입력이 적격인 경우에도 **결측/0분모/음수자본의 계산 보류 조건**과 설명을 결정론적 Python `Decimal`로 구현·테스트한다. 추론 기반 금융 수치 생성/투자 권고 불가.
3. 기존 `proofinvest/engine.py`의 합성 시연용 `calculate`는 새 Risk 게이트를 **통과하지 않는 옛 경로**이다. 기존 테스트를 부수지 않으면서 새 `verified-only → safe calculation` 경로를 명확히 검증하고, `main` 반영 및 실사용 인증은 별도 게이트.
4. 신규 결측/0·음수자본 테스트, 전체 오프라인 unittest/두 CLI를 GitHub Actions로 실제 실행·확인한다. 테스트 실패는 기록하고 수정한다. CI 전 100%로 보고하지 않는다.
5. 11/01 하루 기본 **1.5h + 오류·검수 예비 3.5h = 보수적 최대 5h**(예측, 실제 수행시간 미계측). 해당 작업 100점 검증 게이트를 착수 전에 기록하고 작업 종료 때 **획득점수/100 · 완료율% · 남은 순작업 h + 예비 h · 실제 투입 미계측 여부**를 공시한다.

## 외부 차단 회수 목표
- **10/25~26 DAKER 접근 회수**: 기존 35%에서 재개, 남은 순작업 약 1h+예비 2h=접근 후 최대 3h. 실제 DAKER 로그인·PPTX 원본 없으면 **불가**, 선행 Risk는 진행 가능.
- **10/27 DART 접수번호 원문 회수**: 기존 90%에서 재개, 남은 순작업 약 0.5h+예비 1h=접근 후 최대 1.5h. 뷰어 502면 BLOCKED 보존하고 11/06 PDF 사실검수에서 미검증 표시.
- **11/03~08** 공식 양식 준수 10쪽 이하 PDF 정리·검수·동결; **11/09** 제출권한 최종 확인; **11/10** 사용자 승인 하 조기 최종 제출, **11/12 10:00 KST** 공식 마감. 11/11 장애 예비일. 마감 일정 임의 변경 금지.

## 실행·복원 시 반드시 추가로 읽을 문서 (위부터)
1. [CHAT_BOOTSTRAP.md](CHAT_BOOTSTRAP.md): 한 줄 명령 해석 및 역할
2. [LEAD_ACTIVE_WORK.md](docs/roles/lead/LEAD_ACTIVE_WORK.md): 코드 단위의 최신 작업 포인터
3. [DAILY_PROGRESS.md](docs/roles/lead/DAILY_PROGRESS.md): 날짜별 100점 진도/잔여시간(과거 중간 60%도 있음; **가장 최신 종결 행 우선**)
4. [DAILY_CAPACITY_PLAN_20261024.md](docs/roles/lead/DAILY_CAPACITY_PLAN_20261024.md): 60일 기본/예비/마감, [BLOCKED_WORK_RECOVERY_20261024.md](docs/roles/lead/BLOCKED_WORK_RECOVERY_20261024.md): 차단 재시도
5. [WORK_ORDER_FLEX_POLICY_20261024.md](docs/WORK_ORDER_FLEX_POLICY_20261024.md): 선행 작업 허용, [LEAD_FULLSTACK_PROTOCOL.md](docs/roles/lead/LEAD_FULLSTACK_PROTOCOL.md): GitHub 개발/검수/커밋
6. `proofinvest/`, `tests/`, `.github/workflows/ci.yml`, [STATUS.md](docs/roles/lead/STATUS.md), [HANDOFF.md](docs/roles/lead/HANDOFF.md), [TO_HACKATHON_LEAD.md](docs/roles/lead/TO_HACKATHON_LEAD.md)에서 필요한 근거 확인. 오래된 부분은 이 파일의 최신 상태로 대체.

## 다음 작업이 종료될 때 반드시 이 파일 업데이트
새로운 작업이 100% 종료되거나 외부 막힘/이월/CI 실패 등 의미 있는 변경이 있으면 같은 원격 업무 커밋에서 **이 `KIC_RESUME_STATE.md`의 다음 작업·최종 증거·완료율·외부 차단 상태를 갱신**한다. `LEAD_ACTIVE_WORK.md`·`DAILY_PROGRESS.md`·`STATUS.md`·`HANDOFF.md`·`TO_HACKATHON_LEAD.md`도 동기화하고, 현재 원격 HEAD와 CI 결과를 확인한다. 커밋이 안 되면 GitHub 공시 완료라고 하지 않는다.

**승인/보안:** 신규 현금 지출 0원 기준. 공개 GitHub에 토큰/개인정보/비공개 기획서 원본 금지. 외부 OpenDART API 인증·실 회사 자료 재전송·DAKER 팀 변경/제출은 이용조건·사용자 승인 및 실제 화면 증거 필요. 역할 분리는 *모듈만* 유지, 다른 AI 채팅 재개 요청 금지.
