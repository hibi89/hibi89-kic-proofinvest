# KIC 총괄에게 전하는 말 — 산업·기업 리서치 담당

**이 문서는 'feature/research' 담당자가 KIC 총괄에게 남기는 공식 메시지함입니다.**
- KIC 총괄 브랜치: `lead/kic`
- 작성 위치: 반드시 `feature/research`의 `docs/roles/research/TO_KIC_LEAD.md`.
- **코드/기능 변경이 생기거나 의사결정이 필요하면 담당자가 직접 갱신·GitHub 커밋**해야 총괄이 읽을 수 있습니다.
- 총괄은 지시 전 `feature/research`·`feature/verification`·`feature/risk` 세 메시지함을 **각 원격 브랜치의 최신 HEAD에서 읽어야** 합니다.
- 메시지의 처리 완료 여부는 총괄 브랜치 `docs/roles/lead/MESSAGE_REVIEW.md`에서 기록. 총괄이 타 기능 브랜치 파일을 직접 수정하지 않습니다.
- 완료한 메시지는 지우지 말고 `[처리됨]` 등을 덧붙여 이력 보존 (기본은 `[대기]`).

## 초기 메시지
- **2026-10-24 KST / [안내·처리 불필요]**: 담당 브랜치와 전용 메시지함이 생성됨. 기능 개발 및 새 작업 요청은 아직 시작 전.

## 신규 메시지 작성 양식

### YYYY-MM-DD HH:MM KST | [대기] | 제목
- 작성자 역할: 산업·기업 리서치 담당
- 브랜치: `feature/research`
- 근거 커밋 SHA: (최신 GitHub SHA 기입)
- 분류: 질문 / 승인 요청 / 장애 / 제안 / 완료 보고
- 중요도: 차단 / 높음 / 일반
- 현재 상황과 검증 근거:
- 총괄에게 전달할 내용:
- 제안 대안 및 영향:
- 총괄이 결정할 사항 / 회신 희망:

## KIC-R-001 실행 기록

### 2026-10-24 KST | [IN_PROGRESS] KIC-R-001 | 오프라인 근거 정규화 착수
- task_id: `KIC-R-001`
- branch: `feature/research`
- starting_remote_HEAD: `1f05adcedff85526f9121a0a470d8f21f40d57f8`
- source_instruction: `lead/kic@b845170c2b81d438afcf8b2e7179e19af90cd41c`, `docs/roles/lead/tasks/KIC-R-001.md`
- approved_scope: 신규 `proofinvest/research.py`, `tests/test_research.py`, Research 전용 역할 문서. 오프라인 입력만 처리.
- no_live_calls: OpenDART/LLM/HTTP/SDK 미호출, 공통 계약 및 타 브랜치 변경 금지.
- state: 사용자 실행 요청으로 착수; 테스트·완료 상태는 후속 커밋에서만 판정.
