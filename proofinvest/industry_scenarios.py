"""Evidence-linked conditional industry narratives; never forecasts or Guard decisions.

Consumes only the already-validated Engine C report. No network, LLM,
data retention, financial advice, or claims of source authentication.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation


def _reported_percentage(raw):
    if raw is None:
        return None
    if type(raw) is not str or len(raw) > 32:
        raise ValueError("INVALID_SCENARIO_GROWTH")
    try:
        number = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError("INVALID_SCENARIO_GROWTH") from exc
    if not number.is_finite():
        raise ValueError("INVALID_SCENARIO_GROWTH")
    return format(number, "f")


def build_industry_scenarios(report: dict) -> list[dict]:
    """Build observed/base, conditional opportunity, conditional risk cards.

    User-supplied driver labels remain user claims, never true causal drivers.
    Missing directional evidence withholds the scenario rather than inventing
    upside/downside. Source IDs are guaranteed to occur in the supplied report.
    """
    if (type(report) is not dict or report.get("schema") !=
            "kuodra.industry-vision-explanation.v1" or
            report.get("source_authenticated") is not False or
            report.get("industry_outlook_verified") is not False):
        raise ValueError("SCENARIO_REQUIRES_UNVERIFIED_VISION_REPORT")
    sources = report.get("sources")
    if type(sources) is not list:
        raise ValueError("INVALID_SCENARIO_SOURCES")
    source_map = {}
    for source in sources:
        if (type(source) is not dict or type(source.get("id")) is not str or
                source.get("authenticated") is not False or
                source["id"] in source_map):
            raise ValueError("INVALID_SCENARIO_SOURCES")
        source_map[source["id"]] = source

    def refs(ids):
        if (type(ids) is not list or
                any(type(sid) is not str or sid not in source_map for sid in ids)):
            raise ValueError("INVALID_SCENARIO_SOURCE_LINK")
        return list(dict.fromkeys(ids))

    target = report["target"]
    sector = report["industry_series"]
    peers = report["peers"]
    if type(peers) is not list:
        raise ValueError("INVALID_SCENARIO_PEERS")
    target_pct = _reported_percentage(target["growth_pct_reported_input"])
    sector_pct = _reported_percentage(sector["growth_pct_reported_input"])
    peer_pct = _reported_percentage(report["peer_median_growth_pct"])
    observed_refs = refs(target["source_ids"] + sector["source_ids"] +
                         [sid for peer in peers for sid in peer["source_ids"]])
    if target_pct is None or sector_pct is None:
        base_note = "분모가 0인 입력 계열이 있어 기업·산업 성장률 비교를 보류합니다."
    else:
        base_note = (f"입력 자료의 기업 매출 성장률 {target_pct}%와 산업 지표 성장률 "
                     f"{sector_pct}%를 관측치로만 비교합니다.")
        if peer_pct is not None:
            base_note += f" 입력된 동종 기업 성장률 중위값은 {peer_pct}%입니다."
    result = [{
        "id": "OBSERVED_BASE", "title": "관측 기준 (미검증 입력)",
        "kind": "HISTORICAL_INPUT_COMPARISON",
        "condition": "입력 자료의 측정 정의와 출처가 적절하다는 가정",
        "explanation": base_note, "source_ids": observed_refs,
        "verified": False, "future_growth_forecast_pct": None,
        "future_return_forecast_pct": None,
    }]
    drivers = report.get("vision_drivers")
    if type(drivers) is not list:
        raise ValueError("INVALID_SCENARIO_DRIVERS")
    for key, title, directions in (
        ("CONDITIONAL_UPSIDE", "기회 가설 (조건부)", {"OPPORTUNITY", "MIXED"}),
        ("CONDITIONAL_DOWNSIDE", "위험 가설 (조건부)", {"RISK", "MIXED"}),
    ):
        matched = [d for d in drivers if d["direction_operator_supplied"] in directions]
        if not matched:
            result.append({
                "id": key, "title": title, "kind": "WITHHELD_NO_DRIVER",
                "condition": "해당 방향의 출처 연결 동인이 입력되지 않았습니다.",
                "explanation": "미래 성장·시장 성과에 대한 가설을 생성하지 않습니다.",
                "source_ids": [], "verified": False,
                "future_growth_forecast_pct": None,
                "future_return_forecast_pct": None,
            })
            continue
        evidence = refs([sid for driver in matched for sid in driver["source_ids"]])
        labels = [driver["label"] for driver in matched]
        result.append({
            "id": key, "title": title, "kind": "CONDITIONAL_OPERATOR_HYPOTHESIS",
            "condition": "사용자 입력 동인의 진위·영향·지속성이 추가 확인되는 경우",
            "explanation": ("사용자 입력 " +
                            ("기회" if key == "CONDITIONAL_UPSIDE" else "위험") +
                            " 동인: " + "; ".join(labels) +
                            ". 인과관계와 방향은 검증되지 않았으며 수치 전망은 생성하지 않습니다."),
            "source_ids": evidence, "verified": False,
            "future_growth_forecast_pct": None,
            "future_return_forecast_pct": None,
        })
    return result
