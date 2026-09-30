"""Tests for segmentation offsets, signal precision, and HTML rendering."""

import json
from html import escape

import pytest

from argumentminer.segmenter import ArgumentSegmenter, SegmentType
from argumentminer.graph import build_graph
from argumentminer.visualiser import render_html


@pytest.fixture
def segmenter():
    return ArgumentSegmenter()


class TestOffsets:
    """start_char/end_char must bracket the segment text exactly.

    The offsets used to come from the raw regex match while the text was
    stripped, so every segment after the first pointed one character early.
    """

    def test_offsets_round_trip(self, segmenter):
        text = ("Vaccines are safe. Studies show they prevent disease. "
                "Therefore we should vaccinate.")
        for seg in segmenter.segment(text):
            assert text[seg.start_char:seg.end_char] == seg.text

    def test_offsets_round_trip_with_irregular_spacing(self, segmenter):
        text = "The first clause here.     A second clause follows!   And a third one?"
        segments = segmenter.segment(text)
        assert len(segments) == 3
        for seg in segments:
            assert text[seg.start_char:seg.end_char] == seg.text

    def test_offsets_round_trip_across_newlines(self, segmenter):
        text = "An opening statement here.\n\nBecause the evidence is strong.\n"
        for seg in segmenter.segment(text):
            assert text[seg.start_char:seg.end_char] == seg.text

    def test_first_segment_starts_at_zero(self, segmenter):
        text = "This is the opening clause. And here is another one."
        assert segmenter.segment(text)[0].start_char == 0

    def test_offsets_are_non_overlapping_and_ordered(self, segmenter):
        text = "One clause goes here. Another clause goes here. A third goes here."
        segments = segmenter.segment(text)
        for earlier, later in zip(segments, segments[1:]):
            assert earlier.end_char <= later.start_char


class TestSignalPrecision:
    """Markers with a common non-argumentative sense must not fire on prose."""

    def test_ordinary_for_is_not_a_premise(self, segmenter):
        seg = segmenter.segment("She waited for the train to arrive on time.")[0]
        assert seg.type is SegmentType.BACKGROUND

    def test_ordinary_as_is_not_a_premise(self, segmenter):
        seg = segmenter.segment("He works as a teacher in the local school.")[0]
        assert seg.type is SegmentType.BACKGROUND

    def test_intensifier_so_is_not_a_conclusion(self, segmenter):
        seg = segmenter.segment("The winter that year was so cold and very long.")[0]
        assert seg.type is SegmentType.BACKGROUND

    def test_clause_initial_so_is_still_a_conclusion(self, segmenter):
        seg = segmenter.segment("So we must act on this without further delay.")[0]
        assert seg.type is SegmentType.CONCLUSION

    def test_so_after_a_comma_is_still_a_conclusion(self, segmenter):
        seg = segmenter.segment("The evidence is overwhelming, so we must act now.")[0]
        assert seg.type is SegmentType.CONCLUSION

    def test_because_is_still_a_premise(self, segmenter):
        seg = segmenter.segment("We must act because the evidence is overwhelming.")[0]
        assert seg.type is SegmentType.PREMISE

    def test_therefore_is_still_a_conclusion(self, segmenter):
        seg = segmenter.segment("Therefore the policy should be changed now.")[0]
        assert seg.type is SegmentType.CONCLUSION

    def test_as_a_result_is_still_a_conclusion(self, segmenter):
        seg = segmenter.segment("As a result the policy should be changed now.")[0]
        assert seg.type is SegmentType.CONCLUSION


class TestHtmlRendering:
    """Analysed text is untrusted and must not become part of the page."""

    def test_script_tag_in_text_does_not_close_the_data_block(self, segmenter):
        text = ("We should ban this because the code contains "
                "</script><img src=x onerror=alert(1)> everywhere.")
        page = render_html(build_graph(segmenter.segment(text)))
        assert "</script><img" not in page
        assert "\\u003c/script\\u003e" in page

    def test_title_is_escaped(self, segmenter):
        page = render_html(build_graph(segmenter.segment("A plain sentence here.")),
                           title="<script>alert(2)</script>")
        assert "<script>alert(2)</script>" not in page
        assert escape("<script>alert(2)</script>") in page

    def test_detail_pane_does_not_use_inner_html(self, segmenter):
        page = render_html(build_graph(segmenter.segment("A plain sentence here.")))
        # innerHTML would parse markup inside a segment as live HTML.
        assert ".innerHTML" not in page

    def test_page_still_carries_the_graph_data(self, segmenter):
        text = "We must act because the evidence is overwhelming."
        page = render_html(build_graph(segmenter.segment(text)))
        assert "evidence is overwhelming" in page
        # The embedded block has to be JSON the page can actually parse, which
        # is the part that matters; how it is spelled into the document is not.
        payload = json.loads(self._data_block(page))
        assert payload["nodes"], "the graph carried no nodes"
        assert any("evidence is overwhelming" in n["text"] for n in payload["nodes"])

    def test_the_page_needs_no_network_to_draw(self, segmenter):
        """It used to load D3 from a CDN, so a saved report drew nothing offline."""
        page = render_html(build_graph(segmenter.segment("We must act because it is late.")))
        assert "http://" not in page
        assert "https://" not in page
        assert "cdn" not in page.lower()
        # Nothing may be fetched at view time either.
        for fetcher in ("fetch(", "XMLHttpRequest", "importScripts", "<script src"):
            assert fetcher not in page

    def test_fallacies_reach_the_page_when_given(self, segmenter):
        from argumentminer.fallacy import FallacyDetector
        text = "You should agree because everyone knows this is how it works."
        found = FallacyDetector().detect_unique(text)
        page = render_html(build_graph(segmenter.segment(text)), fallacies=found)
        payload = json.loads(
            page.split('id="fallacies" type="application/json">')[1].split("</script>")[0])
        assert len(payload) == len(found)
        # The caveat travels with them; a bare list reads as a verdict.
        assert "not judgements about the argument" in page

    @staticmethod
    def _data_block(page: str) -> str:
        return page.split('id="data" type="application/json">')[1].split("</script>")[0]
