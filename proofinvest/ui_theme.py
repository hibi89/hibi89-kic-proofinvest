"""Static, dependency-free Streamlit design system for ProofInvest.

No remote assets/fonts/scripts. Static HTML/CSS only; no untrusted content.
"""
from __future__ import annotations


def render_shell(st) -> None:
    st.markdown(
        """
<style>
:root { --pi-navy: #0c223e; --pi-slate: #203957; --pi-teal: #008b88; }
section.main > div.block-container { max-width: 1180px; padding-top: 1.9rem; }
.pi-shell { margin: 0 0 1.35rem; padding: 17px 22px; border: 1px solid #cbd5e1;
  border-radius: 14px; background: linear-gradient(115deg, #0c223e, #173b57); color: #f8fafc; }
.pi-brand { font-family: ui-sans-serif, system-ui, sans-serif; font-weight: 760;
  font-size: 1.13rem; letter-spacing: .065em; }
.pi-brand span { color: #67e8dc; }
.pi-subbrand { font-family: ui-sans-serif, system-ui, sans-serif; font-size: .79rem;
  color: #dbeafe; margin-top: .25rem; }
.pi-eyebrow { font-size: .72rem; font-weight: 760; letter-spacing: .12em;
  color: #0c7778; text-transform: uppercase; padding: 0 0 .4rem; }
.pi-section { font-size: .95rem; font-weight: 750; color: #193755;
  padding-bottom: .45rem; border-bottom: 1px solid #cbd5e1; margin: .9rem 0 .8rem; }
.pi-case { border-left: 4px solid #0f766e; border-radius: 8px;
  background: #edf8f6; padding: .75rem 1rem; color: #194b49; margin: .8rem 0 1rem; }
.pi-case--blocked { border-color: #dc5a5a; background: #fff0ee; color: #822e36; }
.pi-disclaimer { background: #f1f5f9; color: #334155; border-radius: 8px;
  padding: .9rem 1rem; font-size: .85rem; margin: .65rem 0 1rem; }
@media (prefers-color-scheme: dark) {
  .pi-section { color: #e2e8f0; border-color: #475569; }
  .pi-eyebrow { color: #5eead4; }
  .pi-case { background: #123e3e; color: #ccfbf1; }
  .pi-case--blocked { background: #4b1e25; color: #ffe4e6; }
  .pi-disclaimer { background: #253447; color: #e2e8f0; }
}
@media (max-width: 650px) {
  section.main > div.block-container { padding-left: .85rem; padding-right: .85rem; }
  .pi-shell { padding: 13px 15px; }
}
</style>
<div class="pi-shell">
  <div class="pi-brand">PROOF<span>INVEST</span> <span style="font-size:.65em;font-weight:500">/ EVIDENCE LAB</span></div>
  <div class="pi-subbrand">공시 근거 · 수치 검산 · 위험 보류 · 사람 중심 통제</div>
</div>
""",
        unsafe_allow_html=True,
    )
