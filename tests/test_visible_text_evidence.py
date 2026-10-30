"""Fail-closed HTML text-node source locator (no requests or file writes)."""
import unittest

from proofinvest.visible_text_evidence import confirm_html_text_node_literal

NEEDLE = "SOURCE_PASSAGE"


def locate(raw, needle=NEEDLE):
    start = raw.find(needle.encode("ascii"))
    return confirm_html_text_node_literal(
        raw, needle=needle, expected_start=start, expected_end=start + len(needle),
    )


class VisibleTextEvidenceTests(unittest.TestCase):
    def test_plain_html_text_node_with_utf8_prefix_has_exact_byte_span(self):
        raw = ("<html><body><p>한글 " + NEEDLE + "</p></body></html>").encode()
        result = locate(raw)
        self.assertEqual(result["status"], "untrusted_html_text_node_literal_located")
        self.assertEqual(raw[result["start_byte"]:result["end_byte_exclusive"]], NEEDLE.encode())
        self.assertFalse(result["rendered_visibility_verified"])
        self.assertFalse(result["source_authenticated"])

    def test_attributes_script_style_comments_and_templates_cannot_cite(self):
        for html in (
            '<p title="SOURCE_PASSAGE">Visible but unrelated</p>',
            '<script>SOURCE_PASSAGE</script>',
            '<style>SOURCE_PASSAGE</style>',
            '<!-- SOURCE_PASSAGE -->',
            '<template>SOURCE_PASSAGE</template>',
            '<svg><text>SOURCE_PASSAGE</text></svg>',
        ):
            with self.subTest(html=html):
                self.assertEqual(locate(html.encode())["status"], "unavailable")

    def test_duplicate_source_text_nodes_do_not_claim_unique_evidence(self):
        raw = b"<p>SOURCE_PASSAGE</p><p>SOURCE_PASSAGE</p>"
        self.assertEqual(locate(raw)["reason_code"], "AMBIGUOUS_HTML_TEXT_NODE_LITERAL")

    def test_unclosed_hidden_tag_denies_earlier_visible_phrase(self):
        raw = b"<p>SOURCE_PASSAGE</p><script>unfinished"
        self.assertEqual(locate(raw)["reason_code"], "HTML_TEXT_NODE_PARSE_UNCERTAIN")

    def test_untrusted_entity_transform_not_cited(self):
        raw = b"<p>SOURCE_&#80;ASSAGE</p>"
        # Literal does not occur in unmodified bytes; do not invent a cite.
        self.assertEqual(locate(raw)["status"], "unavailable")

    def test_wrong_byte_span_denied(self):
        raw = b"<p>SOURCE_PASSAGE</p>"
        result = confirm_html_text_node_literal(
            raw, needle=NEEDLE, expected_start=0, expected_end=len(NEEDLE),
        )
        self.assertEqual(result["reason_code"], "PINNED_LITERAL_BYTE_SPAN_MISMATCH")

    def test_unsupported_input_denied_without_exceptions(self):
        cases = (b"", b"\xffSOURCE_PASSAGE", b"SOURCE_PASSAGE", b"<p>SOURCE_PASSAGE</p>")
        for raw in cases:
            with self.subTest(raw=raw):
                result = confirm_html_text_node_literal(
                    raw, needle=NEEDLE, expected_start=999,
                    expected_end=999 + len(NEEDLE),
                )
                self.assertEqual(result["status"], "unavailable")

    def test_non_utf8_html_denied(self):
        raw = b"<p>\xffSOURCE_PASSAGE</p>"
        self.assertEqual(locate(raw)["reason_code"], "HTML_NOT_STRICT_UTF8")

if __name__ == "__main__":
    unittest.main()
