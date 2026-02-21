"""Tests for eepro.com parser."""

import pytest
from core.parsers.base import PrelimsError
from core.parsers.eepro import EeproParser


class TestEeproParser:
    def setup_method(self):
        self.parser = EeproParser()

    VALID_URL = "https://eepro.com/results/paris-swing-classic/novice-jnj.html"

    # --- can_parse ---

    def test_can_parse_valid_url(self):
        assert self.parser.can_parse(self.VALID_URL)

    def test_can_parse_with_numbers_in_slug(self):
        assert self.parser.can_parse(
            "https://eepro.com/results/event2026/division-finals.html"
        )

    def test_cannot_parse_wrong_domain(self):
        assert not self.parser.can_parse("https://scoring.dance/results/a/b.html")

    def test_cannot_parse_wrong_path(self):
        assert not self.parser.can_parse("https://eepro.com/events/something.html")

    def test_cannot_parse_missing_html_extension(self):
        assert not self.parser.can_parse("https://eepro.com/results/a/b")

    def test_cannot_parse_missing_second_slug(self):
        assert not self.parser.can_parse("https://eepro.com/results/event.html")

    def test_cannot_parse_generic_url(self):
        assert not self.parser.can_parse("https://example.com/results")

    # --- can_parse_content ---

    def test_can_parse_content_with_example(self, eepro_html):
        assert self.parser.can_parse_content(eepro_html, "results.html")

    def test_cannot_parse_content_plain_html(self):
        assert not self.parser.can_parse_content(
            b"<html><body>Hello world</body></html>", "page.html"
        )

    def test_cannot_parse_content_pdf(self, pdf_bytes):
        assert not self.parser.can_parse_content(pdf_bytes, "scores.pdf")

    def test_cannot_parse_content_scoring_dance(self, scoring_dance_html):
        assert not self.parser.can_parse_content(scoring_dance_html, "results.html")

    # --- get_division_names ---

    def test_get_division_names(self, eepro_html):
        names = self.parser.get_division_names(eepro_html)
        assert len(names) == 8
        assert any("Advanced" in n for n in names)
        assert any("Newcomer" in n for n in names)

    # --- parse (division selection) ---

    def test_parse_with_division_substring(self, eepro_html):
        """Can select a division by substring match."""
        result = self.parser.parse(self.VALID_URL, eepro_html, division="All Star")
        assert "All Star" in result.competition_name

    def test_parse_with_division_case_insensitive(self, eepro_html):
        """Division matching is case-insensitive."""
        result = self.parser.parse(self.VALID_URL, eepro_html, division="all star")
        assert "All Star" in result.competition_name

    def test_parse_with_division_partial(self, eepro_html):
        """Partial substring matches work."""
        result = self.parser.parse(self.VALID_URL, eepro_html, division="Newcomer")
        assert "Newcomer" in result.competition_name

    def test_parse_with_division_takes_first_match(self, eepro_html):
        """When multiple divisions match, takes the first one."""
        # "Jack" appears in all division names, so should match the first
        result = self.parser.parse(self.VALID_URL, eepro_html, division="Jack")
        assert "Advanced" in result.competition_name

    def test_parse_with_division_no_match(self, eepro_html):
        """Error with listing when no division matches."""
        with pytest.raises(ValueError, match='No division matching "Nonexistent"'):
            self.parser.parse(self.VALID_URL, eepro_html, division="Nonexistent")

    def test_parse_with_division_no_match_lists_available(self, eepro_html):
        """Error message lists available divisions."""
        with pytest.raises(ValueError, match="Available divisions:"):
            self.parser.parse(self.VALID_URL, eepro_html, division="Nonexistent")

    def test_parse_no_division_multiple_raises_error(self, eepro_html):
        """Error when no division specified and multiple exist."""
        with pytest.raises(ValueError, match="contains 8 divisions"):
            self.parser.parse(self.VALID_URL, eepro_html)

    def test_parse_no_division_multiple_lists_available(self, eepro_html):
        """Error message lists available divisions."""
        with pytest.raises(ValueError, match="Available divisions:"):
            self.parser.parse(self.VALID_URL, eepro_html)

    def test_parse_no_division_single_works(self):
        """When there's only one division, no division arg is needed."""
        # Build minimal HTML with a single division table
        html = b"""<html><head><title>Event Express Pro</title></head>
        <body><h2>Test Event</h2>
        <table border="1"><tr bgcolor='#ffae5e'><td colspan='5'>Division: Solo Finals</td></tr>
        <tr><td>Place</td><td>Competitor</td><td>Judge A</td><td>BIB</td><td>Marks Sorted</td></tr>
        <tr><td>1</td><td>Alice</td><td>1</td><td>101</td><td>1</td></tr>
        <tr><td>2</td><td>Bob</td><td>2</td><td>102</td><td>2</td></tr>
        </table></body></html>"""
        result = self.parser.parse("test.html", html)
        assert "Solo Finals" in result.competition_name

    # --- parse (data correctness) ---

    def test_parse_competition_name(self, eepro_html):
        result = self.parser.parse(self.VALID_URL, eepro_html, division="Advanced")
        assert "Paris Swing Classic" in result.competition_name

    def test_parse_competitor_count(self, eepro_html):
        result = self.parser.parse(self.VALID_URL, eepro_html, division="Advanced")
        assert result.num_competitors == 12

    def test_parse_judge_count(self, eepro_html):
        result = self.parser.parse(self.VALID_URL, eepro_html, division="Advanced")
        assert result.num_judges == 5

    def test_parse_judges(self, eepro_html):
        result = self.parser.parse(self.VALID_URL, eepro_html, division="Advanced")
        assert "CHRISTOPHER ARNOLD" in result.judges
        assert "FRANÇOIS NORMAND" in result.judges

    def test_parse_competitors(self, eepro_html):
        result = self.parser.parse(self.VALID_URL, eepro_html, division="Advanced")
        assert "Ann Schroeder and Georgia Metz" in result.competitors

    def test_parse_rankings_complete(self, eepro_html):
        """Every judge has a ranking for every competitor."""
        result = self.parser.parse(self.VALID_URL, eepro_html, division="Advanced")
        for judge in result.judges:
            for competitor in result.competitors:
                assert competitor in result.rankings[judge], (
                    f"Missing ranking: {judge} -> {competitor}"
                )

    def test_parse_rankings_valid_range(self, eepro_html):
        """All rankings are between 1 and num_competitors."""
        result = self.parser.parse(self.VALID_URL, eepro_html, division="Advanced")
        for judge in result.judges:
            for competitor in result.competitors:
                rank = result.rankings[judge][competitor]
                assert 1 <= rank <= result.num_competitors, (
                    f"Rank out of range: {judge} -> {competitor} = {rank}"
                )

    def test_parse_spot_check_ranking(self, eepro_html):
        """Verify a specific known ranking."""
        result = self.parser.parse(self.VALID_URL, eepro_html, division="Advanced")
        assert result.rankings["CHRISTOPHER ARNOLD"]["Ann Schroeder and Georgia Metz"] == 1

    def test_parse_invalid_html(self):
        with pytest.raises(ValueError):
            self.parser.parse(self.VALID_URL, b"<html><body>No tables</body></html>")

    # --- prelims detection ---

    PRELIMS_HTML = b"""<html><head><title>Event Express Pro</title></head>
<body><h2>Test Event</h2>
<table border="1"><tr bgcolor='#ffae5e'><td colspan='8'>Advanced Prelims - 10 competed</td></tr>
<tr><td>Count</td><td>Competitor</td><td>Judge A</td><td>BIB</td>
    <td>Counts (Y-A-N)</td><td>Sum</td><td>Promote</td><td>Alt</td></tr>
<tr><td>1</td><td>Alice and Bob</td><td>Y</td><td>101</td>
    <td>1-0-0</td><td>10</td><td>X</td><td></td></tr>
<tr><td>2</td><td>Carol and Dave</td><td>N</td><td>102</td>
    <td>0-0-1</td><td>0</td><td></td><td></td></tr>
</table></body></html>"""

    PRELIMS_HTML_ALTERNATES = b"""<html><head><title>Event Express Pro</title></head>
<body><h2>Test Event</h2>
<table border="1"><tr bgcolor='#ffae5e'><td colspan='10'>Novice Prelims - 8 competed</td></tr>
<tr><td>Count</td><td>Competitor</td><td>Judge A</td><td>Judge B</td><td>BIB</td>
    <td>Counts (Y-A-N)</td><td>Sum</td><td>Promote</td><td>Alt</td></tr>
<tr><td>1</td><td>Alice and Bob</td><td>A1</td><td>Y</td><td>101</td>
    <td>1-1-0</td><td>10</td><td>X</td><td>X</td></tr>
<tr><td>2</td><td>Carol and Dave</td><td>A2</td><td>N</td><td>102</td>
    <td>0-1-1</td><td>0</td><td></td><td></td></tr>
<tr><td>3</td><td>Eve and Frank</td><td>A3</td><td>Y</td><td>103</td>
    <td>1-1-0</td><td>10</td><td>X</td><td></td></tr>
</table></body></html>"""

    def test_parse_prelims_single_division_raises(self):
        """Prelims scoresheet with no division arg raises PrelimsError."""
        with pytest.raises(PrelimsError):
            self.parser.parse(self.VALID_URL, self.PRELIMS_HTML)

    def test_parse_prelims_with_division_specified_raises(self):
        """Prelims scoresheet with division arg still raises PrelimsError."""
        with pytest.raises(PrelimsError):
            self.parser.parse(self.VALID_URL, self.PRELIMS_HTML, division="Prelims")

    def test_parse_prelims_with_alternates_raises(self):
        """Prelims scoresheet with A1/A2/A3 alternate votes raises PrelimsError."""
        with pytest.raises(PrelimsError):
            self.parser.parse(self.VALID_URL, self.PRELIMS_HTML_ALTERNATES)

    def test_parse_finals_not_prelims(self):
        """Finals scoresheets do not raise PrelimsError."""
        html = b"""<html><head><title>Event Express Pro</title></head>
        <body><h2>Test Event</h2>
        <table border="1"><tr bgcolor='#ffae5e'><td colspan='5'>Division: Solo Finals</td></tr>
        <tr><td>Place</td><td>Competitor</td><td>Judge A</td><td>BIB</td><td>Marks Sorted</td></tr>
        <tr><td>1</td><td>Alice</td><td>1</td><td>101</td><td>1</td></tr>
        <tr><td>2</td><td>Bob</td><td>2</td><td>102</td><td>2</td></tr>
        </table></body></html>"""
        result = self.parser.parse(self.VALID_URL, html)
        assert result is not None
