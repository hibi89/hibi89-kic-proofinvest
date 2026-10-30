# P21: 로컬 SEC 원본 직접 검사 — 검증된 Python 방식

PowerShell 실행 래퍼는 실제 Windows CI에서 두 번 실패하여 제거했습니다. **실제 SEC 원본 3종 세트는 아직 확보되지 않아 미검증입니다.** 검증된 P20 Python 백엔드를 별도 변환·저장 없이 직접 호출합니다.

기존 KIC `lead/kic` 저장소에서 `git pull --ff-only` 하고 Python 3.11을 확인하세요. 이미 적법하게 확보한 **원본 그대로의** `submissions.json`, SEC 전체 `companyfacts.json`, 동일 accession의 10-K 원본 HTML 파일이 필요합니다. 전체 CompanyFacts 대신 수동 발췌 JSON을 사용해 실제 원본 검증이라 주장하지 않습니다.

PowerShell에서 파일 위치와 **확인된 실제** 메타데이터로 자리표시자를 바꿔 실행합니다.

```powershell
python -B -m proofinvest.kuodra_loose_sec_compatibility `
  --submissions "C:\SEC-local\submissions.json" `
  --companyfacts "C:\SEC-local\companyfacts.json" `
  --original "C:\SEC-local\original.html" `
  --cik "CIK_10_DIGITS" `
  --accession "ACCESSION_20_CHARS" `
  --as-of "YYYY-MM-DD" `
  --collected-at "YYYY-MM-DDTHH:MM:SSZ"
```

**`--collected-at`은 실제로 확인한 SEC 원본 관측 UTC 시각**이어야 합니다. 알지 못한다면 임의로 과거 시각을 꾸며 입력하지 마세요. 이 도구의 결과는 원본 파일 내용과 경로를 새 파일/DB로 저장하지 않으며 SEC HTTP·Gemini·거래 실행을 하지 않습니다. JSON `status=operator_review_required`와 exit 0은 형식 검토 후보일 뿐 원본 진위·수집 시각·권리·실제 HTML과 accession의 연결 증명이 아닙니다. `status=blocked` 또는 exit 2이면 JSON `reason_code`를 확인합니다. 로그를 공유할 때는 원본 내용·경로·민감정보를 포함하지 마세요.

P20 원래 소스 [CI #41112337291](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/41112337291) 871 Python tests/3 jobs PASS(합성). P21 PowerShell 래퍼는 실실행 FAIL 후 철회. 실제 SEC 3회 요청과 로컬 저장은 별도 승인 후에만 가능하며, Gemini 실연동과 Production은 미검증입니다.
