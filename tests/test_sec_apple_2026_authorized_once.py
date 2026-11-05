"""P238: strict one GET, mock-only network, no credential/original leak."""
from __future__ import annotations
import io
import unittest
from email.message import Message
from urllib.error import HTTPError,URLError
from urllib.request import Request
from unittest.mock import patch
from proofinvest import sec_apple_2026_authorized_once as p
from tests.test_apple_2026_local_edgar_replay import synthetic


class Response:
    def __init__(self, raw, *, status=200, url=p._DOC,
                 content_type="text/html", encoding="identity",
                 declared=None):
        self.raw=raw
        self.status=status
        self.url=url
        self.headers=Message()
        self.headers["Content-Type"]=content_type
        self.headers["Content-Encoding"]=encoding
        self.headers["Content-Length"]=str(len(raw) if declared is None else declared)
        self.read_calls=0
    def geturl(self): return self.url
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self,n):
        self.read_calls+=1
        return self.raw[:n]


class P238OneOfficialGetTests(unittest.TestCase):
    def test_no_request_before_exact_approval_and_valid_contact(self):
        requested=[]
        def forbidden(_):
            requested.append(1)
            raise AssertionError("NO HTTP")
        for approved,ua in (
            (False,"KUODRA Owner-Limited Apple Original Research p238@mock-research-lab.org"),
            (None,"KUODRA Owner-Limited Apple Original Research p238@mock-research-lab.org"),
            (True,None),(True,True),(True,""),(True,"bad"),
        ):
            r=p.read_apple_2026_sec_original_once(
                authorized=approved,user_agent=ua,opener=forbidden)
            self.assertEqual(r["status"],"BLOCKED")
            self.assertEqual(r["http_requests_attempted"],0)
        self.assertEqual(requested,[])

    def test_one_mocked_response_never_proves_sec_signed_hash_or_rights(self):
        raw=synthetic()
        response=Response(raw)
        calls=[]
        def fake(req):
            self.assertIsInstance(req,Request)
            self.assertEqual(req.full_url,p._DOC)
            self.assertEqual(req.get_method(),"GET")
            calls.append(1)
            return response
        ua=p.validate_owner_contact("p238@mock-research-lab.org")
        self.assertIsNotNone(ua)
        out=p.read_apple_2026_sec_original_once(
            authorized=True,user_agent=ua,opener=fake)
        self.assertEqual(out["status"],
                         "TEST_DOUBLE_LOCAL_IXBRL_MATCH_NOT_SEC_ORIGIN",out)
        self.assertEqual(calls,[1])
        self.assertEqual(response.read_calls,1)
        self.assertEqual(out["http_requests_attempted"],1)
        self.assertFalse(out["sec_transport_observed"])
        self.assertFalse(out["sec_original_byte_identical_independently_certified"])
        self.assertFalse(out["independent_sec_signed_sha256_available"])
        self.assertFalse(out["third_party_vendor_data_rights_verified"])
        self.assertFalse(out["ndx_stock_peer_licensed"])
        self.assertFalse(out["original_html_saved"])
        self.assertNotIn("actual_sec_response_sha256",out)
        self.assertNotIn("sec_official_url",out)
        self.assertEqual(out["guard_policy_preview"],"HOLD")
        self.assertEqual(out["trades_executed"],0)
        self.assertNotIn("p238@mock-research-lab.org",str(out))
        self.assertNotIn("<html",str(out).lower())

    def test_redirect_403_429_mime_size_and_bad_values_stop_once(self):
        ua=p.validate_owner_contact("p238@mock-research-lab.org")
        raw=synthetic()
        corrupt=raw.replace(b"478834",b"478835",1)
        for resp in (
            Response(raw,status=302),
            Response(raw,url="https://other.example.org/fake"),
            Response(raw,declared=1),
            Response(raw,encoding="gzip"),
            Response(raw,content_type="application/pdf"),
            Response(raw[:-1]),Response(corrupt),
        ):
            calls=[]
            def once(_):
                calls.append(1)
                return resp
            r=p.read_apple_2026_sec_original_once(
                authorized=True,user_agent=ua,opener=once)
            self.assertEqual(r["status"],"BLOCKED",r)
            self.assertEqual(calls,[1])
            self.assertEqual(r["retries"],0)
            self.assertEqual(r["http_requests_attempted"],1)
        for code in (403,429,500):
            calls=[]
            def deny(req):
                calls.append(1)
                raise HTTPError(req.full_url,code,"blocked",{},io.BytesIO())
            r=p.read_apple_2026_sec_original_once(
                authorized=True,user_agent=ua,opener=deny)
            self.assertEqual(r["status"],"BLOCKED")
            self.assertEqual(calls,[1])
            self.assertEqual(r["retries"],0)
            if code in (403,429):
                self.assertIn(str(code),r["reason_code"])
        with patch.object(p,"_official_open",side_effect=URLError("offline")) as network:
            r=p.read_apple_2026_sec_original_once(authorized=True,user_agent=ua)
            network.assert_called_once()
            self.assertEqual(r["status"],"BLOCKED")

    def test_p239_length_mismatch_reports_safe_bounded_count_not_raw(self):
        # A declared correct length does NOT establish a complete body.
        # This simulates the actual P239 branch without contacting the SEC.
        ua=p.validate_owner_contact("p238@mock-research-lab.org")
        original=synthetic()
        for body,observed,capped in (
            (original[:-13],len(original)-13,False),
            (original+b"?",len(original)+1,True),
            (original+b"oversize",len(original)+1,True),
        ):
            with self.subTest(observed=observed,capped=capped):
                resp=Response(body,declared=p._SIZE)
                calls=[]
                def fake(_):
                    calls.append(1)
                    return resp
                out=p.read_apple_2026_sec_original_once(
                    authorized=True,user_agent=ua,opener=fake)
                self.assertEqual(calls,[1])
                self.assertEqual(resp.read_calls,1)
                self.assertEqual(out["reason_code"],
                                 "SEC_ACTUAL_BODY_LENGTH_MISMATCH")
                self.assertEqual(out["status"],"BLOCKED")
                self.assertEqual(out["response_body_bytes_read"],observed)
                self.assertEqual(out["sec_index_document_bytes_expected"],p._SIZE)
                self.assertEqual(out["response_read_cap_bytes"],p._SIZE+1)
                self.assertIs(out["response_read_cap_reached"],capped)
                self.assertIs(out["response_body_complete_transfer_verified"],False)
                self.assertFalse(out["sec_transport_observed"])
                self.assertEqual(out["http_requests_attempted"],1)
                self.assertEqual(out["retries"],0)
                self.assertFalse(out["original_html_saved"])
                self.assertNotIn(ua,str(out))
                self.assertNotIn("<html",str(out).lower())
                self.assertNotIn("actual_sec_response_sha256",out)

    def test_contact_rejects_whitespace_invalid_or_control_chars(self):
        for s in (None,True,"", "bad","x@localhost",
                  "p238@mock-research-lab.org\nOther: header", "x@example.com"*12):
            self.assertIsNone(p.validate_owner_contact(s))
        self.assertIsNotNone(p.validate_owner_contact("p238@mock-research-lab.org"))
