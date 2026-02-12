"""Shared fixtures for parser tests."""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "examples"


@pytest.fixture
def scoring_dance_html():
    path = EXAMPLES_DIR / "scoring.dance-example.html"
    return path.read_bytes()


@pytest.fixture
def eepro_html():
    path = EXAMPLES_DIR / "eepro.com-example.html"
    return path.read_bytes()


@pytest.fixture
def danceconvention_pdf():
    path = EXAMPLES_DIR / "danceconvention.net-example.pdf"
    return path.read_bytes()


@pytest.fixture
def danceconvention_ru_pdf():
    path = EXAMPLES_DIR / "danceconvention.net-example-ru.pdf"
    return path.read_bytes()
