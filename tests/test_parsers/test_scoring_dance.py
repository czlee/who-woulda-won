"""Tests for scoring.dance parser."""

import pytest
from core.parsers.scoring_dance import ScoringDanceParser


class TestScoringDanceParser:
    def setup_method(self):
        self.parser = ScoringDanceParser()

    VALID_URL = "https://scoring.dance/events/123/results/456.html"
    VALID_URL_WITH_LANG = "https://scoring.dance/en/events/123/results/456.html"
    VALID_URL_WITH_LANG_COUNTRY = "https://scoring.dance/enUS/events/123/results/456.html"
    VALID_URL_WITH_LANG_COUNTRY_HYPHEN = "https://scoring.dance/en-US/events/123/results/456.html"

    # --- can_parse ---

    def test_can_parse_valid_url(self):
        assert self.parser.can_parse(self.VALID_URL)

    def test_can_parse_with_language(self):
        assert self.parser.can_parse(self.VALID_URL_WITH_LANG)

    def test_can_parse_with_language_country(self):
        assert self.parser.can_parse(self.VALID_URL_WITH_LANG_COUNTRY)
        assert self.parser.can_parse("https://scoring.dance/frFR/events/1/results/2.html")
        assert self.parser.can_parse("https://scoring.dance/zhCN/events/1/results/2.html")

    def test_can_parse_with_language_country_hyphen(self):
        assert self.parser.can_parse(self.VALID_URL_WITH_LANG_COUNTRY_HYPHEN)
        assert self.parser.can_parse("https://scoring.dance/fr-FR/events/1/results/2.html")

    def test_cannot_parse_invalid_language_code(self):
        assert not self.parser.can_parse(
            "https://scoring.dance/english/events/123/results/456.html"
        )
        assert not self.parser.can_parse(
            "https://scoring.dance/e/events/123/results/456.html"
        )
        assert not self.parser.can_parse(
            "https://scoring.dance/enus/events/123/results/456.html"
        )

    def test_can_parse_long_numbers(self):
        assert self.parser.can_parse(
            "https://scoring.dance/events/98765/results/12345.html"
        )

    def test_cannot_parse_wrong_domain(self):
        assert not self.parser.can_parse("https://eepro.com/results/a/b.html")

    def test_cannot_parse_wrong_path(self):
        assert not self.parser.can_parse(
            "https://scoring.dance/competitions/123/results"
        )

    def test_cannot_parse_missing_html_extension(self):
        assert not self.parser.can_parse(
            "https://scoring.dance/events/123/results/456"
        )

    def test_cannot_parse_non_numeric_ids(self):
        assert not self.parser.can_parse(
            "https://scoring.dance/events/abc/results/456.html"
        )

    def test_cannot_parse_generic_url(self):
        assert not self.parser.can_parse("https://example.com/scores")

    # --- can_parse_content ---

    def test_can_parse_content_with_example(self, scoring_dance_html):
        assert self.parser.can_parse_content(scoring_dance_html, "results.html")

    def test_cannot_parse_content_plain_html(self):
        assert not self.parser.can_parse_content(
            b"<html><body>Hello world</body></html>", "page.html"
        )

    def test_cannot_parse_content_pdf(self, pdf_bytes):
        assert not self.parser.can_parse_content(pdf_bytes, "scores.pdf")

    def test_cannot_parse_content_eepro(self, eepro_html):
        assert not self.parser.can_parse_content(eepro_html, "results.html")

    # --- parse ---

    def test_parse_competition_name(self, scoring_dance_html):
        result = self.parser.parse(self.VALID_URL, scoring_dance_html)
        assert "Swing Resolution 2026" in result.competition_name
        assert "Novice" in result.competition_name

    def test_parse_competitor_count(self, scoring_dance_html):
        result = self.parser.parse(self.VALID_URL, scoring_dance_html)
        assert result.num_competitors == 12

    def test_parse_judge_count(self, scoring_dance_html):
        result = self.parser.parse(self.VALID_URL, scoring_dance_html)
        assert result.num_judges == 5

    def test_parse_judges(self, scoring_dance_html):
        result = self.parser.parse(self.VALID_URL, scoring_dance_html)
        assert "Tyler Garcia" in result.judges
        assert "Agathe-Luce Potier" in result.judges

    def test_parse_competitors(self, scoring_dance_html):
        result = self.parser.parse(self.VALID_URL, scoring_dance_html)
        assert "Marie-Therese Kade & Suzanne Guyon" in result.competitors

    def test_parse_rankings_complete(self, scoring_dance_html):
        """Every judge has a ranking for every competitor."""
        result = self.parser.parse(self.VALID_URL, scoring_dance_html)
        for judge in result.judges:
            for competitor in result.competitors:
                assert competitor in result.rankings[judge], (
                    f"Missing ranking: {judge} -> {competitor}"
                )

    def test_parse_rankings_valid_range(self, scoring_dance_html):
        """All rankings are between 1 and num_competitors."""
        result = self.parser.parse(self.VALID_URL, scoring_dance_html)
        for judge in result.judges:
            for competitor in result.competitors:
                rank = result.rankings[judge][competitor]
                assert 1 <= rank <= result.num_competitors, (
                    f"Rank out of range: {judge} -> {competitor} = {rank}"
                )

    def test_parse_spot_check_ranking(self, scoring_dance_html):
        """Verify a specific known ranking."""
        result = self.parser.parse(self.VALID_URL, scoring_dance_html)
        assert result.rankings["Tyler Garcia"]["Marie-Therese Kade & Suzanne Guyon"] == 1

    def test_parse_invalid_html(self):
        with pytest.raises(ValueError):
            self.parser.parse(self.VALID_URL, b"<html><body>No data</body></html>")
