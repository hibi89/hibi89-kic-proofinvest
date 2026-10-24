# ProofInvest — AI 작업자 공통 규칙

1. **기본 인수인계 순서**: docs/roles/lead/HANDOFF.md → STATUS.md → OPERATIONS.md → AGENTS.md → REQUIREMENTS.md → 소스. 각 브랜치 고유 역할의 최신 STATUS/HANDOFF와 실소스를 대조하고 원격 HEAD를 확인한다.
2. `main`은 최종 통합본, `lead/kic`는 KIC 총괄 감독, `feature/research`, `feature/verification`, `feature/risk`는 기능별 작업 담당. **역할별 소유 브랜치만 수정**.
3. 사용자: 자이언츠파크 1인. 전체 해커톤 총괄(세 대회 감독)은 KIC 총괄과 별도 역할이다. KIC 총괄은 KIC 제출과 기능 통합만 책임진다.
4. **한 제품, 세 기능**: 연구 → 공시 검증 → 위험 신호. 데이터 계약·기준일·연결/별도·통화·정확한 출처를 통제한다. 기능별 임의 재설계 금지.
5. 합성 수치는 항상 `SYNTHETIC_FIXTURE`로 표기. 누락·혼란·미검증 수치는 추정값으로 채우지 않는다.
6. 투자 권고·매매 실행·타인 계좌 접근은 하지 않는다.
7. Public 저장소이므로 키/토큰/`.env`/개인정보/비공개 기업자료/공식 기획서 비공개 초안 원본을 커밋하지 않는다.
8. 실제 OpenDART 호출은 사용자 승인, 라이선스/쿼터/비용 확인 후 실시. AI Plus 구독은 외부 API 무료 제공 근거가 아니다.
9. 정상 소스 보존; 최소 수정, 오프라인 테스트, PR 검수 후 통합. 무의미한 빈 커밋, 강제 push, Git 이력 강제 수정 금지.
10. 실제 GitHub SHA·CI·HTTP/브라우저 상태를 나누어 검증. CI 녹색이 배포 정상은 아니다.
11. 역할 문서는 각 브랜치의 `HANDOFF.md`와 `STATUS.md`를 종료 전에 갱신. 성공·부분·미검증을 분리.
12. 채팅 맥락은 문서보다 신뢰도가 낮다. 최신 GitHub 브랜치/코드/검증 근거를 우선.
