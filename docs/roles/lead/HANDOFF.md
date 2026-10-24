# HANDOFF — KIC 총괄

1. **목표·확정 요구·기술**: 자이언츠파크 1인 KIC 본선 상위 12팀 목표. ProofInvest (연구·공시 검증·위험 탐지), Python 3.10+, 공개 GitHub.
2. **완료 기능·결정 근거**: 초기 스타터와 4개 작업 브랜치 구성, 기능별 역할 문서·총괄 메시지함 수립. 사용자 요청으로 총괄 브랜치 `lead/kic` 별도 운영; Git worktree 미사용.
3. **테스트 명령·결과**: `python -m unittest discover -s tests -v` — 초기 스타터 9 PASS 보고. 실 API·브라우저·Production 미검증. CI 결과는 별도 확인 후 업데이트.
4. **상태·중단 지점**: 총괄 업무 수립 단계; 실제 3개 기능 확장/통합/배포는 미완료. 새 지시 전 최신 메시지함 3개 검토 필수.
5. **오류·근거·재시도 금지·대안**: 현재 검증된 운영 장애 없음. 외부 API 인증·데이터 계약·출처 라이선스 미확인. 추측으로 실제 사용 가능하다고 단정하지 말 것.
6. **저장소·브랜치·SHA·경로**: `hibi89/hibi89-kic-proofinvest`, `lead/kic`; 초기 공통 베이스 `9e66301145313e7ac2a4e69eab32d9d037bdb64f`. 본 브랜치의 최신 SHA는 GitHub 조회. `docs/roles/lead/*`; 나머지 3개 메시지함은 각 feature 브랜치 소유.
7. **Production URL·환경**: 미설정. Python CLI 오프라인 스타터. GitHub Actions는 원격 상태 확인 필요.
8. **원본·백업·인증 관리**: 기획서 PPTX/PDF는 현재 사용자 대화 파일에 보관, 공개 저장소로 사전 업로드 금지. 토큰/API Key/개인정보 유출 금지. 기능별 원본 코드 무단 변경 금지.
9. **다음 우선순위·승인**: 기능 메시지함 전수 확인 → 데이터 계약·작업지시 검토 → 테스트/PR 검수 → main 통합. 유료 호출·비용·권한 변경·범위 조정은 사전 사용자 승인.
10. **갱신 일시·범위·문서 기준**: 2026-10-24 KST 초기 인수인계. 실제 커밋 후 SHA 확인 및 차기 작업마다 인수인계 갱신.

## 절대 생략 금지
**총괄은 지시 전 항상 `feature/research`, `feature/verification`, `feature/risk`의 최신 `TO_KIC_LEAD.md`를 열람하여 대응한다.** `docs/roles/lead/OPERATIONS.md` 참조.
