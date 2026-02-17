"""Shared fixtures for parser tests."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "examples"
FIXTURES_DIR = Path(__file__).parent / "fixtures"


# --- HTML fixtures (anonymized) ---

@pytest.fixture
def scoring_dance_html():
    path = FIXTURES_DIR / "scoring-dance.html"
    return path.read_bytes()


@pytest.fixture
def eepro_html():
    path = FIXTURES_DIR / "eepro.html"
    return path.read_bytes()


# --- PDF fixtures ---

@pytest.fixture
def danceconvention_pdf():
    """Raw PDF bytes -- only available when the real example file is present.

    Used for can_parse_content and content-detection integration tests.
    """
    path = EXAMPLES_DIR / "danceconvention.net-example.pdf"
    if not path.exists():
        pytest.skip("danceconvention.net-example.pdf not present locally")
    return path.read_bytes()


@pytest.fixture
def danceconvention_ru_pdf():
    """Raw PDF bytes for the Russian example -- only when present."""
    path = EXAMPLES_DIR / "danceconvention.net-example-ru.pdf"
    if not path.exists():
        pytest.skip("danceconvention.net-example-ru.pdf not present locally")
    return path.read_bytes()


@pytest.fixture
def pdf_bytes():
    """Trivial PDF-like bytes for cross-parser rejection tests."""
    return b"%PDF-1.4 fake"


# --- JSON fixtures for danceconvention (anonymized extracted data) ---

@pytest.fixture
def danceconvention_json():
    """Anonymized extracted PDF data (English) as parsed page dicts."""
    path = FIXTURES_DIR / "danceconvention.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def danceconvention_ru_json():
    """Anonymized extracted PDF data (Russian) as parsed page dicts."""
    path = FIXTURES_DIR / "danceconvention-ru.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _make_mock_pdf(pages_data: list[dict]) -> MagicMock:
    """Create a mock pdfplumber PDF object from extracted page data."""
    mock_pages = []
    for page_data in pages_data:
        mock_page = MagicMock()
        mock_page.extract_text.return_value = page_data["text"]
        mock_page.extract_tables.return_value = page_data["tables"]
        mock_pages.append(mock_page)

    mock_pdf = MagicMock()
    mock_pdf.pages = mock_pages
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)
    return mock_pdf


@pytest.fixture
def mock_pdfplumber_en(danceconvention_json, monkeypatch):
    """Monkeypatch pdfplumber.open to return anonymized English PDF data."""
    import pdfplumber

    mock_pdf = _make_mock_pdf(danceconvention_json)
    monkeypatch.setattr(pdfplumber, "open", lambda *args, **kwargs: mock_pdf)
    return mock_pdf


@pytest.fixture
def mock_pdfplumber_ru(danceconvention_ru_json, monkeypatch):
    """Monkeypatch pdfplumber.open to return anonymized Russian PDF data."""
    import pdfplumber

    mock_pdf = _make_mock_pdf(danceconvention_ru_json)
    monkeypatch.setattr(pdfplumber, "open", lambda *args, **kwargs: mock_pdf)
    return mock_pdf


def _make_prelims_page_data(use_alternates=False):
    """Create synthetic prelims PDF page data with callback scores."""
    judges = ["AB", "CD", "EF"]
    text = (
        "Some Event 2026\nNovice Prelims\n"
        "AB Alice Baker\nCD Carol Davis\nEF Eve Foster\n"
    )
    header = ["#", "Name", "AB", "CD", "EF", "Sum", "Result"]
    rows = []
    for i in range(1, 6):
        name = f"Leader {i}\nFollower {i}"
        if use_alternates and i == 3:
            rows.append([str(i), name, "4.5", "10", "0", "14.5", "Alt 1"])
        else:
            yes_no = ["10", "0", "10"] if i % 2 == 1 else ["0", "10", "0"]
            total = str(sum(int(v) for v in yes_no))
            rows.append([str(i), name, *yes_no, total, "Yes" if i % 2 == 1 else ""])
    table = [header] + rows
    return [{"text": text, "tables": [table]}]


@pytest.fixture
def mock_pdfplumber_prelims(monkeypatch):
    """Monkeypatch pdfplumber.open to return synthetic prelims PDF data."""
    import pdfplumber

    mock_pdf = _make_mock_pdf(_make_prelims_page_data(use_alternates=False))
    monkeypatch.setattr(pdfplumber, "open", lambda *args, **kwargs: mock_pdf)
    return mock_pdf


@pytest.fixture
def mock_pdfplumber_prelims_alt(monkeypatch):
    """Monkeypatch pdfplumber.open to return prelims data with alternate scores."""
    import pdfplumber

    mock_pdf = _make_mock_pdf(_make_prelims_page_data(use_alternates=True))
    monkeypatch.setattr(pdfplumber, "open", lambda *args, **kwargs: mock_pdf)
    return mock_pdf
