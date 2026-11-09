"""One-use owner-scoped offline identity agreement tests."""
from __future__ import annotations
import json
import socket
import unittest
from hashlib import sha256
from unittest.mock import patch
from proofinvest.kuodra_identity_approval import (
    approve_local_identity_mapping, consume_local_identity_mapping)
from proofinvest.kuodra_private_gateway import OwnerLocalGateway, VerifiedPrincipal
from proofinvest.kuodra_synthetic_demo import _csv, _table_rows

OWNER=VerifiedPrincipal("ownerTest","fundTest",("owner",),True)
ANALYST=VerifiedPrincipal("analystTest","fundTest",("analyst",),True)
SECOND_ANALYST=VerifiedPrincipal("otherAnalyst","fundTest",("analyst",),True)
WRONG=VerifiedPrincipal("another","anotherFund",("analyst",),True)
AS_OF="2026-01-01T00:00:00Z"

class IdentityMappingApprovalTests(unittest.TestCase):
    def setUp(self):
        self.vault=OwnerLocalGateway("fundTest")
        public=_csv(_table_rows(metric="factor"))
        private=_csv(_table_rows(metric="outcome"))
        self.vault.ingest_csv(OWNER,raw=public,dataset_id="publicTest",
                              source_id="source1",access_level="PUBLIC")
        self.vault.ingest_csv(OWNER,raw=private,dataset_id="privateTest",
                              source_id="source2",access_level="PRIVATE")
        self.params=dict(public_dataset_id="publicTest",
            private_dataset_id="privateTest",
            public_sha256=sha256(public).hexdigest(),
            private_sha256=sha256(private).hexdigest(),
            aliases={r["entity_id"]:r["entity_id"]
                     for r in self.vault._datasets["publicTest"]["records"]},
            as_of=AS_OF,delegate_subject=ANALYST.subject,
            acknowledge_unverified_issuer_identity=True)
    def approve(self,principal=OWNER,**kwargs):
        return approve_local_identity_mapping(
            self.vault,principal,**dict(self.params,**kwargs))
    def consume(self,token,principal=ANALYST,**kwargs):
        opts=dict(token=token,public_dataset_id="publicTest",
                  private_dataset_id="privateTest",as_of=AS_OF)
        opts.update(kwargs)
        return consume_local_identity_mapping(self.vault,principal,**opts)
    def test_approved_source_scoped_token_one_use_no_raw_names(self):
        before=json.dumps(self.vault._datasets,sort_keys=True)
        t=self.approve()
        view,r=self.consume(t["one_use_token"])
        self.assertEqual(t["mapping_sha256"],r["mapping_sha256"])
        self.assertTrue(r["single_use_consumed"])
        self.assertFalse(r["cross_source_identity_verified"])
        self.assertEqual(before,json.dumps(self.vault._datasets,sort_keys=True))
        self.assertFalse(self.vault._local_identity_approvals)
        with self.assertRaises(PermissionError):
            self.consume(t["one_use_token"])
        for secret in ("fundTest","ownerTest","privateTest","fictitiousIssuer"):
            self.assertNotIn(secret,json.dumps(r))
        self.assertEqual(view._datasets["publicTest"]["rows"],
                         self.vault._datasets["publicTest"]["rows"])
    def test_owner_only_and_explicit_ack(self):
        with self.assertRaises(PermissionError):
            self.approve(principal=ANALYST)
        with self.assertRaisesRegex(ValueError,"IDENTITY_OWNER_ACK_REQUIRED"):
            self.approve(acknowledge_unverified_issuer_identity=False)
        self.assertFalse(self.vault._local_identity_approvals)
    def test_wrong_vault_actor_and_as_of_never_consume(self):
        t=self.approve()["one_use_token"]
        with self.assertRaises(PermissionError):
            self.consume(t,principal=WRONG)
        with self.assertRaises(PermissionError):
            self.consume(t,as_of="2026-03-01T00:00:00Z")
        with self.assertRaises(PermissionError):
            consume_local_identity_mapping(OwnerLocalGateway("fundTest"),ANALYST,
                token=t,public_dataset_id="publicTest",
                private_dataset_id="privateTest",as_of=AS_OF)
        self.assertEqual(len(self.vault._local_identity_approvals),1)
        self.assertTrue(self.consume(t)[1]["single_use_consumed"])
    def test_same_owner_analyst_cannot_use_token_approved_for_other_subject(self):
        t=self.approve()["one_use_token"]
        with self.assertRaisesRegex(PermissionError,"IDENTITY_APPROVAL_SCOPE_MISMATCH"):
            self.consume(t,principal=SECOND_ANALYST)
        self.assertEqual(len(self.vault._local_identity_approvals),1)
        self.assertTrue(self.consume(t)[1]["single_use_consumed"])

    def test_invalid_delegate_rejected_before_token_creation(self):
        for subject in ("", "other analyst", None):
            with self.subTest(subject=subject),self.assertRaises(ValueError):
                self.approve(delegate_subject=subject)
        self.assertFalse(self.vault._local_identity_approvals)

    def test_tampered_records_invalidate_approval_even_if_raw_sha_same(self):
        t=self.approve()["one_use_token"]
        self.vault._datasets["publicTest"]["records"][0]["value"]="123456"
        with self.assertRaisesRegex(ValueError,"IDENTITY_APPROVED_SNAPSHOT_CHANGED"):
            self.consume(t)
        self.assertFalse(self.vault._local_identity_approvals)
    def test_changed_source_or_issuer_map_prevents_approval(self):
        for params in (dict(public_sha256="a"*64),
                       dict(aliases={"fake":"fake"})):
            with self.subTest(params=params),self.assertRaises(ValueError):
                self.approve(**params)
        self.assertFalse(self.vault._local_identity_approvals)
    def test_released_public_source_revokes_ticket_even_if_identically_reimported(self):
        ticket=self.approve()["one_use_token"]
        self.vault.release(OWNER,dataset_id="publicTest")
        self.assertFalse(self.vault._local_identity_approvals)
        self.vault.ingest_csv(OWNER,raw=_csv(_table_rows(metric="factor")),
                              dataset_id="publicTest",source_id="source1",
                              access_level="PUBLIC")
        with self.assertRaises(PermissionError):
            self.consume(ticket)

    def test_released_private_source_revokes_ticket_even_if_identically_reimported(self):
        ticket=self.approve()["one_use_token"]
        self.vault.release(OWNER,dataset_id="privateTest")
        self.assertFalse(self.vault._local_identity_approvals)
        self.vault.ingest_csv(OWNER,raw=_csv(_table_rows(metric="outcome")),
                              dataset_id="privateTest",source_id="source2",
                              access_level="PRIVATE")
        with self.assertRaises(PermissionError):
            self.consume(ticket)

    def test_unrelated_release_does_not_revoke_other_pending_ticket(self):
        self.vault.ingest_csv(OWNER,raw=_csv(_table_rows(metric="factor")),
                              dataset_id="unrelatedPublic",source_id="unrelatedSource",
                              access_level="PUBLIC")
        ticket=self.approve()["one_use_token"]
        self.vault.release(OWNER,dataset_id="unrelatedPublic")
        self.assertEqual(len(self.vault._local_identity_approvals),1)
        self.assertTrue(self.consume(ticket)[1]["single_use_consumed"])

    def test_offline_socket_denied_during_approval_and_use(self):
        with patch.object(socket.socket,"connect",
                          side_effect=AssertionError("NO_NETWORK")) as connect:
            t=self.approve()["one_use_token"]
            self.consume(t)
            connect.assert_not_called()
if __name__=="__main__": unittest.main()
