"""Exploratory cross-sectional Pearson + Benjamini-Hochberg FDR evidence.

Avoid naive time-series significance: eligible observations are EXACTLY one
cross-section date with at most one row per issuer/metric. Independent issuer
sampling remains an unverified assumption, never a causal or trading claim.
Only normalized local numeric records; no HTTP, raw-data persistence or export.
"""
from __future__ import annotations

from decimal import Decimal
import math
from typing import Any

from .kuodra_unified_core import _id, _instant


def _bh_fdr(pvalues: list[float]) -> list[float]:
    """Benjamini-Hochberg adjusted q, monotone, including all tested pairs."""
    if not pvalues or any(not 0 <= p <= 1 or not math.isfinite(p) for p in pvalues):
        raise ValueError("STATS_PVALUES_INVALID")
    count = len(pvalues)
    ordered = sorted(range(count), key=lambda i: pvalues[i])
    adjusted = [1.0] * count
    prior = 1.0
    for rank in range(count, 0, -1):
        idx = ordered[rank - 1]
        prior = min(prior, pvalues[idx] * count / rank)
        adjusted[idx] = prior
    return adjusted


def cross_section_fdr(dataset: dict[str, Any], *, metrics: tuple[str, ...],
                      observation_at: str, as_of: str, min_pairs: int = 30,
                      max_results: int = 3) -> dict[str, Any]:
    cutoff, obs = _instant(as_of), _instant(observation_at)
    if (type(dataset) is not dict or dataset.get("schema") != "kuodra.canonical.long.v1"
            or dataset.get("access_level") not in ("PUBLIC", "PRIVATE")
            or not isinstance(dataset.get("records"), list)
            or not dataset["records"] or len(dataset["records"]) != dataset.get("rows")
            or type(metrics) is not tuple or not 2 <= len(metrics) <= 12
            or len(set(metrics)) != len(metrics) or any(not _id(m) for m in metrics)
            or type(min_pairs) is not int or min_pairs < 30
            or type(max_results) is not int or not 1 <= max_results <= 3
            or obs > cutoff):
        raise ValueError("STATS_INPUT_CONTRACT_INVALID")
    cross_section: dict[str, dict[str, float]] = {}
    seen: set[tuple[str, str, str]] = set()
    for row in dataset["records"]:
        if (type(row) is not dict or row.get("dataset_id") != dataset.get("dataset_id")
                or row.get("source_id") != dataset.get("source_id")
                or row.get("access_level") != dataset.get("access_level")
                or row.get("evidence_sha256") != dataset.get("source_sha256")):
            raise ValueError("STATS_LINEAGE_INVALID")
        observed, ready = _instant(row["observation_at"]), _instant(row["available_at"])
        if ready < observed or not _id(row["entity_id"]) or not _id(row["metric_id"]):
            raise ValueError("STATS_ROW_INVALID")
        key = row["entity_id"], row["metric_id"], row["observation_at"]
        if key in seen:
            raise ValueError("STATS_DUPLICATE_OBSERVATION")
        seen.add(key)
        if row["metric_id"] not in metrics or observed != obs or ready > cutoff:
            continue
        try:
            value = float(Decimal(row["value"]))
        except (ValueError, ArithmeticError, TypeError) as exc:
            raise ValueError("STATS_NONFINITE_INPUT") from exc
        if not math.isfinite(value):
            raise ValueError("STATS_NONFINITE_INPUT")
        cross_section.setdefault(row["entity_id"], {})[row["metric_id"]] = value

    # Preserve the entire predeclared testing family, counting pairs that
    # cannot be tested as p=1.0 rather than silently dropping hypotheses.
    family_size = len(metrics) * (len(metrics) - 1) // 2
    family_pvalues = [1.0] * family_size
    pairs = []
    pair_index = -1
    for i, a in enumerate(metrics):
        for b in metrics[i+1:]:
            pair_index += 1
            xys = [(v[a], v[b]) for v in cross_section.values() if a in v and b in v]
            if len(xys) < min_pairs:
                continue
            xs, ys = zip(*xys)
            if len(set(xs)) < 2 or len(set(ys)) < 2:
                continue
            try:
                from scipy.stats import pearsonr
            except ImportError:
                return _withheld(dataset,"SCIPY_OPTIONAL_DEPENDENCY_MISSING",as_of)
            with __import__("warnings").catch_warnings():
                __import__("warnings").simplefilter("error")
                try:
                    r, p = pearsonr(xs, ys)
                except (ValueError, RuntimeWarning):
                    continue
            if not math.isfinite(float(r)) or not math.isfinite(float(p)):
                continue
            family_pvalues[pair_index] = float(p)
            pairs.append({"metric_a": a, "metric_b": b,
                          "pearson_r": round(float(r), 6),
                          "paired_n": len(xys), "p_unadjusted": float(p),
                          "family_index": pair_index})
    if not pairs:
        return _withheld(dataset,"INSUFFICIENT_INDEPENDENT_CROSS_SECTION",as_of)
    adjusted = _bh_fdr(family_pvalues)
    for item in pairs:
        q = adjusted[item.pop("family_index")]

        item["q_bh_fdr"] = round(q, 8)
        item["exploratory_fdr_below_0_05"] = q < 0.05
        item["predictive_claim"] = False
        item["causal_claim"] = False
        item["sampling_independence_verified"] = False
    pairs.sort(key=lambda item: (item["q_bh_fdr"], -abs(item["pearson_r"])))
    return {"schema":"kuodra.insights.cross-sectional-fdr.v1",
            "status":"EXPLORATORY_INDEPENDENCE_UNVERIFIED",
            "dataset_id":dataset["dataset_id"], "access_level":dataset["access_level"],
            "source_sha256":dataset["source_sha256"], "as_of":as_of,
            "observation_at":observation_at, "eligible_entities":len(cross_section),
            "multiple_testing_method":"BENJAMINI_HOCHBERG",
            "pairs_evaluated":len(pairs), "hypotheses_planned":family_size,
            "fdr_denominator":"ALL_PREDECLARED_PAIRS_UNTESTABLE_AS_P_ONE",
            "independence_assumption":"UNVERIFIED_ONE_DATE_DISTINCT_ISSUERS",
            "insights":pairs[:max_results], "model_trained":False,
            "guard":"HOLD", "network_requests":0}


def _withheld(dataset: dict, reason: str, as_of: str) -> dict:
    return {"schema":"kuodra.insights.cross-sectional-fdr.v1", "status":"INSUFFICIENT_EVIDENCE",
            "reason":reason, "dataset_id":dataset["dataset_id"],
            "access_level":dataset["access_level"], "as_of":as_of,
            "insights":[], "model_trained":False, "guard":"HOLD", "network_requests":0}
