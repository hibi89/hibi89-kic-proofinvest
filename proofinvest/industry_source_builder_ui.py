"""P96: owner-held raw sector CSV + issuer/peer CompanyFacts -> Engine C UI.

Reuses existing offline Engine C packet builder and peer source pins.
No real provider authentication, user-data persistence, outbound HTTP,
Guard invocation, trade, forecast or remote LLM.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any

from .industry_packet_builder import build_industry_packet, _MAX_SECTOR_BYTES
from .local_sec_packet import _MAX_FILE_BYTES

_MAX_PEERS = 8
_MAX_ALL_PEERS_BYTES = 48_000_000


def _uploaded_bytes(upload: Any, limit: int, code: str) -> bytes:
    if upload is None or type(getattr(upload, "size", None)) is not int:
        raise ValueError(code)
    if not 0 < upload.size <= limit:
        raise ValueError(code)
    raw = upload.getvalue()
    if type(raw) is not bytes or len(raw) != upload.size:
        raise ValueError(code)
    return raw


def prepare_ui_industry_packet(
    *, target_companyfacts: bytes, target_cik: str,
    target_accession: str, target_name: str,
    peer_uploads: list[tuple[str, str, str, Any]],
    sector_upload: Any, sector_url: str, sector_published_at: str,
    as_of: str, prior_end: str, current_end: str,
    industry_name: str, series_name: str, series_kind: str,
    sector_unit: str,
) -> tuple[bytes, list[tuple[str, str, Any]]]:
    """Build a source-pinned packet and return the SAME peer upload handles.

    No extra copies of uploaded peers are stored in Streamlit session_state.
    A later Guard click rereads each handle and verifies the exact SHA in
    the packet; changing any bytes after this call invalidates the review.
    """
    if type(target_companyfacts) is not bytes or not (
        0 < len(target_companyfacts) <= _MAX_FILE_BYTES
    ):
        raise ValueError("P96_TARGET_COMPANYFACTS_INVALID")
    if type(peer_uploads) is not list or not 1 <= len(peer_uploads) <= _MAX_PEERS:
        raise ValueError("P96_PEER_COUNT_INVALID")
    if any(type(p) is not tuple or len(p) != 4 for p in peer_uploads):
        raise ValueError("P96_PEER_FIELDS_INVALID")
    seen = {target_cik}
    peers = []
    inputs = []
    peer_size = len(target_companyfacts)
    for cik, accession, name, upload in peer_uploads:
        if (type(cik) is not str or cik in seen
                or type(accession) is not str or type(name) is not str):
            raise ValueError("P96_DUPLICATE_OR_INVALID_PEER")
        seen.add(cik)
        original = _uploaded_bytes(
            upload, _MAX_FILE_BYTES, "P96_BAD_PEER_COMPANYFACTS_UPLOAD",
        )
        peer_size += len(original)
        if peer_size > _MAX_ALL_PEERS_BYTES:
            raise ValueError("P96_PEER_TOTAL_MEMORY_BUDGET")
        peers.append((cik, accession, name, original))
        inputs.append((cik, accession, upload))
    csv = _uploaded_bytes(
        sector_upload, _MAX_SECTOR_BYTES, "P96_BAD_SECTOR_CSV_UPLOAD",
    )
    result = build_industry_packet(
        target=(target_cik, target_accession, target_name,
                target_companyfacts),
        peers=peers, sector_csv=csv, sector_url=sector_url,
        sector_published_at=sector_published_at, as_of=as_of,
        prior_end=prior_end, current_end=current_end,
        industry_name=industry_name, series_name=series_name,
        series_kind=series_kind, sector_unit=sector_unit,
    )
    return result, inputs


def render_local_industry_builder(
    st, *, uploaded_target_sources: dict[str, Any],
    operator_archive: Any, request: dict[str, Any],
    source_loader,
) -> tuple[bytes | None, list[tuple[str, str, Any]]]:
    """Optional Streamlit controls, no file paths and no automatic Guard.

    Source_loader is existing _selected_workspace_sources; it is called
    ONLY in operator-enabled mode, and binds the selected SEC ZIP's identity
    and UTC statement to the current human-entered request.
    """
    st.subheader("Engine C · 산업 CSV + 경쟁사 원본에서 자동 구성 (선택)")
    enabled = st.checkbox(
        "산업 CSV·경쟁사 CompanyFacts로 Engine C 구성 (로컬, 출처 미인증)",
        key="kuodra_build_industry_from_sources", value=False,
    )
    if not enabled:
        return None, []
    st.caption(
        "산업 지표는 period_end,value 두 열·정확히 2개 연도. "
        "1~8개 경쟁사의 CIK·해당 10-K 접수번호·CompanyFacts를 모두 지정합니다. "
        "검증된 원본을 저장하지 않고 현재 로컬 화면에서만 분석합니다."
    )
    name = st.text_input(
        "분석 기업 표시명", key="kuodra_builder_target_name", max_chars=90,
    )
    industry = st.text_input(
        "산업 이름", key="kuodra_builder_industry_name", max_chars=160,
    )
    series_name = st.text_input(
        "산업 지표명", key="kuodra_builder_series_name", max_chars=160,
    )
    kind = st.selectbox(
        "산업 지표 종류",
        ["PRODUCTION_INDEX", "DEMAND_INDEX",
         "REAL_GROSS_OUTPUT", "NOMINAL_INDUSTRY_SALES"],
        key="kuodra_builder_series_kind",
    )
    unit = st.text_input(
        "산업 지표 단위", key="kuodra_builder_sector_unit", max_chars=50,
    )
    sector_url = st.text_input(
        "산업 CSV 출처 HTTPS URL (사용자 주장)",
        key="kuodra_builder_sector_url", max_chars=350,
    )
    sector_published_at = st.text_input(
        "산업 CSV 공개일 (YYYY-MM-DD, 사용자 주장)",
        key="kuodra_builder_sector_date", max_chars=10,
    )
    sector_upload = st.file_uploader(
        "2개 연도 산업 지표 CSV (period_end,value)",
        type=["csv"], key="kuodra_builder_sector_csv",
    )
    count = st.number_input(
        "경쟁사 수 (1~8)", min_value=1, max_value=8, value=1,
        step=1, key="kuodra_builder_peer_count",
    )
    peers = []
    for i in range(int(count)):
        label = str(i + 1)
        cik = st.text_input(
            f"경쟁사 {label} CIK 10자리",
            key=f"kuodra_builder_peer_cik_{i}", max_chars=10,
        )
        accession = st.text_input(
            f"경쟁사 {label} 10-K 접수번호",
            key=f"kuodra_builder_peer_accession_{i}", max_chars=20,
        )
        peer_name = st.text_input(
            f"경쟁사 {label} 표시명",
            key=f"kuodra_builder_peer_name_{i}", max_chars=90,
        )
        upload = st.file_uploader(
            f"경쟁사 {label} SEC CompanyFacts JSON",
            type=["json"], key=f"kuodra_builder_peer_upload_{i}",
        )
        peers.append((cik, accession, peer_name, upload))
    if (not all((name, industry, series_name, unit,
                 sector_url, sector_published_at))
            or sector_upload is None
            or any(not all((cik, acc, title, upload))
                   for cik, acc, title, upload in peers)):
        st.info("산업 CSV·출처·공개일과 모든 경쟁사의 원본/CIK/접수번호를 입력해야 구성됩니다.")
        return None, []

    try:
        # Reject a source ZIP with changed declared issuer/clock. Do not keep
        # original or generated JSON in session state between reruns.
        target_raw = source_loader(
            uploaded_target_sources, operator_archive, request=request,
        )["companyfacts"]
        packet, peer_inputs = prepare_ui_industry_packet(
            target_companyfacts=target_raw,
            target_cik=request["cik"],
            target_accession=request["accession"], target_name=name,
            peer_uploads=peers, sector_upload=sector_upload,
            sector_url=sector_url,
            sector_published_at=sector_published_at,
            as_of=request["as_of"],
            prior_end=request["prior_end"],
            current_end=request["current_end"],
            industry_name=industry, series_name=series_name,
            series_kind=kind, sector_unit=unit,
        )
    except (ValueError, TypeError, OSError, OverflowError,
            RecursionError, UnicodeError, KeyError):
        st.error(
            "Engine C 자동 구성 차단: 회사·기간·원본 해시·연간 매출·"
            "산업 CSV·공개일·출처가 일치하지 않습니다."
        )
        return None, []
    st.success("원본 기반 Engine C 입력 구성 완료 · SEC 출처 미인증 · Guard 미실행")
    st.json({
        "generated_industry_sha256": sha256(packet).hexdigest(),
        "peer_source_count": len(peers),
        "source_authenticated": False,
        "sector_publisher_verified": False,
        "real_world_verified": False,
        "audit_written": False,
        "external_http_called": False,
        "trade_executed": False,
    })
    return packet, peer_inputs
