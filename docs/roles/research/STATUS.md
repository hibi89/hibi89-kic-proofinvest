# STATUS — KIC ProofInvest Research

- **갱신 시점**: 2026-10-24 13:02 KST
- **저장소 / 브랜치**: `hibi89/hibi89-kic-proofinvest` / `feature/research`
- **과제**: `KIC-R-001` / 완료 보고 준비, **총괄 검수 대기 (AWAITING_REVIEW)**.
- **시작 원격 HEAD**: `1f05adcedff85526f9121a0a470d8f21f40d57f8`.
- **작업 시작 영수증**: `1ebc0593b0662fb1a1a8661fcade8e339ee249d1` (`[IN_PROGRESS]`).
- **신규 기능 코드 커밋**: `6339ec05cc89786c7f3e0673af52b3738268bd94`.
- **신규 테스트 반영 커밋**: `1baeb881ca9d7a6b4afe78ed251b86792314d0f6`.
- **구현**: `proofinvest/research.py` — 입력으로 제공된 기록만 결정론적으로 정규화. HTTPS 원문 URL, 필수 출처 필드, 발행일/수집일, 중복 ID 충돌, 찾을 수 없는 참조 ID, 기준일 이후 자료, 근거보다 이전 시점 주장, 공백 claim을 안전하게 차단. 상태 `success|partial|unavailable`; 상세 경고 코드 제공.
- **신규 테스트**: `tests/test_research.py` — `SYNTHETIC_FIXTURE` 전용 17개.
- **로컬 재현 테스트**: `python -m unittest discover -s tests -v` → **26 PASS / 0 FAIL / 0 ERROR** (기존 9 + 신규 17). `python -m proofinvest --claim-revenue-growth-pct 20` → **성공, SYNTHETIC_FIXTURE, verified, 20.00**.
- **재현성 검증**: 테스트에 필요한 원격 GitHub 원본 8개 파일을 로컬에 구성했고, 모든 파일의 Git Blob SHA가 GitHub와 일치함을 확인. 이 결과는 **동일 내용 로컬 Python 실행 검증**이며 GitHub Actions 검증과 구분.
- **CI**: commit status API의 상태 항목 0개; 연결된 워크플로 실행 URL을 직접 확인하지 못함. **원격 CI 미검증**(성공 판정 금지).
- **외부 운영**: OpenDART/LLM/HTTP 호출 없음; 외부 기업의 사실 여부, 라이선스 적법성 및 Production 실서비스 검증 미실시.
- **공통 코드·데이터 보존**: `engine.py`, `dart_adapter.py`, `__main__.py`, `main`, `lead/kic`, 다른 기능 브랜치는 수정하지 않음.
- **결정 대기**: Research 내부 구조를 전역 계약으로 동결할지 총괄 검수 및 승인 필요. Verification 연동/라이브 API는 후속 지시 전 착수 금지.
- **보고/다음 지시**: `docs/roles/research/TO_KIC_LEAD.md`. 현재 DONE 메시지 기록 후 총괄이 검수하여 `lead/kic/NEXT_TASK.md`를 갱신하기 전까지 대기.
