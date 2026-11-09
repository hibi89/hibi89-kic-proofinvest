"""Offline cross-sectional BH FDR, release-time and leakage controls."""
import csv
from io import StringIO
from unittest import TestCase
from unittest.mock import patch
from proofinvest.kuodra_unified_core import normalize_local_csv
from proofinvest.kuodra_stats import cross_section_fdr,_bh_fdr


def sample(*,n=50,missing_releases=False,secret=False,constant_z=False):
    wout=StringIO(newline="");w=csv.writer(wout,lineterminator="\n")
    w.writerow(("entity_id","metric_id","observation_at","available_at","value","unit"))
    for i in range(n):
        for metric,v in (("x",str(i+1)),("y",str(3*(i+1)+7)),("z","1" if constant_z else str((i*17)%41))):
            available="2027-01-01T00:00:00Z" if missing_releases else "2026-01-01T00:00:00Z"
            w.writerow((f"issuer{i}",metric,"2026-01-01T00:00:00Z",available,v,"count"))
    return normalize_local_csv(wout.getvalue().encode(),dataset_id="statsSynthetic",
        source_id="generated",access_level="PRIVATE" if secret else "PUBLIC",
        consent=secret)


class CrossSectionStatsTest(TestCase):
    def test_bh_known_values(self):
        self.assertEqual([round(x,4) for x in _bh_fdr([0.04,0.01,0.03,0.5])],
                         [0.0533,0.04,0.0533,0.5])

    def test_multivariate_issuer_cross_section_bh(self):
        d=sample()
        r=cross_section_fdr(d,metrics=("x","y","z"),
            observation_at="2026-01-01T00:00:00Z",
            as_of="2026-02-01T00:00:00Z")
        self.assertEqual(r["status"],"EXPLORATORY_INDEPENDENCE_UNVERIFIED")
        self.assertEqual(r["pairs_evaluated"],3)
        self.assertEqual(r["hypotheses_planned"],3)
        self.assertEqual(r["eligible_entities"],50)
        xy=next(i for i in r["insights"] if {i["metric_a"],i["metric_b"]}=={"x","y"})
        self.assertAlmostEqual(xy["pearson_r"],1.0)
        self.assertLess(xy["q_bh_fdr"],0.05)
        self.assertFalse(xy["sampling_independence_verified"])
        self.assertFalse(xy["predictive_claim"])
        self.assertEqual(r["guard"],"HOLD")

    def test_bh_family_includes_unavailable_predeclared_hypotheses(self):
        with patch("proofinvest.kuodra_stats._bh_fdr", wraps=_bh_fdr) as spy:
            r=cross_section_fdr(sample(constant_z=True),metrics=("x","y","z"),
                observation_at="2026-01-01T00:00:00Z",
                as_of="2026-02-01T00:00:00Z")
        family=spy.call_args.args[0]
        self.assertEqual(len(family),3)
        self.assertEqual(family.count(1.0),2)
        self.assertEqual(r["hypotheses_planned"],3)
        self.assertEqual(r["pairs_evaluated"],1)
        self.assertEqual(r["fdr_denominator"],
                         "ALL_PREDECLARED_PAIRS_UNTESTABLE_AS_P_ONE")
        xy=r["insights"][0]
        self.assertGreaterEqual(xy["q_bh_fdr"],xy["p_unadjusted"])
        self.assertEqual(r["guard"],"HOLD")

    def test_future_releases_withheld(self):
        r=cross_section_fdr(sample(missing_releases=True),metrics=("x","y"),
            observation_at="2026-01-01T00:00:00Z",as_of="2026-02-01T00:00:00Z")
        self.assertEqual(r["status"],"INSUFFICIENT_EVIDENCE")
        self.assertEqual(r["insights"],[])

    def test_too_few_independent_issuers_withheld(self):
        r=cross_section_fdr(sample(n=12),metrics=("x","y"),
            observation_at="2026-01-01T00:00:00Z",as_of="2026-02-01T00:00:00Z")
        self.assertEqual(r["status"],"INSUFFICIENT_EVIDENCE")

    def test_tamper_access_level_rejected(self):
        d=sample(secret=True)
        d["records"][0]["access_level"]="PUBLIC"
        with self.assertRaisesRegex(ValueError,"STATS_LINEAGE_INVALID"):
            cross_section_fdr(d,metrics=("x","y"),
                observation_at="2026-01-01T00:00:00Z",as_of="2026-02-01T00:00:00Z")

    def test_impossible_observation_date_rejected(self):
        with self.assertRaisesRegex(ValueError,"STATS_INPUT_CONTRACT_INVALID"):
            cross_section_fdr(sample(),metrics=("x","y"),
                observation_at="2026-03-01T00:00:00Z",as_of="2026-02-01T00:00:00Z")

    def test_private_and_public_same_math_separate_access_label(self):
        a=cross_section_fdr(sample(),metrics=("x","y"),
            observation_at="2026-01-01T00:00:00Z",as_of="2026-02-01T00:00:00Z")
        b=cross_section_fdr(sample(secret=True),metrics=("x","y"),
            observation_at="2026-01-01T00:00:00Z",as_of="2026-02-01T00:00:00Z")
        self.assertEqual(a["insights"],b["insights"])
        self.assertEqual(b["access_level"],"PRIVATE")
