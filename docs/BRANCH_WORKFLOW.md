# KIC ProofInvest — branch/role contract

## 구조
- `main` = **유일한 통합 기준**. 기능별 작업 직접 수행 금지(정상적 통합/문서 갱신 제외).
- `lead/kic` = **KIC 총괄 전담 채팅방**. 기획서·심사 규정·일정·데이터 계약·검수·통합 PR.
- `feature/research` = **산업·기업 리서치 담당**.
- `feature/verification` = **재무 수치·공시 검증 담당**.
- `feature/risk` = **위험 신호 검출 담당**.

## 새 채팅 시작 매뉴얼
사용자는 해당 담당 채팅에서 "**GitHub `hibi89/hibi89-kic-proofinvest`의 `<branch>` 확인하고 HANDOFF.md부터 읽고 진행해**"라고만 말해도 된다. 담당자는 반드시 최신 원격 브랜치와 SHA부터 확인하고, 해당 브랜치에서 `HANDOFF.md → STATUS.md → AGENTS.md → REQUIREMENTS.md → 실제 소스` 순으로 검증한다. 브랜치 문서가 실제 소스와 다르면 소스를 우선하고 차이를 보고한다. 다른 브랜치 문서를 읽어도 해당 브랜치 권한을 무단 침범하지 않는다.

## 개발·통합
1. 각 담당자는 **담당 브랜치에서만** 변경·테스트·커밋. 종료 시 HANDOFF/STATUS와 테스트 근거를 함께 갱신.
2. 공통 데이터 계약 변경은 lead/kic에게 설계 제안 후 승인. 독립 브랜치에서 임의 중복 구현 방지.
3. feature → main PR(리뷰는 lead/kic). 실패 테스트, 미검증 API 성공 주장, 비밀정보 포함 시 병합 금지.
4. Worktree/force push/빈 커밋/무단 레포 재설계 불필요.
5. 기획서 PPTX/PDF 제출물은 공개용 검토 완료 전 원본을 올리지 않는다.

## 데이터 계약(제안; 구현 검증 전)
- 연구: `target`, `sources[{title,url,published_at,collected_at}]`, `findings`, `status`.
- 검증: `claims[{metric,period,value,unit}]`, `checks[{metric,state,value,source,reason}]`, `status`.
- 위험: `verified_inputs`, `risk_signals[{rule,state,value,threshold,explanation,source}]`, `status`.
- `verified/conflict/unavailable` 현재 프로토타입 상태와 API 간 표준화는 추후 테스트를 통해 결정.

## 검증
`python -m unittest discover -s tests -v`; 합성 fixture 출력은 실 데이터가 아니다. CI 성공과 Production/브라우저 작동은 별개.
