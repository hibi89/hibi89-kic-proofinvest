# KIC 2026-11-21 Peer 선정 근거 — 오프라인 근거연결·비교 범위 검증

## 일정·목표
- 원래 2026-11-21 예정 / 2026-10-24 KST 선행 수행. 단일 총괄 브랜치 `lead/kic`.
- 목표는 **비교기업 선정 이유 한 가지를 재현 가능하게 설명**하는 것이다. 실제 기업 추천·투자 적격성·공식 산업코드 인증을 목적으로 하지 않음.
- 비교기업 분석 실무 근거: CFA Institute [Industry and Competitive Analysis](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/industry-and-competitive-analysis)에서 산업 경계·유사 제품/서비스·경쟁구조의 정의가 선행되어야 한다고 설명. CFA Institute [Stick to the Fundamentals and Discover Your Peers](https://rpc.cfainstitute.org/research/financial-analysts-journal/2017/stick-to-the-fundamentals-and-discover-your-peers)는 **단순 동일 업종만으로 동질적 수익성/성장/위험 특성을 보장하지 않는다**고 제시. [CFA Institute Peer Benchmarking 2024](https://rpc.cfainstitute.org/blogs/enterprising-investor/2024/for-the-analyst-peer-benchmarking-methods-to-improve-earnings-forecasts)는 회계 표시 특성과 가치 동인의 비교 필요를 소개.
- **본 MVP의 작은 계약**: 산업코드·제품군·사업모델·시장 지역·규모구간·동일 보고연도·CFS/OFS 유형·통화가 동일하고, 기존 `normalize_research`에서 구조적으로 수락된 source_id가 표적 기업과 후보 기업 각각에 연결되면 **candidate_for_review**로 분류. 단 하나라도 불일치하거나 근거가 빠지면 `excluded`(불일치 항목/사유 기재). 유효 후보가 하나도 없으면 결과 `unavailable`. 정성적 시장구조/가치 동인 실증이 없는 경우 보수적 기초 스크리닝에 한정.

## 구현과 선택
- 구현 코드 `1b1b4c05f2e1331afeda2daa48cdebe7db1ae20d`: 새 `proofinvest/peers.py` / `tests/test_peers.py`. 순수 오프라인 Python, 입력 수정 없음, 외부 네트워크/API 호출·LLM 추정 없음.
- 출력: `status=candidates_for_review|unavailable`, `scope=OFFLINE_PROVISIONAL_PEER_SCREEN`, `verified_real_company_peers=false`, 항목별 `state=candidate_for_review|excluded`, `reasons`, `source_ids`, `authenticated_external_source=false`.
- **검증 vs 실제 사실**: 입력 issuer/산업/사업/규모 값 및 인용 URL은 호출자가 제공. Research `success`는 타임스탬프·형식·링크 구조가 유효함을 뜻할 뿐, **공식 기업·동종성·업종분류/실적·재배포권/라이선스·원문 인증이 아님**. 어떠한 입력에도 투자 추천·동종기업 확정 판정을 반환하지 않음.
- 중복 `issuer_id`(상충 여부 불문)는 개수 기준으로 동일 ID 전체 제외; 대상 자기 자신 제외. 기간/통화/CFS-OFS 혼합·규모구간 결측은 제외. 실제 시장 데이터가 준비되지 않았기에 합성 fixture로만 시험.
- **대안 비교**: A 유명 기업을 임의로 예시 peer 목록으로 고정 (빨라 보여도 제품/수익원·통화·원문 근거 허위 위험). B 출처 연결이 있는 입력 데이터를 **검토 후보**로만 분류하고 선택 이유/탈락 이유를 기계 판정 (**선택**, 외부 비용 0, 실패 시 보류, 스키마 독립 모듈). 실거래/평가 멀티플 계산 없음.

## 회귀 / CI / 남은 한계
- **신규 8개**: 완전 매칭은 임시후보, 동일 업종이라도 제품·모델·시장·규모 중 다르면 제외, 회계연도/통화/CFS-OFS 혼합 제외, 출처 ID 결측 제외, 대상 출처 결측 시 전체 보류, 중복 issuer ID 차단, 자기 자신/잘못된 범위 차단, 순수성/결정성 및 미검증 Research 차단.
- [GitHub CI #40080754184](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40080754184) code SHA `1b1b4c05f2e1331afeda2daa48cdebe7db1ae20d` / GitHub Actions `completed/success`, 단위테스트 **106/106 PASS**, 60일 원장 검증·합성 CLI·실기업 수동기록 CLI **PASS**. 별도 로컬/외부 API·브라우저 E2E·계정 인증 실행 없음.
- 진짜 Peer 기업 선정은 추후 1차 출처로 대상/후보의 제품군·부문 매출·시장·사업 모델·연도·공시 범위·통화·크기 등 공식 검증 필요. **매칭 항목을 독립 증명하는 출처까지 검증한 것은 아님**.
- DAKER 개인/팀장 로그인 제출권한 10/25·11/09 각60% BLOCKED (동일 외부 원인), DART 공식 원문 접수번호 10/30 90% BLOCKED, 11/10 사용자 최종 제출 NOT_STARTED. frozen 비공개 PDF/PPTX 6개 기존 백업 기록 유지, 이번 변경/공개 업로드 없음.
- **11/21 날짜별 100/100 DONE**, 남은 기본0h+예비0h=0h, 실제 소요 미계측. 60일 정본 갱신 예정 20 DONE/3 BLOCKED/37 NOT_STARTED.
- **11/22 예비일은 건너뛰어 DONE 처리한 것이 아님**: 실작업 기본 0h, 장애 발생 시 회수하는 일정. 아직 NOT_STARTED. 다음 선행 가능한 **11/23 Research 회귀·중복 근거 테스트** 0/100, 기본1h+예비2h=3h.
- 롤백 기준: 변경 전 GitHub SHA `242cb78b0b105d6eece99d2eccade4652320282a`, Git 역커밋 가능. force-push·다른 브랜치·실계정/API·비공개 바이너리 변경 없음.
