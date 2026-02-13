"""Anonymize the danceconvention.net example PDF files.

Extracts text and tables per page using pdfplumber, anonymizes names in the
extracted data, and saves as JSON fixtures that can be used to mock pdfplumber
in tests.

Usage:
    python scripts/anonymize_danceconvention.py examples/danceconvention.net-example.pdf
    python scripts/anonymize_danceconvention.py examples/danceconvention.net-example.pdf -o out.json
    python scripts/anonymize_danceconvention.py examples/danceconvention.net-example-ru.pdf \
        --locale ru_RU -o fixtures/danceconvention-ru.json
"""

import argparse
import json
import re
from io import BytesIO
from pathlib import Path

import pdfplumber
from faker import Faker

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "test_parsers" / "fixtures"
DEFAULT_OUTPUT = FIXTURES_DIR / "danceconvention.json"

SEED = 20260301


def extract_pdf_data(pdf_bytes: bytes) -> list[dict]:
    """Extract text and tables from each page of the PDF."""
    pages_data = []
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            tables = page.extract_tables() or []
            pages_data.append({
                "text": text,
                "tables": tables,
            })
    return pages_data


def is_judge_initials(s: str) -> bool:
    """Check if a string looks like judge initials (2-4 alphanumeric chars)."""
    return 2 <= len(s) <= 4 and s.isalnum()


def extract_judge_key(text: str) -> dict[str, str]:
    """Extract judge initials -> full name mapping from text."""
    judge_key = {}
    for line in text.split("\n"):
        words = line.strip().split()
        if len(words) < 3:
            continue
        initials = words[0]
        if not is_judge_initials(initials):
            continue
        name_parts = words[1:]
        if all(w.isalpha() for w in name_parts):
            judge_key[initials] = " ".join(name_parts)
    return judge_key


def is_results_header(header: list) -> bool:
    """Check if a table header row looks like a results table."""
    for cell in (header or [])[:2]:
        if cell and str(cell).strip() == "#":
            return True
    return False


def find_column_indices(header: list) -> dict[str, int]:
    """Find key column indices in a results table header."""
    indices = {
        "number": 0,
        "name": 1,
        "judge_start": 2,
        "judge_end": len(header),
    }
    for i, cell in enumerate(header):
        if not cell:
            continue
        cell_str = str(cell).strip()
        if cell_str == "#":
            indices["number"] = i
            indices["name"] = i + 1
            indices["judge_start"] = i + 2
        elif cell_str.startswith("1-"):
            indices["judge_end"] = min(indices["judge_end"], i)
    return indices


def extract_competitor_names(pages_data: list[dict]) -> list[str]:
    """Extract competitor names from results tables."""
    names = []
    for page in pages_data:
        for table in page["tables"]:
            if not table or len(table) < 2:
                continue
            header = table[0]
            if not is_results_header(header):
                continue
            col_indices = find_column_indices(header)
            name_idx = col_indices["name"]
            for row in table[1:]:
                if not row or len(row) <= name_idx:
                    continue
                name_cell = row[name_idx]
                if name_cell:
                    name = str(name_cell).strip()
                    if name:
                        names.append(name)
    return names


def discover_names(pages_data: list[dict]) -> tuple[dict[str, str], list[str]]:
    """Discover all personal names in the extracted PDF data.

    Returns (judge_key, competitor_names) where judge_key is
    {initials: full_name} and competitor_names is a list of raw name strings
    from the tables.
    """
    all_text = "\n".join(page["text"] for page in pages_data)
    judge_key = extract_judge_key(all_text)
    competitor_names = extract_competitor_names(pages_data)
    return judge_key, competitor_names


def _simple_fake_name(fake: Faker) -> str:
    """Generate a simple two-word alphabetic name (no hyphens, titles, etc.).

    The danceconvention parser's judge key extraction requires each word
    in the judge name to pass str.isalpha(), so we must avoid names with
    hyphens, periods, or other non-alpha characters.
    """
    for _ in range(100):
        name = f"{fake.first_name()} {fake.last_name()}"
        if all(w.isalpha() for w in name.split()):
            return name
    return f"{fake.first_name()} {fake.last_name()}"  # fallback


def generate_fake_judge_names(judge_key: dict[str, str], fake: Faker
                              ) -> dict[str, str]:
    """Generate fake names for judges. Returns {real_name: fake_name}."""
    mapping: dict[str, str] = {}
    all_real = set(judge_key.values())

    for initials in sorted(judge_key.keys()):
        real_name = judge_key[initials]
        if real_name in mapping:
            continue
        fake_name = _simple_fake_name(fake)
        while fake_name in all_real or fake_name in mapping.values():
            fake_name = _simple_fake_name(fake)
        mapping[real_name] = fake_name

    return mapping


