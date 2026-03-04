"""Tests for core/kv.py."""

from unittest.mock import MagicMock, patch

import pytest

from core.kv import normalize_url, get_competition_name, set_meta


class TestNormalizeUrl:
    def test_scoring_dance_with_lang_prefix(self):
        url = "https://scoring.dance/enCA/events/123/results/456.html"
        assert normalize_url(url) == "meta:https://scoring.dance/events/123/results/456.html"

    def test_scoring_dance_without_lang_prefix(self):
        url = "https://scoring.dance/events/123/results/456.html"
        assert normalize_url(url) == "meta:https://scoring.dance/events/123/results/456.html"

    def test_scoring_dance_lang_variants_map_to_same_key(self):
        url_en = "https://scoring.dance/enCA/events/123/results/456.html"
        url_fr = "https://scoring.dance/frFR/events/123/results/456.html"
        url_sv = "https://scoring.dance/svSE/events/123/results/456.html"
        url_bare = "https://scoring.dance/events/123/results/456.html"
        assert normalize_url(url_en) == normalize_url(url_fr)
        assert normalize_url(url_en) == normalize_url(url_sv)
        assert normalize_url(url_en) == normalize_url(url_bare)

    def test_danceconvention_strips_lang_segment(self):
        url = "https://danceconvention.net/eventdirector/fr/roundscores/789.pdf"
        assert normalize_url(url) == "meta:https://danceconvention.net/eventdirector/roundscores/789.pdf"

    def test_danceconvention_lang_variants_map_to_same_key(self):
        url_fr = "https://danceconvention.net/eventdirector/fr/roundscores/789.pdf"
        url_en = "https://danceconvention.net/eventdirector/en/roundscores/789.pdf"
        assert normalize_url(url_fr) == normalize_url(url_en)

    def test_eepro_unchanged(self):
        url = "https://eepro.com/competitions/scores/123"
        assert normalize_url(url) == "meta:https://eepro.com/competitions/scores/123"

    def test_lowercases_url(self):
        url = "https://scoring.dance/Events/123/Results/456.html"
        result = normalize_url(url)
        assert result == result.lower()

    def test_division_appended(self):
        url = "https://eepro.com/competitions/scores/123"
        assert normalize_url(url, division="novice") == "meta:https://eepro.com/competitions/scores/123:novice"

    def test_no_division(self):
        url = "https://eepro.com/competitions/scores/123"
        assert normalize_url(url, division=None) == "meta:https://eepro.com/competitions/scores/123"

    def test_empty_division_not_appended(self):
        url = "https://eepro.com/competitions/scores/123"
        assert normalize_url(url, division="") == "meta:https://eepro.com/competitions/scores/123"

    def test_meta_prefix(self):
        url = "https://eepro.com/competitions/scores/123"
        assert normalize_url(url).startswith("meta:")


class TestGetCompetitionName:
    def test_returns_name_from_kv(self):
        mock_client = MagicMock()
        mock_client.hget.return_value = "My Competition 2025"
        with patch("core.kv._get_client", return_value=mock_client):
            result = get_competition_name("https://eepro.com/competitions/scores/123")
        assert result == "My Competition 2025"

    def test_returns_none_when_not_found(self):
        mock_client = MagicMock()
        mock_client.hget.return_value = None
        with patch("core.kv._get_client", return_value=mock_client):
            result = get_competition_name("https://eepro.com/competitions/scores/123")
        assert result is None

    def test_returns_none_when_client_unavailable(self):
        with patch("core.kv._get_client", return_value=None):
            result = get_competition_name("https://eepro.com/competitions/scores/123")
        assert result is None

    def test_returns_none_on_kv_exception(self):
        mock_client = MagicMock()
        mock_client.hget.side_effect = Exception("connection refused")
        with patch("core.kv._get_client", return_value=mock_client):
            result = get_competition_name("https://eepro.com/competitions/scores/123")
        assert result is None

    def test_passes_division_to_normalize(self):
        mock_client = MagicMock()
        mock_client.hget.return_value = "Division Competition"
        with patch("core.kv._get_client", return_value=mock_client):
            get_competition_name("https://eepro.com/competitions/scores/123", division="novice")
        key_used = mock_client.hget.call_args[0][0]
        assert key_used.endswith(":novice")


class TestSetMeta:
    def test_sets_competition_name_on_first_write(self):
        mock_client = MagicMock()
        mock_client.hget.return_value = None  # no existing first_analyzed_at
        with patch("core.kv._get_client", return_value=mock_client):
            set_meta("https://eepro.com/competitions/scores/123", None, "My Competition")
        call_kwargs = mock_client.hset.call_args
        values = call_kwargs[1]["values"]
        assert values["competition_name"] == "My Competition"
        assert "first_analyzed_at" in values

    def test_preserves_first_analyzed_at_on_update(self):
        mock_client = MagicMock()
        mock_client.hget.return_value = "2026-01-01T00:00:00Z"  # already set
        with patch("core.kv._get_client", return_value=mock_client):
            set_meta("https://eepro.com/competitions/scores/123", None, "Updated Name")
        call_kwargs = mock_client.hset.call_args
        values = call_kwargs[1]["values"]
        assert values["competition_name"] == "Updated Name"
        assert "first_analyzed_at" not in values

    def test_silent_on_kv_exception(self):
        mock_client = MagicMock()
        mock_client.hget.side_effect = Exception("connection refused")
        with patch("core.kv._get_client", return_value=mock_client):
            # Should not raise
            set_meta("https://eepro.com/competitions/scores/123", None, "My Competition")

    def test_silent_when_client_unavailable(self):
        with patch("core.kv._get_client", return_value=None):
            # Should not raise
            set_meta("https://eepro.com/competitions/scores/123", None, "My Competition")

    def test_first_analyzed_at_is_iso_format(self):
        mock_client = MagicMock()
        mock_client.hget.return_value = None
        with patch("core.kv._get_client", return_value=mock_client):
            set_meta("https://eepro.com/competitions/scores/123", None, "My Competition")
        values = mock_client.hset.call_args[1]["values"]
        ts = values["first_analyzed_at"]
        # Should parse as ISO datetime
        from datetime import datetime, timezone
        dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
        assert dt is not None
