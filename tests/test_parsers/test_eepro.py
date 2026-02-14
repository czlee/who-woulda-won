"""Tests for eepro.com parser."""

import pytest
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

    # --- parse (first division) ---

    def test_parse_competition_name(self, eepro_html):
        result = self.parser.parse(self.VALID_URL, eepro_html)
        assert "Paris Swing Classic" in result.competition_name

    def test_parse_competitor_count(self, eepro_html):
        result = self.parser.parse(self.VALID_URL, eepro_html)
        assert result.num_competitors == 12

    def test_parse_judge_count(self, eepro_html):
        result = self.parser.parse(self.VALID_URL, eepro_html)
        assert result.num_judges == 5

    def test_parse_judges(self, eepro_html):
        result = self.parser.parse(self.VALID_URL, eepro_html)
        assert "CHRISTOPHER ARNOLD" in result.judges
        assert "FRANÇOIS NORMAND" in result.judges

    def test_parse_competitors(self, eepro_html):
        result = self.parser.parse(self.VALID_URL, eepro_html)
        assert "Ann Schroeder and Georgia Metz" in result.competitors

    def test_parse_rankings_complete(self, eepro_html):
        """Every judge has a ranking for every competitor."""
        result = self.parser.parse(self.VALID_URL, eepro_html)
        for judge in result.judges:
            for competitor in result.competitors:
                assert competitor in result.rankings[judge], (
                    f"Missing ranking: {judge} -> {competitor}"
                )

    def test_parse_rankings_valid_range(self, eepro_html):
        """All rankings are between 1 and num_competitors."""
        result = self.parser.parse(self.VALID_URL, eepro_html)
        for judge in result.judges:
            for competitor in result.competitors:
                rank = result.rankings[judge][competitor]
                assert 1 <= rank <= result.num_competitors, (
                    f"Rank out of range: {judge} -> {competitor} = {rank}"
                )

    def test_parse_spot_check_ranking(self, eepro_html):
        """Verify a specific known ranking."""
        result = self.parser.parse(self.VALID_URL, eepro_html)
        assert result.rankings["CHRISTOPHER ARNOLD"]["Ann Schroeder and Georgia Metz"] == 1

    def test_parse_second_division(self, eepro_html):
        """Can parse a different division by index."""
        result = self.parser.parse(self.VALID_URL, eepro_html, division_index=1)
        assert "All Star" in result.competition_name

    def test_parse_invalid_division_index(self, eepro_html):
        with pytest.raises(ValueError, match="out of range"):
            self.parser.parse(self.VALID_URL, eepro_html, division_index=99)

    def test_parse_invalid_html(self):
        with pytest.raises(ValueError):
            self.parser.parse(self.VALID_URL, b"<html><body>No tables</body></html>")