def generate_fake_competitor_names(competitor_names: list[str], fake: Faker
                                  ) -> dict[str, str]:
    """Generate fake names for competitors.

    Competitor names may contain newlines (leader\\nfollower format).
    Each individual person gets a unique fake name.
    """
    # Split compound names into individual people
    person_names: set[str] = set()
    for name in competitor_names:
        # Names may be "Leader\\nFollower" or just "Leader & Follower"
        parts = re.split(r"\n", name)
        for part in parts:
            part = part.strip()
            if part:
                person_names.add(part)

    person_mapping: dict[str, str] = {}
    for person in sorted(person_names):
        fake_name = fake.name()
        while fake_name in person_names or fake_name in person_mapping.values():
            fake_name = fake.name()
        person_mapping[person] = fake_name

    # Build full mapping for compound names
    mapping: dict[str, str] = {}
    mapping.update(person_mapping)
    for name in competitor_names:
        if name not in mapping:
            parts = re.split(r"\n", name)
            fake_parts = [person_mapping.get(p.strip(), p.strip())
                          for p in parts]
            mapping[name] = "\n".join(fake_parts)

    return mapping


def apply_replacements(pages_data: list[dict],
                       judge_mapping: dict[str, str],
                       competitor_mapping: dict[str, str]) -> list[dict]:
    """Apply name replacements to the extracted PDF data."""
    # Build combined mapping, longest first
    all_mappings: dict[str, str] = {}
    all_mappings.update(judge_mapping)
    all_mappings.update(competitor_mapping)

    sorted_replacements = sorted(all_mappings.items(), key=lambda x: len(x[0]),
                                 reverse=True)

    result = []
    for page in pages_data:
        # Replace in text
        text = page["text"]
        for original, replacement in sorted_replacements:
            text = text.replace(original, replacement)

        # Replace in tables
        new_tables = []
        for table in page["tables"]:
            new_table = []
            for row in table:
                new_row = []
                for cell in row:
                    if cell is None:
                        new_row.append(None)
                    else:
                        cell_str = str(cell)
                        for original, replacement in sorted_replacements:
                            cell_str = cell_str.replace(original, replacement)
                        new_row.append(cell_str)
                new_table.append(new_row)
            new_tables.append(new_table)

        result.append({
            "text": text,
            "tables": new_tables,
        })

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Anonymize danceconvention.net example PDF")
    parser.add_argument("input", help="Path to the input PDF file")
    parser.add_argument("-o", "--output", default=str(DEFAULT_OUTPUT),
                        help=f"Output path (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--locale", default="en_US",
                        help="Faker locale for generating names (default: en_US)")
    args = parser.parse_args()

    pdf_bytes = Path(args.input).read_bytes()

    pages_data = extract_pdf_data(pdf_bytes)
    print(f"Extracted {len(pages_data)} pages")

    judge_key, competitor_names = discover_names(pages_data)
    print(f"Found {len(judge_key)} judges and {len(competitor_names)} "
          f"competitor entries")

    locales = ["en_US", "en_GB", "de_DE", "fr_FR"]
    if args.locale not in locales:
        locales.insert(0, args.locale)
    fake = Faker(locales)
    Faker.seed(SEED)

    judge_mapping = generate_fake_judge_names(judge_key, fake)
    competitor_mapping = generate_fake_competitor_names(competitor_names, fake)

    print("Judge replacements:")
    for original, replacement in sorted(judge_mapping.items()):
        print(f"  {original} -> {replacement}")
    print("Competitor replacements (individuals):")
    for original, replacement in sorted(competitor_mapping.items()):
        if "\n" not in original:
            print(f"  {original} -> {replacement}")

    result = apply_replacements(pages_data, judge_mapping, competitor_mapping)

    # Verify no original names remain in text
    all_originals = set(judge_mapping.keys()) | set(competitor_mapping.keys())
    remaining = []
    for page in result:
        for name in all_originals:
            if name in page["text"]:
                remaining.append(name)
    if remaining:
        print(f"WARNING: {len(remaining)} names still found in text: "
              f"{set(remaining)}")
    else:
        print("All names successfully replaced.")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"Written to {output_path}")


if __name__ == "__main__":
    main()
