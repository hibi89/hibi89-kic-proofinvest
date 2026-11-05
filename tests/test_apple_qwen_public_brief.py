"""P235 real local model public financial evidence-card synthesis guards."""
from __future__ import annotations
import json
import unittest
from unittest.mock import patch
from proofinvest import apple_qwen_public_brief as p


def reply(refs=None,scenario=None,decision=None,model=None,tokens=26,extra=False):
    obj={
        "scenario":p._SCENARIO if scenario is None else scenario,
        "source_refs":list(p._REFS) if refs is None else refs,
        "decision":p._POLICY if decision is None else decision,
    }
    if extra: obj["recommendation"]="BUY"
    return json.dumps({
        "done":True,"model":p._MODEL if model is None else model,
        "eval_count":tokens,"response":json.dumps(obj),
    }).encode()


class SourceCardQwenTests(unittest.TestCase):
    def test_actual_public_card_replay_no_unsupported_rights(self):
        res=p.verify_public_evidence_model_response(reply())
        self.assertEqual(res["status"],
                         "REAL_LOCAL_MODEL_MULTI_PUBLIC_FACT_BRIEF_VERIFIED",res)
        self.assertTrue(res["actual_model_tokens_verified"])
        self.assertTrue(res["source_bound_multi_fact_model_verified"])
        self.assertEqual(res["source_refs"],list(p._REFS))
        self.assertEqual(res["guard_policy_preview"],"HOLD")
        self.assertIn("재고 증가율",res["approved_human_only_text"])
        for key in ("publisher_original_byte_authenticated",
                    "source_redistribution_rights_verified",
                    "market_price_ndx_rights_verified",
                    "representative_peer_rights_verified",
                    "financial_ai_full_authorized",
                    "full_abc_complete","model_free_text_displayed",
                    "market_prediction","fraud_proven",
                    "investment_recommendation",
                    "confidential_originals_transmitted"):
            self.assertFalse(res[key],key)
        self.assertEqual(res["trades_executed"],0)

    def test_bad_model_output_and_fake_rights_never_displayed(self):
        for raw in (
            reply(refs=list(reversed(p._REFS))),
            reply(refs=list(p._REFS[:2])),
            reply(refs=[p._REFS[0]]*3),
            reply(scenario="ALL_SOURCES_VERIFIED"),
            reply(decision="BUY"),
            reply(extra=True),
            reply(model="other"),
            reply(tokens=0),
            reply().replace(b'"eval_count": 26',b'"eval_count": true'),
            b"{}",b"\xff",b'{"done":true,"done":false}',b"x"*8193,
        ):
            with self.subTest(raw=raw[:70]):
                blocked=p.verify_public_evidence_model_response(raw)
                self.assertEqual(blocked["status"],"BLOCKED")
                self.assertFalse(blocked["source_bound_multi_fact_model_verified"])
                self.assertFalse(blocked["model_free_text_displayed"])
                self.assertEqual(blocked["guard_policy_preview"],"HOLD")
                self.assertEqual(blocked["trades_executed"],0)

    def test_default_denies_network_without_exact_two_consents(self):
        with patch.object(p,"_call_loopback",
                          side_effect=AssertionError("NO_NET")) as net:
            for opts in ({},{"local_model_confirmed":True},
                         {"public_fact_summary_consent":True},
                         {"local_model_confirmed":True,
                          "public_fact_summary_consent":True,"port":11434}):
                self.assertEqual(p.run_local_public_evidence_summary(**opts)["status"],
                                 "BLOCKED")
            net.assert_not_called()

    def test_single_local_only_source_status_request(self):
        calls=[]
        def call(data,*,port):
            calls.append((data,port))
            return reply()
        with patch.object(p,"_call_loopback",side_effect=call):
            res=p.run_local_public_evidence_summary(
                local_model_confirmed=True,
                public_fact_summary_consent=True)
        self.assertTrue(res["source_bound_multi_fact_model_verified"])
        self.assertEqual(len(calls),1)
        data,port=calls[0]
        self.assertEqual(port,11435)
        payload=json.loads(data)
        self.assertEqual(payload["model"],p._MODEL)
        self.assertEqual(payload["format"]["properties"]["scenario"]["enum"],
                         [p._SCENARIO,"ALL_SOURCES_VERIFIED"])
        prompt=payload["prompt"]
        for key in p._REFS: self.assertIn(key,prompt)
        for forbidden in ("AAPL","Apple","145097","132175","478834",
                          "154.30","15.06","NDX", "https://","api_key",
                          "source_sha256","CONFIDENTIAL"):
            self.assertNotIn(forbidden,prompt)
        self.assertLessEqual(len(data),2048)

    def test_forged_independent_public_source_never_calls_model(self):
        with patch.object(p,"public_2026_values",return_value={
            "inventory":{"2025":"1","2026":"5"}}),patch.object(
            p,"_call_loopback",side_effect=AssertionError("NO_NET")
        ) as mocked:
            res=p.run_local_public_evidence_summary(
                local_model_confirmed=True,
                public_fact_summary_consent=True)
        self.assertEqual(res["status"],"BLOCKED")
        mocked.assert_not_called()
