"""P161: prevent ambiguous SEC company and sector evidence ownership.

Only validates the *relationships* of supplied role/source identifiers. It
does NOT authenticate an SEC filing, supplier, URL, source hash or legal rights.
"""
from __future__ import annotations

import re
from typing import Any

_SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)


def require_disjoint_cohort_evidence(
    sources: Any, *, target: Any, peers: Any,
    industry_source_ids: Any,
) -> dict:
    """Fail closed when one claimed source backs unrelated CIKs/sector.

    The same SEC company document may legitimately support both annual
    comparisons for ONE issuer. But identical source IDs or SHA256 across two
    DIFFERENT entities (or the sector aggregate) do not constitute separate
    peer evidence. The caller has already validated dates, fields and CIKs.
    """
    if (type(sources) is not list or not 2 <= len(sources) <= 24
            or type(target) is not dict or type(peers) is not list
            or len(peers) > 8
            or type(industry_source_ids) not in (list, tuple)
            or len(industry_source_ids) != 2):
        raise ValueError("COHORT_EVIDENCE_SHAPE_INVALID")
    by_id = {}
    for source in sources:
        if (type(source) is not dict
                or type(source.get("id")) is not str
                or type(source.get("sha256")) is not str
                or _SHA.fullmatch(source["sha256"]) is None
                or source["id"] in by_id):
            raise ValueError("COHORT_EVIDENCE_SOURCE_INVALID")
        by_id[source["id"]] = source
    owners_by_id = {}
    owners_by_digest = {}

    def bind(owner: str, ids: Any) -> None:
        if (type(ids) not in (list, tuple) or len(ids) != 2
                or any(type(sid) is not str or sid not in by_id
                       for sid in ids)):
            raise ValueError("COHORT_EVIDENCE_ROLE_INVALID")
        for sid in ids:
            digest = by_id[sid]["sha256"]
            if (sid in owners_by_id and owners_by_id[sid] != owner
                    or digest in owners_by_digest
                    and owners_by_digest[digest] != owner):
                raise ValueError("COHORT_CROSS_ISSUER_SOURCE_COLLISION")
            owners_by_id[sid] = owner
            owners_by_digest[digest] = owner

    if type(target.get("cik")) is not str:
        raise ValueError("COHORT_EVIDENCE_TARGET_INVALID")
    bind("COMPANY:" + target["cik"], target.get("source_ids"))
    company_ids = {target["cik"]}
    for peer in peers:
        if (type(peer) is not dict or type(peer.get("cik")) is not str
                or peer["cik"] in company_ids):
            raise ValueError("COHORT_EVIDENCE_DUPLICATE_CIK")
        company_ids.add(peer["cik"])
        bind("COMPANY:" + peer["cik"], peer.get("source_ids"))
    bind("SECTOR_AGGREGATE", industry_source_ids)
    return {
        "status": "DISJOINT_SOURCE_CLAIMS_ONLY_UNVERIFIED",
        "target_count": 1,
        "peer_count": len(peers),
        "claimed_role_count": len(company_ids) + 1,
        "source_authenticated": False,
        "rights_verified": False,
    }
