"""Offline private gateway: role denial, anti-egress, no-public-disclosure tests."""
import csv
from datetime import datetime, timezone, timedelta
from io import StringIO
from unittest import TestCase
from unittest.mock import patch
import socket

from proofinvest.kuodra_private_gateway import OwnerLocalGateway, VerifiedPrincipal


def rows(*, entities=1, periods=35, delayed=False):
    out=StringIO(newline="")
    writer=csv.writer(out,lineterminator="\n")
    writer.writerow(("entity_id","metric_id","observation_at","available_at","value","unit"))
    for i in range(periods):
        day=datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(days=i)
        t=day.strftime("%Y-%m-%dT%H:%M:%SZ")
        available=(day+timedelta(days=100)).strftime("%Y-%m-%dT%H:%M:%SZ") if delayed else t
        for k in range(entities):
            name=f"issuer{k}"
            for metric,value in (("x",str(i+k+1)),("y",str(3*(i+k+1)))):
                writer.writerow((name,metric,t,available,value,"count"))
    return out.getvalue().encode()


OWNER=VerifiedPrincipal("owner1","fund1",("owner",),True)
ANALYST=VerifiedPrincipal("analyst1","fund1",("analyst",),True)
VIEWER=VerifiedPrincipal("viewer1","fund1",("viewer",),True)
OTHER=VerifiedPrincipal("outside","fund2",("owner",),True)
UNVERIFIED=VerifiedPrincipal("owner1","fund1",("owner",),False)


class PrivateGatewayTest(TestCase):
    def setUp(self):
        self.vault=OwnerLocalGateway("fund1")
        self.secret=b"top-secret-bytes-must-not-leak"
        self.raw=rows()
        self.vault.ingest_csv(OWNER,raw=self.raw,dataset_id="internal1",
            source_id="synthetic1",access_level="PRIVATE")

    def test_owner_and_analyst_can_read_private_locally(self):
        for principal in (OWNER,ANALYST):
            ans=self.vault.descriptive(principal,dataset_id="internal1",
                metrics=("x","y"),as_of="2026-06-01T00:00:00Z")
            self.assertEqual(ans["status"],"DESCRIPTIVE_ONLY")
            self.assertEqual(ans["guard"],"HOLD")

    def test_deny_unauthorized_role_and_cross_tenant(self):
        for p in (VIEWER,OTHER,UNVERIFIED):
            with self.assertRaisesRegex(PermissionError,"GATEWAY_ACCESS_DENIED"):
                self.vault.descriptive(p,dataset_id="internal1",metrics=("x","y"),
                    as_of="2026-06-01T00:00:00Z")

    def test_no_dataset_existence_or_ids_leak_in_denial(self):
        for name in ("internal1","unknown"):
            with self.assertRaisesRegex(PermissionError,"GATEWAY_ACCESS_DENIED") as err:
                self.vault.descriptive(VIEWER,dataset_id=name,metrics=("x","y"),
                    as_of="2026-06-01T00:00:00Z")
            self.assertNotIn(name,str(err.exception))

    def test_private_public_export_denied_constant_response(self):
        result=self.vault.export_to_public(OWNER,dataset_id="internal1")
        self.assertFalse(result["data_disclosed"])
        self.assertNotIn("internal1",str(result))
        self.assertNotIn("synthetic1",str(result))
        self.assertNotIn("top-secret",str(result))

    def test_public_unlicensed_export_also_denied(self):
        self.vault.ingest_csv(OWNER,raw=self.raw,dataset_id="public1",
            source_id="synthetic2",access_level="PUBLIC")
        self.assertEqual(self.vault.export_to_public(OWNER,dataset_id="public1"),
            self.vault.export_to_public(OWNER,dataset_id="internal1"))

    def test_ingest_owner_only_host_auth(self):
        for p in (ANALYST,OTHER,UNVERIFIED):
            with self.assertRaises(PermissionError):
                self.vault.ingest_csv(p,raw=self.raw,dataset_id="new",
                    source_id="synthetic",access_level="PRIVATE")

    def test_no_overwrite_and_no_raw_in_receipt(self):
        with self.assertRaisesRegex(ValueError,"GATEWAY_DATASET_ALREADY_REGISTERED"):
            self.vault.ingest_csv(OWNER,raw=self.raw,dataset_id="internal1",
                source_id="synthetic1",access_level="PRIVATE")
        vault=OwnerLocalGateway("fund1")
        receipt=vault.ingest_csv(OWNER,raw=self.raw,dataset_id="test2",
            source_id="secret",access_level="PRIVATE")
        self.assertEqual(receipt["rows"],70)
        for forbidden in ("source_sha256","dataset_id","records","secret"):
            self.assertNotIn(forbidden,str(receipt))

    def test_no_socket_egress_in_ingest_analyze_export(self):
        vault=OwnerLocalGateway("fund1")
        with patch.object(socket.socket,"connect",side_effect=AssertionError("EGRESS")) as connect:
            vault.ingest_csv(OWNER,raw=self.raw,dataset_id="test",source_id="fixture",
                             access_level="PRIVATE")
            vault.descriptive(ANALYST,dataset_id="test",metrics=("x","y"),
                as_of="2026-06-01T00:00:00Z")
            vault.export_to_public(OWNER,dataset_id="test")
            connect.assert_not_called()

    def test_mutating_returned_report_does_not_modify_store(self):
        a=self.vault.descriptive(OWNER,dataset_id="internal1",metrics=("x","y"),
            as_of="2026-06-01T00:00:00Z")
        a["insights"][0]["pearson_r"]=-77
        b=self.vault.descriptive(OWNER,dataset_id="internal1",metrics=("x","y"),
            as_of="2026-06-01T00:00:00Z")
        self.assertNotEqual(b["insights"][0]["pearson_r"],-77)

    def test_release_requires_owner(self):
        with self.assertRaises(PermissionError):
            self.vault.release(ANALYST,dataset_id="internal1")
        self.vault.release(OWNER,dataset_id="internal1")
        with self.assertRaises(PermissionError):
            self.vault.export_to_public(OWNER,dataset_id="internal1")

    def test_reject_malformed_roles_and_unverified_subject(self):
        with self.assertRaises(ValueError):
            VerifiedPrincipal("bad id","fund1",("owner",),True)
        with self.assertRaisesRegex(ValueError,"GATEWAY_ROLES_INVALID"):
            self.vault.ingest_csv(OWNER,raw=self.raw,dataset_id="dup2",
                source_id="fixture",access_level="PUBLIC",allowed_roles=("owner",))

    def test_statistical_cross_section_no_issuer_history_pvalue(self):
        result=self.vault.statistical(OWNER,dataset_id="internal1",metrics=("x","y"),
            observation_at="2026-01-20T00:00:00Z",as_of="2026-06-01T00:00:00Z")
        self.assertEqual(result["status"],"INSUFFICIENT_EVIDENCE")
        self.assertEqual(result["guard"],"HOLD")

