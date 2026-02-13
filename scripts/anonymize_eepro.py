"""Anonymize the eepro.com example HTML file.

Parses the HTML to discover all personal names (judges, competitors) across
all divisions, generates fake replacements using faker with a fixed seed,
and writes an anonymized copy.

Usage:
    python scripts/anonymize_eepro.py examples/eepro.com-example.html
    python scripts/anonymize_eepro.py examples/eepro.com-example.html -o output.html
"""

import argparse
from pathlib import Path

from bs4 import BeautifulSoup
from faker import Faker

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "test_parsers" / "fixtures"
DEFAULT_OUTPUT = FIXTURES_DIR / "eepro.html"

SEED = 20260201


def discover_names(html: str) -> set[str]:
    """Discover all personal names in the HTML.

    Finds judge names (from header rows) and competitor names (from data rows)
    across all divisions. Returns deduplicated names preserving exact case as
    found, but also tracking case-insensitive duplicates.
    """
    soup = BeautifulSoup(html, "lxml")
    names: set[str] = set()

    tables = soup.find_all("table")
    for table in tables:
        header_row = table.find("tr", bgcolor="#ffae5e")
        if not header_row:
            continue

        rows = table.find_all("tr")
        if len(rows) < 3:
            continue

        # Parse column headers to find judge names
        header_cells = rows[1].find_all("td")
        headers = [cell.get_text(strip=True) for cell in header_cells]

        try:
            comp_idx = next(i for i, h in enumerate(headers)
                           if "competitor" in h.lower())
            bib_idx = next(i for i, h in enumerate(headers)
                          if "bib" in h.lower())
        except StopIteration:
            continue

        # Judge names are between Competitor and BIB columns
        for i in range(comp_idx + 1, bib_idx):
            judge_name = headers[i]
            if judge_name:
                names.add(judge_name)

        # Competitor names from data rows
        for row in rows[2:]:
            cells = row.find_all("td")
            if len(cells) > comp_idx:
                competitor = cells[comp_idx].get_text(strip=True)
                if competitor:
                    names.add(competitor)

    return names


def split_competitor_name(name: str) -> list[str]:
    """Split a competitor name into individual person names.

    Handles patterns like "First Last and First Last".
    """
    parts = name.split(" and ")
    return [p.strip() for p in parts if p.strip()]


def generate_fake_names(names: set[str], seed: int) -> dict[str, str]:
    """Generate a mapping of real names to fake names.

    For competitor names containing " and " (leader and follower), each
    person is replaced individually so the same person gets the same fake
    name across divisions.
    """
    fake = Faker(["en_US", "en_GB", "de_DE", "fr_FR"])
    Faker.seed(seed)

    # First, collect all individual person names
    person_names: set[str] = set()
    compound_names: set[str] = set()

    for name in names:
        parts = split_competitor_name(name)
        if len(parts) > 1:
            compound_names.add(name)
            for part in parts:
                person_names.add(part)
        else:
            person_names.add(name)

    # Generate fake names for each individual person
    person_mapping: dict[str, str] = {}
    used_fakes: set[str] = set()

    # Group by case-insensitive key to give same fake name
    # to different case variants (e.g., "JANE DOE" and "Jane Doe")
    lower_to_canonical: dict[str, str] = {}
    for name in sorted(person_names):
        lower = name.lower()
        if lower not in lower_to_canonical:
            lower_to_canonical[lower] = name

    for lower_name in sorted(lower_to_canonical.keys()):
        canonical = lower_to_canonical[lower_name]
        fake_name = fake.name()
        while fake_name.lower() in {n.lower() for n in person_names} or \
                fake_name.lower() in {n.lower() for n in used_fakes}:
            fake_name = fake.name()
        used_fakes.add(fake_name)

        # Map all case variants of this person
        for name in sorted(person_names):
            if name.lower() == lower_name:
                if name.isupper():
                    person_mapping[name] = fake_name.upper()
                else:
                    person_mapping[name] = fake_name

    # Build the full mapping: individual names + compound names
    mapping: dict[str, str] = {}
    mapping.update(person_mapping)

    for compound in compound_names:
        parts = split_competitor_name(compound)
        fake_parts = [person_mapping.get(p, p) for p in parts]
        mapping[compound] = " and ".join(fake_parts)

    return mapping


def apply_replacements(html: str, mapping: dict[str, str]) -> str:
    """Apply all replacements to the HTML string.

    Replaces longer strings first to avoid partial matches.
    """
    for original in sorted(mapping, key=len, reverse=True):
        replacement = mapping[original]
        html = html.replace(original, replacement)

    return html


def main():
    parser = argparse.ArgumentParser(
        description="Anonymize eepro.com example HTML")
    parser.add_argument("input", help="Path to the input HTML file")
    parser.add_argument("-o", "--output", default=str(DEFAULT_OUTPUT),
                        help=f"Output path (default: {DEFAULT_OUTPUT})")
    args = parser.parse_args()

    html = Path(args.input).read_text(encoding="utf-8")

    names = discover_names(html)
    print(f"Found {len(names)} unique name strings")

    mapping = generate_fake_names(names, SEED)

    for original, fake in sorted(mapping.items()):
        print(f"  {original} -> {fake}")

    result = apply_replacements(html, mapping)

    # Verify no original names remain
    remaining = []
    for name in names:
        if name in result:
            remaining.append(name)
    if remaining:
        print(f"WARNING: {len(remaining)} names still found: {remaining}")
    else:
        print("All names successfully replaced.")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result, encoding="utf-8")
    print(f"Written to {output_path}")


if __name__ == "__main__":
    main()
