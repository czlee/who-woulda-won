"""Tests for danceconvention.net PDF parser."""

import pytest
from core.parsers.danceconvention import DanceConventionParser


class TestDanceConventionParser:
    def setup_method(self):
        self.parser = DanceConventionParser()

    VALID_URL = "https://danceconvention.net/eventdirector/en/roundscores/12345.pdf"

    # --- can_parse ---

    def test_can_parse_valid_url(self):
        assert self.parser.can_parse(self.VALID_URL)

    def test_can_parse_short_number(self):
        assert self.parser.can_parse(
            "https://danceconvention.net/eventdirector/en/roundscores/1.pdf"
        )

    def test_cannot_parse_wrong_domain(self):
        assert not self.parser.can_parse("https://scoring.dance/results")

    def test_cannot_parse_wrong_path(self):
        assert not self.parser.can_parse(
            "https://danceconvention.net/results/123.pdf"
        )

    def test_cannot_parse_non_numeric_id(self):
        assert not self.parser.can_parse(
            "https://danceconvention.net/eventdirector/en/roundscores/abc.pdf"
        )

    def test_cannot_parse_random_pdf(self):
        """A .pdf on another domain shouldn't match."""
        assert not self.parser.can_parse("https://example.com/results.pdf")

    def test_cannot_parse_generic_url(self):
        assert not self.parser.can_parse("https://danceconvention.net/")

    # --- can_parse_content ---

    def test_can_parse_content_with_example(self, danceconvention_pdf):
        assert self.parser.can_parse_content(danceconvention_pdf, "scores.pdf")

    def test_cannot_parse_content_plain_html(self):
        assert not self.parser.can_parse_content(
            b"<html><body>Hello world</body></html>", "page.html"
        )

    def test_cannot_parse_content_random_pdf(self):
        assert not self.parser.can_parse_content(b"%PDF-1.4 not a real pdf", "doc.pdf")

    def test_cannot_parse_content_scoring_dance(self, scoring_dance_html):
        assert not self.parser.can_parse_content(scoring_dance_html, "results.html")

    def test_cannot_parse_content_eepro(self, eepro_html):
        assert not self.parser.can_parse_content(eepro_html, "results.html")

    # --- parse (English, using mock pdfplumber) ---

    def test_parse_competition_name(self, mock_pdfplumber_en):
        result = self.parser.parse(self.VALID_URL, b"%PDF")
        assert "After Party" in result.competition_name or "Novice" in result.competition_name

    def test_parse_competitor_count(self, mock_pdfplumber_en):
        result = self.parser.parse(self.VALID_URL, b"%PDF")
        assert result.num_competitors == 12

    def test_parse_judge_count(self, mock_pdfplumber_en):
        result = self.parser.parse(self.VALID_URL, b"%PDF")
        assert result.num_judges == 7

    def test_parse_judges(self, mock_pdfplumber_en):
        result = self.parser.parse(self.VALID_URL, b"%PDF")
        assert "Marlis West" in result.judges
        assert "Claire Newman" in result.judges
        assert "Zehra Martin" in result.judges

    def test_parse_competitors(self, mock_pdfplumber_en):
        result = self.parser.parse(self.VALID_URL, b"%PDF")
        assert any("Hazel Cox" in c for c in result.competitors)

    def test_parse_rankings_complete(self, mock_pdfplumber_en):
        """Every judge has a ranking for every competitor."""
        result = self.parser.parse(self.VALID_URL, b"%PDF")
        for judge in result.judges:
            for competitor in result.competitors:
                assert competitor in result.rankings[judge], (
                    f"Missing ranking: {judge} -> {competitor}"
                )

    def test_parse_rankings_valid_range(self, mock_pdfplumber_en):
        """All rankings are positive integers."""
        result = self.parser.parse(self.VALID_URL, b"%PDF")
        for judge in result.judges:
            for competitor in result.competitors:
                rank = result.rankings[judge][competitor]
                assert rank >= 1, (
                    f"Rank not positive: {judge} -> {competitor} = {rank}"
                )

    def test_parse_spot_check_ranking(self, mock_pdfplumber_en):
        """Verify a specific known ranking."""
        result = self.parser.parse(self.VALID_URL, b"%PDF")
        # Marlis West ranked Hazel Cox & Laura Lynn 3rd
        assert result.rankings["Marlis West"]["Hazel Cox & Laura Lynn"] == 3

    def test_parse_includes_page_2_competitors(self, mock_pdfplumber_en):
        """The PDF has competitors spanning 2 pages. All must be parsed."""
        result = self.parser.parse(self.VALID_URL, b"%PDF")
        # Émilie Perrot & Antonios Pieper are on page 2
        page_2_found = any("Perrot" in c or "Antonios" in c for c in result.competitors)
        assert page_2_found, (
            f"Page 2 competitor not found. Competitors: {result.competitors}"
        )

    def test_parse_page_2_spot_check_ranking(self, mock_pdfplumber_en):
        """Page 2 competitor should have correct rankings."""
        result = self.parser.parse(self.VALID_URL, b"%PDF")
        # Émilie Perrot & Antonios Pieper: MW ranked them 9
        page_2_comp = [c for c in result.competitors if "Perrot" in c or "Antonios" in c]
        assert len(page_2_comp) == 1, f"Expected 1 page 2 competitor, got {page_2_comp}"
        assert result.rankings["Marlis West"][page_2_comp[0]] == 9

    # --- Russian-language PDF ---

    VALID_RU_URL = "https://danceconvention.net/eventdirector/ru/roundscores/12345.pdf"

    def test_can_parse_ru_url(self):
        assert self.parser.can_parse(self.VALID_RU_URL)

    def test_can_parse_content_with_ru_example(self, danceconvention_ru_pdf):
        assert self.parser.can_parse_content(danceconvention_ru_pdf, "scores.pdf")

    def test_parse_ru_competition_name(self, mock_pdfplumber_ru):
        result = self.parser.parse(self.VALID_RU_URL, b"%PDF")
        assert "Jack'n'Jill Advanced" in result.competition_name

    def test_parse_ru_competitor_count(self, mock_pdfplumber_ru):
        result = self.parser.parse(self.VALID_RU_URL, b"%PDF")
        assert result.num_competitors == 10

    def test_parse_ru_judge_count(self, mock_pdfplumber_ru):
        result = self.parser.parse(self.VALID_RU_URL, b"%PDF")
        assert result.num_judges == 7

    def test_parse_ru_judges(self, mock_pdfplumber_ru):
        result = self.parser.parse(self.VALID_RU_URL, b"%PDF")
        assert "Лавр Пахомова" in result.judges
        assert "Юлия Овчинникова" in result.judges

    def test_parse_ru_rankings_complete(self, mock_pdfplumber_ru):
        result = self.parser.parse(self.VALID_RU_URL, b"%PDF")
        for judge in result.judges:
            for competitor in result.competitors:
                assert competitor in result.rankings[judge], (
                    f"Missing ranking: {judge} -> {competitor}"
                )

    def test_parse_ru_rankings_valid_range(self, mock_pdfplumber_ru):
        result = self.parser.parse(self.VALID_RU_URL, b"%PDF")
        for judge in result.judges:
            for competitor in result.competitors:
                rank = result.rankings[judge][competitor]
                assert rank >= 1, (
                    f"Rank not positive: {judge} -> {competitor} = {rank}"
                )

    def test_parse_ru_spot_check_ranking(self, mock_pdfplumber_ru):
        """Verify a specific known ranking from the Russian PDF."""
        result = self.parser.parse(self.VALID_RU_URL, b"%PDF")
        # Лавр Пахомова ranked Субботин Денис Даниилович & Назар Владиславович Буров 2nd
        comp_319 = [c for c in result.competitors if "Субботин" in c]
        assert len(comp_319) == 1
        assert result.rankings["Лавр Пахомова"][comp_319[0]] == 2
