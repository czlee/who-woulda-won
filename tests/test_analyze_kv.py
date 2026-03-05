"""Integration tests: api/analyze.py calls kv.set_meta after URL-based analysis."""

import json
from unittest.mock import MagicMock, patch

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.analyze import app
from core.analyze import AnalysisResult
from core.models import Scoresheet


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _make_mock_result(competition_name="Test Competition 2025"):
    mock_scoresheet = MagicMock(spec=Scoresheet)
    mock_scoresheet.competition_name = competition_name
    mock_result = MagicMock(spec=AnalysisResult)
    mock_result.scoresheet = mock_scoresheet
    mock_result.results = []
    mock_result.to_dict.return_value = {
        "competition_name": competition_name,
        "competitors": [],
        "judges": [],
        "num_competitors": 0,
        "num_judges": 0,
        "rankings": [],
        "results": [],
        "summary": {},
    }
    return mock_result


class TestKvCalledForUrlAnalysis:
    def test_set_meta_called_after_url_analysis(self, client):
        mock_result = _make_mock_result("Awesome Open 2025")
        with patch("api.analyze.detect_parser", return_value=MagicMock()):
            with patch("api.analyze.fetch_url", return_value=("https://scoring.dance/events/1/results/2.html", b"")):
                with patch("api.analyze.analyze_scoresheet", return_value=mock_result):
                    with patch("api.analyze.kv.set_meta") as mock_set_meta:
                        response = client.post(
                            "/api/analyze",
                            data=json.dumps({"url": "https://scoring.dance/events/1/results/2.html"}),
                            content_type="application/json",
                        )
        assert response.status_code == 200
        mock_set_meta.assert_called_once_with(
            "https://scoring.dance/events/1/results/2.html",
            None,
            "Awesome Open 2025",
            og_rows=[],
        )

    def test_set_meta_called_with_division(self, client):
        mock_result = _make_mock_result("Awesome Open 2025 - Novice")
        with patch("api.analyze.detect_parser", return_value=MagicMock()):
            with patch("api.analyze.fetch_url", return_value=("https://eepro.com/scores/123", b"")):
                with patch("api.analyze.analyze_scoresheet", return_value=mock_result):
                    with patch("api.analyze.kv.set_meta") as mock_set_meta:
                        response = client.post(
                            "/api/analyze",
                            data=json.dumps({"url": "https://eepro.com/scores/123", "division": "novice"}),
                            content_type="application/json",
                        )
        assert response.status_code == 200
        mock_set_meta.assert_called_once_with(
            "https://eepro.com/scores/123",
            "novice",
            "Awesome Open 2025 - Novice",
            og_rows=[],
        )

    def test_set_meta_not_called_for_file_upload(self, client):
        mock_result = _make_mock_result("File Upload Competition")
        with patch("api.analyze.analyze_scoresheet", return_value=mock_result):
            with patch("api.analyze.kv.set_meta") as mock_set_meta:
                from io import BytesIO
                response = client.post(
                    "/api/analyze",
                    data={"file": (BytesIO(b"<html></html>"), "scoresheet.html")},
                    content_type="multipart/form-data",
                )
        mock_set_meta.assert_not_called()
