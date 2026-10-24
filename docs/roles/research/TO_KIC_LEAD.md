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

### 2026-10-24 13:02 KST | [DONE] KIC-R-001 | Research 오프라인 근거 정규화 구현·로컬 검증 완료
- task_id: `KIC-R-001`
- branch: `feature/research`
- source_instruction: `lead/kic@b845170c2b81d438afcf8b2e7179e19af90cd41c`
- latest_verified_parent_HEAD: `4b09520774b5b5ab3103e7727aea0f7e36e5a272`; **최종 문서 커밋 SHA는 이 메시지 자체와 순환 참조가 되므로 GitHub의 `refs/heads/feature/research` HEAD를 조회하여 확정한다.**
- code_commit_SHA: `6339ec05cc89786c7f3e0673af52b3738268bd94`
- test_commit_SHA: `1baeb881ca9d7a6b4afe78ed251b86792314d0f6`
- 수정 파일: 신규 `proofinvest/research.py`, `tests/test_research.py`; 갱신 `docs/roles/research/STATUS.md`, `HANDOFF.md`, `TO_KIC_LEAD.md`. 다른 브랜치·공통 엔진 코드 미수정.
- 테스트 명령: `python -m unittest discover -s tests -v` → **26 PASS(기존 9 + 신규 17) / 0 FAIL / 0 ERROR**, 로컬; `python -m proofinvest --claim-revenue-growth-pct 20` → `SYNTHETIC_FIXTURE` 합성 데모 성공. GitHub 8개 원본 파일의 Git blob SHA와 로컬 테스트본 일치 확인.
- CI: 원격 GitHub commit status 항목 0개, workflow runs 조회는 PR 트리거 전용이라 push 결과 확인 불가. **CI 미검증**. 유효한 run 링크 확보 못함; 워크플로 경로 `.github/workflows/ci.yml`.
- 구현된 내부 계약 제안: `normalize_research(payload)` 입력 `target_name, target_id?, as_of, sources[{id,title,url,published_at,collected_at,license}], findings[{claim,source_ids,as_of}]`; 출력 `status=success|partial|unavailable, source_kind, target, as_of, sources, findings, warnings[{code,detail}]`. 표준 라이브러리, 결정론적, 네트워크 미사용.
- 차단/검증: 잘못된 HTTP URL·빈 URL, 출처 누락·동일 ID의 상이한 자료, 미등록 source ID, 미래 발행 자료, 시점 역전, 공백 claim, 빈 입력 → 허위 성공 금지. 유효 finding과 무효 finding 혼합 시 partial.
- 확인된 제한: 제공된 기록의 형식·연결만 검사. **실제 산업 주장 진위, license의 법적 적합성, 출처의 실제 존재, 기업 실체 확인 불가**. timezone timestamp는 날짜 단위 검증; 타임존 정책 별도 확정 필요.
- 보안·비용: OpenDART/LLM/외부 API 호출 없음, 신규 결제 없음, 비밀정보·실 고객자료 미커밋.
- 총괄 검수 요청: (1) 코드 및 26개 테스트 (2) 원격 CI run 확인 (3) 내부 필드·상태를 전역 계약으로 채택할지 결정 (4) 미래 Research→Verification 데이터 인터페이스와 라이선스 확인 정책 승인.
- 최종 상태: **담당 작업자 DONE / 총괄 AWAITING_REVIEW**. 총괄 승인 전 `lead/kic/NEXT_TASK.md` 변경 또는 Verification/Risk로 자동 전환하지 않음.
