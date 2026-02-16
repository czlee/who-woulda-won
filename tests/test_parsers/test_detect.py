"""Tests for content-based parser detection."""

from unittest import skip

from core.parsers import detect_parser_by_content
from core.parsers.scoring_dance import ScoringDanceParser
from core.parsers.eepro import EeproParser
from core.parsers.danceconvention import DanceConventionParser


class TestDetectParserByContent:

    def test_detects_scoring_dance(self, scoring_dance_html):
        parser = detect_parser_by_content(scoring_dance_html, "results.html")
        assert isinstance(parser, ScoringDanceParser)

    @skip
    def test_detects_eepro(self, eepro_html):
        parser = detect_parser_by_content(eepro_html, "results.html")
        assert isinstance(parser, EeproParser)

    def test_detects_danceconvention(self, danceconvention_pdf):
        parser = detect_parser_by_content(danceconvention_pdf, "scores.pdf")
        assert isinstance(parser, DanceConventionParser)

    def test_returns_none_for_plain_html(self):
        parser = detect_parser_by_content(
            b"<html><body>Hello world</body></html>", "page.html"
        )
        assert parser is None

    def test_returns_none_for_empty_content(self):
        parser = detect_parser_by_content(b"", "empty.html")
        assert parser is None
