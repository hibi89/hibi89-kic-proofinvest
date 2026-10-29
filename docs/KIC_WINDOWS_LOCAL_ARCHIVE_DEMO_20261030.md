# KIC 로컬 SEC형 ZIP → 검산/Risk/Guard 감사 시연 (Windows, 2026-10-30)

**범위:** 실제 SEC, DAKER, 금융 서비스 인증과 무관한 **직접 생성한 합성 SEC 형식 자료**를 사용해, 사용자의 Windows PC에서 전체 오프라인 분석 경로를 확인합니다.

## 사용자가 직접 실행하는 절차

PowerShell에서 현재 ProofInvest-KIC 저장소 폴더로 이동한 상태를 기준으로 합니다.

1. 실행 중인 Streamlit을 `Ctrl+C`로 종료합니다.
2. `git pull --ff-only origin feature/kic-integrated-components`
3. 원본이 없는 새 출력 파일을 하나 생성합니다. 같은 이름의 기존 파일은 **절대 덮어쓰지 않습니다**.

   ```powershell
   py -3.11 -m proofinvest.kic_full_backend_demo --write-synthetic-zip .\kic-synthetic-3source.zip
   py -3.11 -m streamlit run streamlit_app.py
   ```

4. 브라우저 `http://localhost:8501`에서 **자료 유형 → 저장된 SEC 3원문 ZIP → 검산·Risk·Guard 감사 — 오프라인**을 고릅니다.
5. 폼에 아래 내용을 입력합니다.

   | 필드 | 예시 |
   |---|---|
   | ZIP 전체 경로 | `C:\...\ProofInvest-KIC\kic-synthetic-3source.zip` |
   | 별도 SQLite 감사 DB | `C:\...\ProofInvest-KIC\kic-synthetic-guard.sqlite` |
   | 당기 종료일 | `2025-09-30` |
   | 전기 종료일 | `2024-09-30` |
   | 원문 앵커 | `TEST_LITERAL_SOURCE_SPAN` |
   | 성장률 주장 | 공란(HOLD) 또는 `1.00`(REJECT) |
   | 실행 ID | `synthetic-ui-hold-1`, `synthetic-ui-conflict-1` 등 **서로 다른 이름** |
   | 검토 조치 | 먼저 `기록 없음` |

6. **로컬 ZIP 검산·Risk·Guard 감사 실행**을 명시적으로 누릅니다. 다음을 확인합니다.
   - 수치 자체는 산술 검산하나 출처는 여전히 **미인증**
   - 주장 없음: `calculated_unverified` → **HOLD**
   - `1.00` 충돌 주장: `conflict` → **REJECT**
   - SQLite 감사 체인 검사 **PASS**, 감사 해시·원문 해시·보고서 조회
   - JSON/Markdown은 외부 인가나 금융투자 보고서가 아니라 **미인증 로컬 검토 기록**

## 재현성 및 데이터 보존

- 합성 ZIP은 사용자가 **명시적으로 생성**한 파일입니다. 사용자가 원하면 수동 삭제할 수 있습니다.
- SQLite 감사 DB는 UI의 **실행 버튼을 누른 후에만** 생성될 수 있습니다. 합성 UI 임시 시연과 달리 저장형 모드는 DB를 남깁니다.
- 같은 실행 ID와 동일 증거/주장으로 재호출하면 기록을 재사용합니다. 다른 주장이나 입력으로 같은 실행 ID를 쓰면 실패하도록 설계되어 있으므로 새 실행 ID를 사용합니다.
- 새 화면은 로컬에 존재하는 자료만 읽습니다. 자동 SEC HTTP 조회·로그인·주문·권고·실제 투자 승인 기능이 없습니다.
- ZIP의 self-reported HTTP 카운트/시각·CIK·URL·SHA는 스스로 생성한 가상 메타데이터입니다. **실제 SEC HTTP 0회**, 공시 원문 진위·재배포 권리는 확인되지 않았습니다.
- 경로/원문/개인적인 검토 메모는 공개 GitHub에 올리지 마십시오.
- 기존 DL → Guard 임시 합성 시연 메뉴도 그대로 유지됩니다.

## 자동 검증

- `tests/test_kic_archived_sec_guard_ui.py` (AppTest): 실행 전 쓰기 없음, 정상 HOLD, 충돌 REJECT, SHA 변조 차단, 감사 ID 재사용 차단, 사람 검토 독립성, 위조 상태 차단, Windows 작업 디렉터리의 임시 DB 정리
- `tests/test_kic_full_backend_demo.py`: ZIP 생성 명시성, 재분석 가능성, 덮어쓰기 금지, 외부 HTTP 0회
- `.github/workflows/ci.yml`: Linux Python + Chromium과 별도 **Windows SQLite/Streamlit/AppTest** 매트릭스

현재 테스트는 **기능 재현과 fail-closed 안전성**을 확인할 뿐, 실제 기업의 회계 수치 진위·미래 투자성과 또는 본선 제출 완성도를 입증하지 않습니다. 프론트 UI·PDF 시각 디자인은 별도 전면 개선 대상입니다.
