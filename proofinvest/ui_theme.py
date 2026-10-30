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
.pi-judge-hero { background: linear-gradient(112deg,#10283e,#174d59);
 border:1px solid #335e69; border-radius:16px; color:#f3f9fb;
 padding:23px 27px; margin:.25rem 0 1rem; }
.pi-judge-kicker {color:#76e5d7; font-weight:750; letter-spacing:.12em;
 font-size:.71rem; margin-bottom:7px;}
.pi-judge-hero h2 {color:#fff; font-size:1.33rem; font-weight:800;
 margin:0 0 8px; line-height:1.4;}
.pi-judge-hero p {color:#d7e8ed; font-size:.89rem; margin:0; line-height:1.55;}
.pi-judge-grid {display:grid; grid-template-columns:repeat(3,minmax(0,1fr));
 gap:12px; margin:.75rem 0;}
.pi-judge-card {background:#f8fbfd; border:1px solid #d4e0e7;
 border-radius:12px; padding:17px 18px; min-height:151px;}
.pi-judge-card .step {font-size:.73rem; font-weight:750; color:#536981;}
.pi-judge-card h3 {font-size:.94rem; font-weight:750; color:#1b334b;
 margin:7px 0 9px;}
.pi-judge-card .decision {font-size:.77rem; font-weight:800;
 padding:3px 8px; border:1px solid #72cdbf; color:#087267;
 border-radius:6px; display:inline-block;}
.pi-judge-card .decision.reject {color:#b33341; border-color:#f1b2b7;}
.pi-judge-card p {margin:9px 0 0; font-size:.78rem;
 line-height:1.5; color:#506980;}
.pi-judge-steps {border-top:1px solid #d5e1ea; padding:12px 0 3px;
 margin-bottom:.65rem; font-size:.78rem; font-weight:700;
 letter-spacing:.01em; color:#386079; overflow-wrap:anywhere;}
.pi-trace-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr));
  gap:11px; margin: .9rem 0 1rem; }
.pi-trace-node { position:relative; min-width:0; border:1px solid #d6e2ea;
  border-radius:12px; background:#f8fafc; padding:15px 16px 13px; }
.pi-trace-number { display:inline-block; font-size:.7rem; font-weight:800;
  letter-spacing:.07em; color:#54718d; margin-right:9px; }
.pi-trace-title { font-size:.79rem; font-weight:750; color:#294b65; }
.pi-trace-node strong { display:block; margin:.52rem 0 .36rem;
  font-size:.99rem; font-weight:800; color:#183c4d; }
.pi-trace-node p { margin:0; font-size:.73rem; line-height:1.5; color:#536c7f; }
.pi-trace-hold { background:#f4faf9; border-color:#9dd8d2; }
.pi-trace-hold strong { color:#106d65; }
.pi-trace-blocked { background:#fff8f6; border-color:#efd0c9; }
.pi-trace-blocked strong { color:#9f3545; }
@media (prefers-color-scheme: dark) {
  .pi-section { color: #e2e8f0; border-color: #475569; }
  .pi-eyebrow { color: #5eead4; }
  .pi-case { background: #123e3e; color: #ccfbf1; }
  .pi-case--blocked { background: #4b1e25; color: #ffe4e6; }
  .pi-disclaimer { background: #253447; color: #e2e8f0; }
  .pi-judge-card {background:#19334c; border-color:#3b5971;}
  .pi-judge-card h3 {color:#e9f4fb;}
  .pi-judge-card .step,.pi-judge-card p,.pi-judge-steps {color:#b8cfe0;}
  .pi-trace-node {background:#19334c; border-color:#3b5971;}
  .pi-trace-node strong {color:#e3f3fa;}
  .pi-trace-node p,.pi-trace-node .pi-trace-title,.pi-trace-number {color:#b6ccdc;}
  .pi-trace-hold {background:#153c3f; border-color:#327e76;}
  .pi-trace-hold strong {color:#8de7d2;}
  .pi-trace-blocked {background:#492830; border-color:#96505b;}
  .pi-trace-blocked strong {color:#ffd1d8;}
}
@media (max-width: 650px) {
  section.main > div.block-container { padding-left: .85rem; padding-right: .85rem; }
  .pi-shell { padding: 13px 15px; }
  .pi-judge-grid {grid-template-columns:1fr;}
  .pi-judge-hero {padding:17px 18px;}
  .pi-judge-card {min-height:auto;}
  .pi-trace-grid {grid-template-columns:1fr;}
}
</style>
<div class="pi-shell">
  <div class="pi-brand">PROOF<span>INVEST</span> <span style="font-size:.65em;font-weight:500">/ EVIDENCE LAB</span></div>
  <div class="pi-subbrand">공시 근거 · 수치 검산 · 위험 보류 · 사람 중심 통제</div>
</div>
""",
        unsafe_allow_html=True,
    )
