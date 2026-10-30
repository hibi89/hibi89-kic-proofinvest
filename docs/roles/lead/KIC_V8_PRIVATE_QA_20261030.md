# KIC ProofInvest Global V8 — exact private review candidate QA (2026-10-30 KST)

**Decision:** A NEW private V8 review copy was created without overwriting the owner-supplied official template or private V7. **NOT APPROVED / NOT SUBMITTED / NO PIN REPIN.** Its bytes are not present in this public repository, and there is no claim of DAKER final acceptance.

## Exact candidate identity (private)
- PDF: `KIC_ProofInvest_Global_V8_PRIVATE_REVIEW_20261030.pdf`, **481732 bytes**, SHA-256 `78d2b55390d6a9ffefcf9eab9c9754a1f921c0b2d0af239a3d64530144747310`.
- Editable PPTX: `KIC_ProofInvest_Global_V8_PRIVATE_REVIEW_20261030.pptx`, **122808 bytes**, SHA-256 `ad6648dbc244479e533684d0ff72f272399a6a3ed046eb821a4ad52217a0d298`.
- V7 protected reference PDF remains SHA-256 `f2b949b6747c30a4ee788e1bf7d45d00167fede6c5332b8459766e724b07a4b8`; V7 PPTX remains `618492d8107fbbbc53c1f61d182f82d75a80ec2b0656b6e73d469d9b985fd806`.
- Original organizer PPTX SHA-256 `e0c8ffdfba16ed1ef5c6112d7581f78d47da196deb1879ef2e6f86644af870d5`.
- Private archive `KIC_ProofInvest_Global_V8_PRIVATE_REVIEW_20261030.zip` **438840 bytes**, SHA-256 `127133af6fb58ebce08e0b22a6ad5a5251cd1a9cbaba4e40309cacf67066c95e`. It contains PDF/PPTX/QA/README/stdlib integrity verifier/manifest, and **none of the older protected originals**. Full verification PASS and a deliberately corrupted test ZIP rejected.

## Source-level corrections and actual local review
1. Page 10 previous public GitHub link pointed to old `feature/kic-integrated-components`. V8 uses latest designated KIC source branch **`https://github.com/hibi89/hibi89-kic-proofinvest/tree/lead/kic`**. Hyperlink target and on-page label updated.
2. Organizer PPTX instruction includes AI model name disclosure. Page 10 V8 specifies `ChatGPT(GPT-6)` plus drafting / code-and-test support, while keeping final human source/fact/license approval language unchanged.
3. Original official organizer PPTX inspected side-by-side: 10 slides, same dimensions. **96/96 retained source shapes preserve type/position/size/rotation**, while 8 instructional body boxes (slide 3–10 shape ID 11) were intentionally replaced by substantive content. V7→V8: **258/258 shape IDs and geometry preserved**; precisely 2 text shapes and 1 hyperlink target changed on slide 10.
4. V8 and V7 PDFs each 10 pages. **Pages 1–9 text and 90-DPI rendered pixels exactly identical.** Page 10's differences confined to intended text region, visually inspected. No out-of-bounds text spans or U+FFFD replacement glyphs. All 11 PDF font-object references returned nonempty embedded program data; all four expected external URLs matched. PDF opens unencrypted and text-selectable.
5. Separate run of `verify_packet.py` reported PASS for original private ZIP and FAIL for a copied ZIP with one corrupted PDF member. Evidence is a runtime-executed local Python QA, **not GitHub CI or live SEC**.
6. Current `lead/kic` CI baseline `4bdcd29d7cf0c1932be1dfe123b522b01964a6db` [#41067082813](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/41067082813) was SUCCESS on Python, Windows SQLite and Chromium offline synthetic pathways. V8 content changes did not alter any product code or independently authenticate SEC.

## Remaining mandatory gates

- Organizer: official [DAKER contest](https://daker.ai/public/hackathons/kic-ai-agent-competition) 7 sections and ≤10 PDF pages; deadline **2026-11-12 10:00 KST**. Submission permission and account/team leader access are **not checked**.
- Participant must explicitly review and approve **V8 exact filename, title, content and PDF SHA**. Otherwise leave existing pin and private sources untouched.
- After explicit approval: review any upload preflight exact-byte pin change with rollback, execute preflight, obtain separately explicit DAKER upload+finalization authority and verify portal receipt. No upload/submit action performed here.
- Future finalist-only live SEC/LLM, rights, deployed URL and model evaluation remain unverified. CI green does not resolve these.
- The private ZIP and source files were generated into this chat's working container; **not yet saved into the user's persistent Library or GitHub**. User should download/store the candidate before assuming it will persist across sessions. Only these public metadata and test notes are in GitHub.
