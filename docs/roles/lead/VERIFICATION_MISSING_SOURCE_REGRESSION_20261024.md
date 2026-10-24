# KIC Verification 누락·불확실성 표시 회귀 — 2026-11-16 계획분

- **원래 일정 / 실제 실행**: 2026-11-16 / 2026-10-24 KST. 단일 KIC 총괄 `lead/kic`.
- **수정 코드 SHA**: `cf5552c840588f28f26b0649fb00ac2098efe71e`; 수정: `proofinvest/engine.py`, `tests/test_engine.py`.
- **오류 재현**: 구형 `calculate(..., is_demo=False)`는 비합성 공시 입력에 `rcept_no`가 비어도 매출 산술과 주장 일치만으로 `verified`를 반환해 출처 링크가 없는 결과를 검증인 양 표현할 수 있었다.
- **A/B 비교**: A는 `revenue_yoy_pct` 검증에 존재하는 공식 형식 접수번호로 구성 가능한 출처 링크가 **없는 비합성 데이터만** `unavailable`, `value=None`, `source=None`으로 보류 (**채택**: 호출 비용 0, 수정 범위 작음, 오표시 위험 낮음). B는 외부 서버에서 자동 조회해 검증 (승인·토큰·쿼터·실패복구 필요; 무단 호출 위험). 사용자의 실 API 승인 전 B 미적용.
- **코드**: `calculate`의 매출 검사에서 재무 수치/분모 결측 후 source guard를 두고, 비합성 모드에서 `rev["source"]`가 없으면 '공시 접수번호·출처 링크가 없어 비합성 매출 검증 보류'를 표시. 합성 `SYNTHETIC_FIXTURE`와 기존 JSON 키/다른 검증 경로 보존.
- **회귀 4개**: 실제 모드 접수번호 누락 시 값·링크 null; 형식 틀린 접수번호 null; 모의 14자리 접수번호 *형식만* 유효하면 내부 산술 verified 유지; 출처 없는 합성 fixture는 `demo_not_real` 유지. 14자리 모의 번호는 진짜 DART 원본을 의미하지 않음.
- **오프라인 검증**: [GitHub CI #40079239630](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40079239630) `completed/success`, **94/94 unittest PASS**, FAIL 0 ERROR 0, `scripts/master_progress.py --check` 및 합성/수동 기록 CLI GitHub Actions 단계 SUCCESS. 별도 로컬 테스트·HTTP·브라우저·실 API 실호출 미실행.
- **개념적 한계**: 14자리 형식과 URL 생성은 실제 접수번호 존재·원본 진위·라이선스·인증된 API를 보장하지 않음. `engine.calculate`의 레거시 데모 위험 신호는 verified-only Risk 별도 게이트와 다름. 실서비스/Production/투자 조언이 아님.
- **백업/복구**: 수정 전 GitHub SHA `052b7b4152c3108f2851823f57c4db202a8f5b3f`, 원본 보존·force push 미실시. Git 이력에서 정상 역커밋 가능.
- **게이트**: 11/16 계획 업무 **100/100 DONE**, 남은 기본0h+예비0h=0h; 실제 투입시간 미계측. 60일 전체 제품 완성률 아님.
- **외부 BLOCKED 유지**: 10/25 DAKER 60%, 11/09 DAKER 60% (계정·팀장 제출권한 로그인 증거 없음), 10/30 DART 원문 대조 90%. 11/10 실제 공식 접수 NOT_STARTED, 사용자의 제출 승인 필요. 동결된 후보 PDF/PPTX 공개 저장소 미게시·이번 변경 없음.
- **다음**: 2026-11-17 검증 테스트/CI 및 잔여 장애 목록, READY 0/100, 기본1h+예비2h=3h. 인증된 DAKER 권한 확보 가능할 때 P0 점검 최우선.
