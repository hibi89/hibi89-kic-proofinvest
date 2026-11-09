"""Owner-attested, source-bound entity aliases for LOCAL hybrid analysis only.

Aliases are not proof that public and private issuer identities match. Never
export mappings or private-derived analytics to public/remote destinations.
This module is a local exploratory adapter, not IAM or a source authenticator.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import re
from typing import Any

from .kuodra_hybrid import analyze_local_hybrid, _approved_snapshot_digest
from .kuodra_group_time_ml import evaluate_owner_local_hybrid_group
from .kuodra_private_gateway import OwnerLocalGateway, VerifiedPrincipal
from .kuodra_unified_core import _id, _instant

_SHA = re.compile(r'[0-9a-f]{64}\Z', re.ASCII)


def _prepare_owner_alias_view(
        vault: OwnerLocalGateway, principal: VerifiedPrincipal, *,
        public_dataset_id: str, private_dataset_id: str,
        public_sha256: str, private_sha256: str,
        aliases: dict[str, str], as_of: str) -> tuple[OwnerLocalGateway, str]:
    """Reconcile explicitly mapped local entities, never silently join names.

    All public/private row-level identifiers remain only inside temporary
    memory. Even a valid digest and an owner role cannot prove external issuer
    identity or institute authentication. Only exploratory HOLD is returned.
    """
    if (type(vault) is not OwnerLocalGateway or type(principal) is not VerifiedPrincipal
            or not _id(public_dataset_id) or not _id(private_dataset_id)
            or public_dataset_id == private_dataset_id
            or not (type(public_sha256) is str and _SHA.fullmatch(public_sha256))
            or not (type(private_sha256) is str and _SHA.fullmatch(private_sha256))
            or type(aliases) is not dict or not 1 <= len(aliases) <= 200
            or any(not _id(k) or not _id(v) for k, v in aliases.items())
            or len(set(aliases.values())) != len(aliases)):
        raise ValueError('ALIAS_MAPPING_CONTRACT_INVALID')
    _instant(as_of)
    # Owner authority is required even for local fictional aliases. A caller
    # supplied host-authenticated boolean is not an actual IAM verification.
    vault._check(principal, write=True)
    if 'owner' not in principal.roles:
        raise PermissionError('ALIAS_OWNER_ONLY')
    # Check both scopes before inspecting any source IDs.
    vault._check(principal, dataset_id=public_dataset_id)
    vault._check(principal, dataset_id=private_dataset_id)
    public = deepcopy(vault._datasets[public_dataset_id])
    private = deepcopy(vault._datasets[private_dataset_id])
    if (public.get('schema') != 'kuodra.canonical.long.v1'
            or private.get('schema') != 'kuodra.canonical.long.v1'
            or public.get('access_level') != 'PUBLIC'
            or private.get('access_level') != 'PRIVATE'
            or public.get('source_sha256') != public_sha256
            or private.get('source_sha256') != private_sha256
            or public.get('source_authenticated') is not False
            or private.get('source_authenticated') is not False
            or public.get('source_rights_verified') is not False
            or private.get('source_rights_verified') is not False
            or type(public.get('records')) is not list
            or type(private.get('records')) is not list):
        raise ValueError('ALIAS_SOURCE_RECEIPT_OR_SCOPE_INVALID')
    pub_ids = {r.get('entity_id') for r in public['records'] if type(r) is dict}
    priv_ids = {r.get('entity_id') for r in private['records'] if type(r) is dict}
    if (not set(aliases).issubset(pub_ids)
            or not set(aliases.values()).issubset(priv_ids)):
        raise ValueError('ALIAS_SOURCE_ENTITY_MISSING')
    keys = set(aliases.values())
    public['records'] = [dict(r, entity_id=aliases[r['entity_id']])
                         for r in public['records'] if r['entity_id'] in aliases]
    private['records'] = [r for r in private['records'] if r['entity_id'] in keys]
    public['rows'] = len(public['records'])
    private['rows'] = len(private['records'])
    digest_data = {'public_sha256': public_sha256, 'private_sha256': private_sha256,
                   'as_of': as_of, 'mapping': sorted(aliases.items())}
    digest = sha256((json.dumps(digest_data, sort_keys=True,
                             separators=(',', ':'), ensure_ascii=True) + '\n').encode()).hexdigest()
    # Ephemeral scoped view; source digests are of original bytes, while the
    # separately recorded mapping digest describes the asserted transform.
    temporary = OwnerLocalGateway(principal.owner_id)
    temporary._register(public_dataset_id, public, ('analyst',))
    temporary._register(private_dataset_id, private, ('analyst',))
    temporary._approved_hybrid_scope = (
        public_dataset_id, private_dataset_id, as_of,
        _approved_snapshot_digest(temporary._datasets[public_dataset_id]),
        _approved_snapshot_digest(temporary._datasets[private_dataset_id]))
    return temporary, digest


def analyze_owner_alias_hybrid(
        vault: OwnerLocalGateway, principal: VerifiedPrincipal, *,
        public_dataset_id: str, private_dataset_id: str,
        public_sha256: str, private_sha256: str,
        aliases: dict[str, str], as_of: str,
        metrics: tuple[str, ...], observation_at: str) -> dict[str, Any]:
    """Owner-scoped, explicitly mapped private cross-sectional exploration."""
    _instant(observation_at)
    temporary, digest = _prepare_owner_alias_view(
        vault, principal, public_dataset_id=public_dataset_id,
        private_dataset_id=private_dataset_id,
        public_sha256=public_sha256, private_sha256=private_sha256,
        aliases=aliases, as_of=as_of)
    result = analyze_local_hybrid(temporary, principal,
        public_dataset_id=public_dataset_id,
        private_dataset_id=private_dataset_id,
        as_of=as_of, mode='cross_section', metrics=metrics,
        observation_at=observation_at)
    if result.get('guard') != 'HOLD' or result.get('public_export_allowed') is not False:
        raise ValueError('ALIAS_RESULT_SCOPE_INVALID')
    return {
        'schema': 'kuodra.local-operator-alias-review.v1',
        'status': 'OWNER_LOCAL_EXPLORATION_ONLY',
        'decision': 'HOLD', 'mapping_attestation': 'OWNER_ASSERTED_NOT_SOURCE_VERIFIED',
        'cross_source_entity_link_verified': False,
        'alias_count': len(aliases), 'mapping_sha256': digest,
        'source_hashes': {'public': public_sha256, 'private': private_sha256},
        'joined_entity_times': result['joined_entity_times'],
        'analysis': result['analysis'],
        'public_export_allowed': False, 'external_llm_allowed': False,
        'host_iam_verified': False, 'host_egress_verified': False,
        'source_rights_verified': False, 'network_requests': 0,
        'data_rows_disclosed': False, 'trade_authorized': False,
    }



def analyze_owner_alias_group_ml(
        vault: OwnerLocalGateway, principal: VerifiedPrincipal, *,
        public_dataset_id: str, private_dataset_id: str,
        public_sha256: str, private_sha256: str,
        aliases: dict[str, str], as_of: str,
        target_metric: str, feature_metrics: tuple[str, ...]) -> dict[str, Any]:
    """Owner-declared cross-source names -> existing issuer/time holdout ML.

    This is exploratory only. Reuses the exact existing future-label embargo,
    disjoint issuer split, out-of-time CV/Dummy benchmark and HOLD policy.
    Aliases are not source authentication, external data rights, or a
    permission to publish model-derived conclusions.
    """
    temporary, digest = _prepare_owner_alias_view(
        vault, principal, public_dataset_id=public_dataset_id,
        private_dataset_id=private_dataset_id,
        public_sha256=public_sha256, private_sha256=private_sha256,
        aliases=aliases, as_of=as_of)
    result = evaluate_owner_local_hybrid_group(
        temporary, principal,
        public_dataset_id=public_dataset_id,
        private_dataset_id=private_dataset_id,
        target_metric=target_metric,
        feature_metrics=feature_metrics, as_of=as_of)
    if (result.get('guard') != 'HOLD' or result.get('public_export_allowed') is not False
            or result.get('access_level') != 'PRIVATE'
            or result.get('data_rows_disclosed') is not False
            or type(result.get('analysis')) is not dict
            or result['analysis'].get('production_ready') is not False
            or result['analysis'].get('calibrated_probability') is not None):
        raise ValueError('ALIAS_GROUP_ML_NOT_RESTRICTED')
    return {
        'schema': 'kuodra.local-operator-alias-group-time.v1',
        'status': 'OWNER_LOCAL_EXPLORATION_ONLY', 'decision': 'HOLD',
        'mapping_attestation': 'OWNER_ASSERTED_NOT_SOURCE_VERIFIED',
        'cross_source_entity_link_verified': False,
        'alias_count': len(aliases), 'mapping_sha256': digest,
        'source_hashes': {'public': public_sha256, 'private': private_sha256},
        'analysis': result['analysis'], 'public_export_allowed': False,
        'external_llm_allowed': False, 'host_iam_verified': False,
        'host_egress_verified': False, 'source_rights_verified': False,
        'network_requests': 0, 'data_rows_disclosed': False,
        'trade_authorized': False,
    }
