"""P43: issuer/filing agent accession compatibility in annual side panels."""
import json
import unittest

from proofinvest.kic_dl_demo import SYNTHETIC_CIK, AS_OF
from proofinvest.kuodra_sec_cashflow import review_sec_annual_cashflow
from proofinvest.kuodra_sec_balance import review_sec_balance_sheet
from proofinvest.accounting_integrity import review_accounting_integrity
from test_accounting_integrity import fixture

AGENT = "0009999999-25-000123"


def agent_fixture():
    data = fixture(accession=AGENT)
    for row in data["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"]:
        row["accn"] = AGENT
    gaap = data["facts"]["us-gaap"]
    for tag, val in (("Assets", 300), ("Liabilities", 200),
                     ("StockholdersEquity", 100)):
        gaap[tag] = {"units": {"USD": [{
            "accn": AGENT, "form": "10-K",
            "end": "2025-09-30", "filed": "2025-10-15", "val": val
        }]}}
    return data


class AgentFiledFinancialSidePanelTests(unittest.TestCase):
    def test_agent_accession_issuer_facts_accepted_in_existing_panels(self):
        raw = json.dumps(agent_fixture()).encode()
        args = dict(cik=SYNTHETIC_CIK, accession=AGENT,
                    period_end="2025-09-30", as_of=AS_OF)
        cash = review_sec_annual_cashflow(raw, **args)
        bal = review_sec_balance_sheet(raw, **args)
        quality = review_accounting_integrity(
            raw, cik=SYNTHETIC_CIK, accession=AGENT,
            current_end="2025-09-30", prior_end="2024-09-30", as_of=AS_OF,
        )
        self.assertEqual(cash["status"], "reviewed_unverified")
        self.assertEqual(cash["operating_cashflow_usd"], "20")
        self.assertEqual(bal["status"], "reviewed_unverified")
        self.assertEqual(bal["liabilities_to_equity_pct"], "200.00")
        self.assertEqual(quality["status"], "reviewed_unverified")

    def test_wrong_issuer_or_missing_accession_still_fail_closed(self):
        a = agent_fixture()
        a["cik"] = 11
        raw = json.dumps(a).encode()
        cash = review_sec_annual_cashflow(
            raw, cik=SYNTHETIC_CIK, accession=AGENT,
            period_end="2025-09-30", as_of=AS_OF,
        )
        bal = review_sec_balance_sheet(
            raw, cik=SYNTHETIC_CIK, accession=AGENT,
            period_end="2025-09-30", as_of=AS_OF,
        )
        self.assertEqual(cash["status"], "unavailable")
        self.assertEqual(bal["status"], "unavailable")
        correct = agent_fixture()
        for tag in ("Assets", "Liabilities", "StockholdersEquity"):
            correct["facts"]["us-gaap"][tag]["units"]["USD"][0]["accn"] = "0009999999-25-000999"
        bal = review_sec_balance_sheet(
            json.dumps(correct).encode(), cik=SYNTHETIC_CIK, accession=AGENT,
            period_end="2025-09-30", as_of=AS_OF,
        )
        self.assertEqual(bal["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
