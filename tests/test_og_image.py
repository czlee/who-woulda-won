"""Tests for api/og_image.py."""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from api.og_image import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


SAMPLE_OG_ROWS = [
    {"name": "Alice Smith & Bob Jones", "ranks": [1, 2, 1, 3]},
    {"name": "Carol Davis & Dave Evans", "ranks": [2, 1, 2, 1]},
    {"name": "Eve Franklin & Frank Green", "ranks": [3, 3, 3, 2]},
    {"name": "Grace Hill & Henry Irwin", "ranks": [4, 4, 4, 4]},
]


class TestOgImageEndpoint:
    def test_returns_png_for_known_url(self, client):
        with patch("api.og_image.kv.get_competition_name", return_value="Awesome Open 2025"):
            with patch("api.og_image.kv.get_og_rows", return_value=SAMPLE_OG_ROWS):
                response = client.get("/api/og_image?url=https://scoring.dance/events/1/results/2.html")
        assert response.status_code == 200
        assert response.content_type == "image/png"
        assert response.headers["Cache-Control"] == "public, max-age=31536000, immutable"
        assert response.data[:4] == b"\x89PNG"

    def test_returns_fallback_for_unknown_url(self, client):
        with patch("api.og_image.kv.get_competition_name", return_value=None):
            with patch("api.og_image.kv.get_og_rows", return_value=None):
                response = client.get("/api/og_image?url=https://scoring.dance/events/9/results/9.html")
        assert response.status_code == 200
        assert response.content_type == "image/png"
        assert response.data[:4] == b"\x89PNG"

    def test_no_params_returns_generic_png(self, client):
        response = client.get("/api/og_image")
        assert response.status_code == 200
        assert response.content_type == "image/png"
        assert response.data[:4] == b"\x89PNG"

    def test_division_passed_to_kv(self, client):
        with patch("api.og_image.kv.get_competition_name", return_value="My Event") as mock_name:
            with patch("api.og_image.kv.get_og_rows", return_value=[]) as mock_rows:
                client.get("/api/og_image?url=https://eepro.com/scores/123&division=novice")
        mock_name.assert_called_once_with("https://eepro.com/scores/123", "novice")
        mock_rows.assert_called_once_with("https://eepro.com/scores/123", "novice")
