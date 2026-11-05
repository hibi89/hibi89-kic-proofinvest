"""P226 real issuer A/B/C status-only loopback and strict consent contract."""
from __future__ import annotations
from copy import deepcopy
from datetime import date,timedelta
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import threading
import unittest
from unittest.mock import patch

from proofinvest.real_issuer_local_market import review_real_issuer_local_market_pair
from proofinvest.real_issuer_abc_local_review import build_partial_source_bound_abc
from proofinvest.real_issuer_abc_fact_review import build_source_factual_abc_brief
from proofinvest.real_issuer_model_focus import review_real_issuer_model_focus

def market(symbol,base):
    d=date(2026,8,18);i=0;rows={}
    while d<=date(2026,11,4):
        if d.weekday()<5:
            rows[d.isoformat()]={"4. close":str(base+i*2+(i%5)*3)}
            i+=1
        d+=timedelta(days=1)
    return json.dumps({"Meta Data":{"2. Symbol":symbol},
                       "Time Series (Daily)":rows}).encode()

def source_pair():
    ab=review_real_issuer_local_market_pair(
        ticker="NVDA",stock_json=market("NVDA",120),
        ndx_json=market("NDX",10000))
    joined=build_partial_source_bound_abc(ab_review=ab)
    brief=build_source_factual_abc_brief(joined)
    return joined,brief

class Loopback(BaseHTTPRequestHandler):
    observations=[]
    answer={"model":"test-model","done":True,
            "response":'{"focus_engine":"A","decision":"HUMAN_REVIEW_ONLY"}'}
    def log_message(self,*args):pass
    def do_POST(self):
        data=self.rfile.read(int(self.headers["Content-Length"]))
        type(self).observations.append({
            "path":self.path,"host":self.headers.get("Host"),"data":data})
        raw=json.dumps(type(self).answer).encode()
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

class ActualIssuerLocalModelFocusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.abc,cls.brief=source_pair()
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),Loopback)
        cls.port=cls.server.server_address[1]
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join(timeout=3)
    def setUp(self):
        Loopback.observations.clear()
        Loopback.answer={"model":"test-model","done":True,
          "response":'{"focus_engine":"A","decision":"HUMAN_REVIEW_ONLY"}'}
    def run_focus(self,**kwargs):
        args=dict(model="test-model",port=self.port,
                  allow_local_model=True,confirm_only_status_codes=True)
        return review_real_issuer_model_focus(self.abc,self.brief,
                                              **(args|kwargs))
    def test_default_never_calls_local_model_without_both_consents(self):
        with patch("proofinvest.real_issuer_model_focus._call_loopback",
                   side_effect=AssertionError("NO_CALL")):
            for opts in ({},{"allow_local_model":True},
                         {"confirm_only_status_codes":True}):
                out=review_real_issuer_model_focus(
                    self.abc,self.brief,model="test-model",port=self.port,**opts)
                self.assertEqual(out["status"],"BLOCKED")
                self.assertEqual(out["loopback_http_attempts"],0)
        self.assertEqual(len(Loopback.observations),0)
    def test_actual_loopback_http_exactly_one_status_only_request(self):
        out=self.run_focus()
        self.assertEqual(out["status"],
                         "LOCAL_REAL_ISSUER_MODEL_FOCUS_PROTOCOL_ONLY")
        self.assertEqual(out["focus_engine"],"A")
        self.assertTrue(out["model_protocol_http_verified"])
        self.assertFalse(out["model_inference_authenticated"])
        self.assertFalse(out["financial_llm_inference_verified"])
        self.assertEqual(out["guard_policy_preview"],"HOLD")
        self.assertFalse(out["external_sharing_allowed"])
        self.assertFalse(out["trade_executed"])
        self.assertEqual(out["loopback_http_attempts"],1)
        self.assertEqual(len(Loopback.observations),1)
        body=json.loads(Loopback.observations[0]["data"])
        self.assertEqual(Loopback.observations[0]["path"],"/api/generate")
        self.assertEqual(Loopback.observations[0]["host"],
                         "127.0.0.1:"+str(self.port))
        self.assertEqual(body["model"],"test-model")
        self.assertEqual(body["format"]["properties"]["decision"]["enum"],
                         ["HUMAN_REVIEW_ONLY"])
        self.assertLessEqual(len(Loopback.observations[0]["data"]),2048)
        serial=Loopback.observations[0]["data"].decode()
        for private in ("NVDA","AMD","INTC","source_sha256","215938","65.47",
                        "34.34","10-K","api_key","https://","external"):
            self.assertNotIn(private,serial)
    def test_wrong_model_output_and_free_text_fail_without_advice(self):
        for response in (
           "BUY NVDA", '{"focus_engine":"C","decision":"HUMAN_REVIEW_ONLY"}',
           '{"focus_engine":"A","decision":"BUY"}',
           '{"focus_engine":"A","decision":"HUMAN_REVIEW_ONLY","advice":"BUY"}',
           '{"focus_engine":"A","focus_engine":"C","decision":"HUMAN_REVIEW_ONLY"}',
        ):
            Loopback.answer={"model":"test-model","done":True,"response":response}
            out=self.run_focus()
            self.assertEqual(out["status"],"BLOCKED",response)
            self.assertFalse(out["trade_executed"])
            self.assertEqual(out["guard_policy_preview"],"HOLD")
        self.assertEqual(len(Loopback.observations),5)
    def test_tampered_issuer_or_peer_or_source_rights_never_posts(self):
        baseline=(self.abc,self.brief)
        for name,transform in (
            ("issuer",lambda a,b:a.update(ticker="DELL")),
            ("peer",lambda a,b:a["engine_c_partial"].update(peer_count=10)),
            ("rights",lambda a,b:b.update(source_rights_verified=True)),
            ("narrative",lambda a,b:b["claims"][1].update(value="999999")),
        ):
            a,b=deepcopy(baseline)
            transform(a,b)
            with self.subTest(name=name):
                out=review_real_issuer_model_focus(
                    a,b,model="test-model",port=self.port,
                    allow_local_model=True,confirm_only_status_codes=True)
                self.assertEqual(out["status"],"BLOCKED")
                self.assertEqual(out["loopback_http_attempts"],0)
        self.assertFalse(Loopback.observations)
    def test_native_panel_default_disabled_no_network(self):
        from streamlit.testing.v1 import AppTest
        from pathlib import Path
        app=Path(__file__).resolve().parents[1]/"streamlit_app.py"
        with patch("proofinvest.kuodra_local_workspace_ui.local_workspace_enabled",
                   return_value=True),patch(
                   "proofinvest.real_issuer_model_focus._call_loopback",
                   side_effect=AssertionError("NOT_CONSENTED")):
            at=AppTest.from_file(str(app)).run(timeout=30)
            at.selectbox[0].set_value(
                "KUODRA · 실제 발행사 종목 직접 입력 (2종 · 제한)").run(timeout=30)
            next(x for x in at.text_input
                 if x.key=="p218_real_issuer_input").set_value("NVDA").run(timeout=30)
            self.assertFalse(at.exception,[str(x.message) for x in at.exception])
            self.assertTrue(any("로컬 AI 검토 우선순위" in x.value
                                for x in at.subheader))
            self.assertFalse(next(x for x in at.checkbox
                                  if x.key=="p226_model_expander").value)
