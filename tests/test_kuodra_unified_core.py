"""Synthetic public/private canonical and no-future-data regression tests."""
import csv
from io import StringIO
import unittest
from proofinvest.kuodra_unified_core import normalize_local_csv, observed_relationships


def fixture(*, private=False, delayed=False, bad_unit=False):
    f=StringIO(newline="")
    w=csv.writer(f, lineterminator="\n")
    w.writerow(("entity_id","metric_id","observation_at","available_at","value","unit"))
    for i in range(24):
        d=f"2026-01-{i+1:02d}T00:00:00Z"
        for metric,val,unit in (("x",str(i+1),"count"),("y",str((i+1)*2),"usd")):
            r=d if not delayed else "2026-12-31T00:00:00Z"
            w.writerow(("issuerA",metric,d,r,val,unit if not(bad_unit and i == 6 and metric=="y") else "eur"))
    return normalize_local_csv(f.getvalue().encode(),dataset_id="testLocal",source_id="fixture",
        access_level="PRIVATE" if private else "PUBLIC", consent=private)


class CanonicalTest(unittest.TestCase):
    def test_public_and_private_share_schema(self):
        a,b=fixture(),fixture(private=True)
        self.assertEqual([set(r) for r in a["records"]],[set(r) for r in b["records"]])
        self.assertFalse(a["source_authenticated"])
        self.assertFalse(b["host_egress_policy_verified"])
        self.assertEqual(a["network_requests"],b["network_requests"])

    def test_insights_are_descriptive_only(self):
        r=observed_relationships(fixture(),metrics=("x","y"),as_of="2026-02-01T00:00:00Z")
        self.assertEqual(r["status"],"DESCRIPTIVE_ONLY")
        self.assertEqual(r["insights"][0]["paired_n"],24)
        self.assertAlmostEqual(r["insights"][0]["pearson_r"],1.0)
        self.assertFalse(r["model_trained"])
        self.assertEqual(r["guard"],"HOLD")
        self.assertEqual(r["multiple_testing_status"],"NOT_ADJUSTED_NO_SIGNIFICANCE_CLAIM")

    def test_future_only_values_are_hidden(self):
        d=fixture(delayed=True)
        r=observed_relationships(d,metrics=("x","y"),as_of="2026-02-01T00:00:00Z")
        self.assertEqual(r["status"],"INSUFFICIENT_EVIDENCE")
        self.assertEqual(r["insights"],[])

    def test_historical_association_rejects_future_observation_backdated_release(self):
        # A locally normalized source may be represented by mutable records.
        # Altering its later observation to claim a release before observation
        # previously smuggled a future pair into the 2026-01-17 review.
        d=fixture()
        valid=observed_relationships(d,metrics=("x","y"),
            as_of="2026-01-17T00:00:00Z")
        self.assertEqual(valid["insights"][0]["paired_n"],17)
        for row in d["records"]:
            if row["observation_at"]>"2026-01-17T00:00:00Z":
                row["available_at"]="2026-01-01T00:00:00Z"
        with self.assertRaisesRegex(ValueError,"INSIGHT_RELEASE_ORDER_INVALID"):
            observed_relationships(d,metrics=("x","y"),
                as_of="2026-01-17T00:00:00Z")

    def test_private_requires_consent(self):
        with self.assertRaisesRegex(ValueError,"CANONICAL_SOURCE_POLICY_DENIED"):
            normalize_local_csv(b"a",dataset_id="d",source_id="s",access_level="PRIVATE")

    def test_units_mismatch_fails(self):
        with self.assertRaisesRegex(ValueError,"CANONICAL_UNIT_CONFLICT"):
            fixture(bad_unit=True)

    def test_reject_release_before_observation(self):
        raw=("entity_id,metric_id,observation_at,available_at,value,unit\n"
             "issuerA,x,2026-02-01T00:00:00Z,2026-01-01T00:00:00Z,1,count\n").encode()
        with self.assertRaisesRegex(ValueError,"CANONICAL_RELEASE_PRECEDES_OBSERVATION"):
            normalize_local_csv(raw,dataset_id="d",source_id="s",access_level="PUBLIC")

    def test_duplicate_row_fails(self):
        row="issuerA,x,2026-01-01T00:00:00Z,2026-01-01T00:00:00Z,1,count\n"
        raw=("entity_id,metric_id,observation_at,available_at,value,unit\n"+row+row).encode()
        with self.assertRaisesRegex(ValueError,"CANONICAL_DUPLICATE"):
            normalize_local_csv(raw,dataset_id="d",source_id="s",access_level="PUBLIC")

    def test_reject_export_lineage_tamper(self):
        d=fixture()
        d["records"][0]["access_level"]="PRIVATE"
        with self.assertRaisesRegex(ValueError,"INSIGHT_SOURCE_LINEAGE_INVALID"):
            observed_relationships(d,metrics=("x","y"),as_of="2026-02-01T00:00:00Z")

    def test_reject_csv_formula_in_number(self):
        raw=("entity_id,metric_id,observation_at,available_at,value,unit\n"
             "issuerA,x,2026-01-01T00:00:00Z,2026-01-01T00:00:00Z,=1+1,count\n").encode()
        with self.assertRaisesRegex(ValueError,"CANONICAL_VALUE_INVALID"):
            normalize_local_csv(raw,dataset_id="d",source_id="s",access_level="PUBLIC")

    def test_unknown_rights_is_not_licensed(self):
        d=fixture()
        self.assertFalse(d["source_rights_verified"])
        self.assertFalse(d["publisher_vintage_verified"])

if __name__ == "__main__": unittest.main()


class SQLiteTest(unittest.TestCase):
    @staticmethod
    def _database():
        import sqlite3
        c=sqlite3.connect(":memory:")
        c.execute("CREATE TABLE records(entity_id TEXT,metric_id TEXT,observation_at TEXT,available_at TEXT,value TEXT,unit TEXT)")
        c.execute("INSERT INTO records VALUES(?,?,?,?,?,?)",(
            "issuerA","sales","2026-01-01T00:00:00Z","2026-01-03T00:00:00Z","24.5","usd"))
        data=c.serialize(); c.close();return data

    def test_sqlite_read_only_normalizes_same_contract(self):
        from proofinvest.kuodra_unified_core import normalize_local_sqlite
        from hashlib import sha256
        raw=self._database()
        d=normalize_local_sqlite(raw,table="records",dataset_id="approved",source_id="upload",
            access_level="PRIVATE",consent=True)
        self.assertEqual(d["source_sha256"],sha256(raw).hexdigest())
        self.assertEqual(d["records"][0]["evidence_sha256"],d["source_sha256"])
        self.assertEqual(d["source_type"],"SQLITE_IN_MEMORY_READ_ONLY")
        self.assertFalse(d["host_egress_policy_verified"])

    def test_sqlite_rejects_table_injection(self):
        from proofinvest.kuodra_unified_core import normalize_local_sqlite
        with self.assertRaisesRegex(ValueError,"SQLITE_INPUT_OR_SCOPE_DENIED"):
            normalize_local_sqlite(self._database(),table='records"; DROP TABLE',
                dataset_id="approved",source_id="upload",access_level="PUBLIC")

    def test_sqlite_private_missing_consent(self):
        from proofinvest.kuodra_unified_core import normalize_local_sqlite
        with self.assertRaisesRegex(ValueError,"SQLITE_INPUT_OR_SCOPE_DENIED"):
            normalize_local_sqlite(self._database(),table="records",dataset_id="approved",
                source_id="upload",access_level="PRIVATE")