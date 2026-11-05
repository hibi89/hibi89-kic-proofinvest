"""P236 official SEC public EDGAR general reuse policy, not data-origin auth."""
from __future__ import annotations


def render_sec_public_filing_policy(st, reviewed_filing: dict) -> None:
    from .sec_public_filing_policy import (
        verify_official_public_edgar_reuse_policy,
    )
    x=verify_official_public_edgar_reuse_policy(
        filing_reference=reviewed_filing.get("public_filing_url"),
        issuer=reviewed_filing.get("ticker"),
        accession=reviewed_filing.get("accession"),
        as_of="2026-11-05",
        intended_use="PUBLIC_EDGAR_FACTS_IN_HUMAN_REPORT",
    )
    # The result only acknowledges general SEC website reuse rules; it
    # does NOT approve any downloaded file, individual vendor or AI use.
    with st.expander("SEC 공개 EDGAR 자료 재사용 정책 · 원본 인증과 별개",expanded=False):
        if x.get("status") != "OFFICIAL_PUBLIC_EDGAR_GENERAL_REUSE_POLICY_VERIFIED":
            st.warning("SEC 정책 일반 범위/기존 출처 참조 검증을 완료하지 못했습니다.")
            return
        # A general policy notice is NOT a successful verification of the
        # currently selected issuer or document; avoid global success badges.
        st.info(
            "SEC 공식 지침 확인: EDGAR 공개 공시자료의 일반적인 "
            "접근·복사·재사용·재배포는 허용됩니다."
        )
        st.markdown(
            "[SEC Webmaster FAQ](https://www.sec.gov/files/about/webmaster-faq.htm)"
            " · [SEC Website Dissemination]"
            "(https://www.sec.gov/about/privacy-information)"
        )
        st.warning(
            "이는 공시 재사용에 관한 SEC의 일반 정책입니다. 이 화면에 사용된 "
            "개별 SEC 원본 HTML 바이트·해시·접속 경로 인증은 미완료입니다. "
            "SEC 로고·상표 사용권, 별도 제3자 이미지·시장 주가·NDX·"
            "비교기업 제공자 사용권, 외부 AI 처리·실서비스 배포는 승인되지 않았습니다. "
            "과거 SEC 403 차단 주소 재시도도 허용하지 않습니다."
        )
        st.json({
            "edgar_public_filing_general_reuse_policy_verified":True,
            "policy_sources":x["official_policy_evidence_urls"],
            "manual_filing_reference_reviewed":True,
            "original_sec_bytes_authenticated":False,
            "individual_source_license_and_origin_verified":False,
            "SEC_mark_usage_allowed":False,
            "NDX_vendor_AI_production_entitlement":False,
            "sec_network_retry_authorized":False,
            "guard":"HOLD","trades":0,
        })
