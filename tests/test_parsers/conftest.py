"""Shared fixtures for parser tests."""

import html as _html
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "examples"
FIXTURES_DIR = Path(__file__).parent / "fixtures"


# --- HTML builders ---

@pytest.fixture
def make_eepro_html():
    """Factory fixture: returns minimal eepro HTML bytes with one stub table per division name."""
    def _make(division_names: list[str]) -> bytes:
        tables = "".join(
            f"<table border='1'><tr bgcolor='#ffae5e'><td colspan='5'>{_html.escape(name)}</td></tr>"
            f"<tr><td>Place</td><td>Competitor</td><td>Judge A</td><td>BIB</td><td>Marks Sorted</td></tr>"
            f"<tr><td>1</td><td>Alice</td><td>1</td><td>101</td><td>1</td></tr>"
            f"<tr><td>2</td><td>Bob</td><td>2</td><td>102</td><td>2</td></tr>"
            f"</table>"
            for name in division_names
        )
        return (
            f"<html><head><title>Event Express Pro</title></head>"
            f"<body><h2>Test Event</h2>{tables}</body></html>"
        ).encode()
    return _make


# --- HTML fixtures (anonymized) ---

@pytest.fixture
def scoring_dance_html():
    path = FIXTURES_DIR / "scoring-dance.html"
    return path.read_bytes()


@pytest.fixture
def eepro_html():
    path = FIXTURES_DIR / "eepro.html"
    return path.read_bytes()


@pytest.fixture
def eepro_mixed_html():
    path = FIXTURES_DIR / "eepro-prelims-finals-same-page.html"
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


@pytest.fixture
def danceconvention_full_tie_json():
    path = FIXTURES_DIR / "danceconvention-full-tie.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def mock_pdfplumber_full_tie(danceconvention_full_tie_json, monkeypatch):
    import pdfplumber
    mock_pdf = _make_mock_pdf(danceconvention_full_tie_json)
    monkeypatch.setattr(pdfplumber, "open", lambda *args, **kwargs: mock_pdf)
    return mock_pdf


def _make_multi_competition_page_data():
    """Four-page PDF with two competitions (leaders + followers), each spanning two pages."""
    def _make_finals_table(judges, competitors):
        cumulative = [f"1-{i}" for i in range(1, len(competitors) + 1)]
        header = ["#", "Name"] + judges + cumulative + ["Result"]
        rows = []
        for bib, (name, ranks) in enumerate(competitors, start=1):
            rows.append([str(bib), name] + [str(r) for r in ranks] + [""] * (len(cumulative) + 1))
        return [header] + rows

    leaders_judges = ["AB", "CD", "EF"]
    leaders_text_p1 = (
        "Great Event 2025\nPro-Am Novice Leaders Finals\n"
        "AB Alice Baker\nCD Carol Davis\nEF Eve Foster\n"
    )
    leaders_table_p1 = _make_finals_table(
        leaders_judges,
        [
            ("Leader One\nFollower One", [1, 2, 1]),
            ("Leader Two\nFollower Two", [2, 1, 3]),
            ("Leader Three\nFollower Three", [3, 3, 2]),
        ],
    )
    # Continuation page: text starts with "#" (table column header row)
    leaders_text_p2 = "# Name AB CD EF 1-1 1-2 1-3 Result\n"
    leaders_table_p2 = _make_finals_table(
        leaders_judges,
        [
            ("Leader Four\nFollower Four", [4, 4, 4]),
            ("Leader Five\nFollower Five", [5, 5, 5]),
        ],
    )

    followers_judges = ["GH", "IJ", "KL"]
    followers_text_p1 = (
        "Great Event 2025\nPro-Am Novice Followers Finals\n"
        "GH Grace Hill\nIJ Iris Jones\nKL Karen Lee\n"
    )
    followers_table_p1 = _make_finals_table(
        followers_judges,
        [
            ("Leader A\nFollower A", [1, 1, 2]),
            ("Leader B\nFollower B", [2, 2, 1]),
            ("Leader C\nFollower C", [3, 3, 3]),
        ],
    )
    followers_text_p2 = "# Name GH IJ KL 1-1 1-2 1-3 Result\n"
    followers_table_p2 = _make_finals_table(
        followers_judges,
        [
            ("Leader D\nFollower D", [4, 4, 4]),
            ("Leader E\nFollower E", [5, 5, 5]),
        ],
    )

    return [
        {"text": leaders_text_p1, "tables": [leaders_table_p1]},
        {"text": leaders_text_p2, "tables": [leaders_table_p2]},
        {"text": followers_text_p1, "tables": [followers_table_p1]},
        {"text": followers_text_p2, "tables": [followers_table_p2]},
    ]


@pytest.fixture
def mock_pdfplumber_multi(monkeypatch):
    """Monkeypatch pdfplumber.open to return a two-competition PDF."""
    import pdfplumber

    mock_pdf = _make_mock_pdf(_make_multi_competition_page_data())
    monkeypatch.setattr(pdfplumber, "open", lambda *args, **kwargs: mock_pdf)
    return mock_pdf


def _make_duplicate_names_page_data():
    """Create a finals PDF where two competitors share the same cleaned name."""
    judges = ["AB", "CD", "EF"]
    text = (
        "Some Event 2026\nNovice J&J Finals\n"
        "AB Alice Baker\nCD Carol Davis\nEF Eve Foster\n"
    )
    # bibs 3 and 5 will have the same name after _clean_competitor_name
    competitor_rows = [
        ("1", "Alpha\nBeta",         [1, 2, 1]),
        ("2", "Gamma\nDelta",        [2, 1, 2]),
        ("3", "Redacted\nRedacted",  [3, 4, 3]),
        ("4", "Epsilon\nZeta",       [4, 3, 4]),
        ("5", "Redacted\nRedacted",  [5, 5, 5]),
    ]
    cumulative = [f"1-{i}" for i in range(1, len(competitor_rows) + 1)]
    header = ["#", "Name"] + judges + cumulative + ["Result"]
    rows = [
        [bib, name] + [str(r) for r in ranks] + [""] * (len(cumulative) + 1)
        for bib, name, ranks in competitor_rows
    ]
    return [{"text": text, "tables": [[header] + rows]}]


@pytest.fixture
def mock_pdfplumber_duplicate_names(monkeypatch):
    """Monkeypatch pdfplumber.open to return finals data with duplicate competitor names."""
    import pdfplumber
    mock_pdf = _make_mock_pdf(_make_duplicate_names_page_data())
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