class SQLiteGatewayEndToEnd(TestCase):
    def test_synthetic_private_sqlite_to_fdr_with_no_export(self):
        import sqlite3
        c=sqlite3.connect(":memory:")
        c.execute("CREATE TABLE records(entity_id TEXT,metric_id TEXT,observation_at TEXT,available_at TEXT,value TEXT,unit TEXT)")
        for idx in range(50):
            for metric, val in (("x",idx+1),("y",(idx+1)*7)):
                c.execute("INSERT INTO records VALUES(?,?,?,?,?,?)",(
                    f"issuer{idx}",metric,"2026-01-01T00:00:00Z","2026-01-01T00:00:00Z",str(val),"count"))
        raw_db=c.serialize(); c.close()
        vault=OwnerLocalGateway("fund1")
        receipt=vault.ingest_sqlite(OWNER,raw_db=raw_db,table="records",dataset_id="sql1",
                                    source_id="fixture",access_level="PRIVATE")
        self.assertEqual(receipt["rows"],100)
        report=vault.statistical(ANALYST,dataset_id="sql1",metrics=("x","y"),
            observation_at="2026-01-01T00:00:00Z",as_of="2026-02-01T00:00:00Z")
        self.assertEqual(report["status"],"EXPLORATORY_INDEPENDENCE_UNVERIFIED")
        self.assertEqual(report["eligible_entities"],50)
        self.assertEqual(report["guard"],"HOLD")
        self.assertFalse(vault.export_to_public(OWNER,dataset_id="sql1")["data_disclosed"])

    def test_sqlite_table_name_injection_denied(self):
        with self.assertRaisesRegex(ValueError,"SQLITE_INPUT_OR_SCOPE_DENIED"):
            from proofinvest.kuodra_unified_core import normalize_local_sqlite
            normalize_local_sqlite(b"fake",table='records"; DROP TABLE',dataset_id="p",
                source_id="fixture",access_level="PRIVATE",consent=True)
