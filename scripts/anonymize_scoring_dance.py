"""Anonymize the scoring.dance example HTML file.

Parses the HTML to discover all personal names (judges, competitors) and
WSDC IDs, generates fake replacements using faker with a fixed seed, and
writes an anonymized copy.

Usage:
    python scripts/anonymize_scoring_dance.py examples/scoring.dance-example.html
    python scripts/anonymize_scoring_dance.py examples/scoring.dance-example.html -o output.html
"""

import argparse
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup
from faker import Faker

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "test_parsers" / "fixtures"
DEFAULT_OUTPUT = FIXTURES_DIR / "scoring-dance.html"

SEED = 20260101


def discover_names(html: str) -> tuple[set[str], set[str]]:
    """Discover all personal names and WSDC IDs in the HTML.

    Returns (names, wsdc_ids) where names is a set of name strings and
    wsdc_ids is a set of numeric ID strings.
    """
    soup = BeautifulSoup(html, "lxml")
    names: set[str] = set()
    wsdc_ids: set[str] = set()

    # Parse JSON-LD blocks for names
    for script in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            continue

        results = data.get("result", [])
        for result in results:
            # Judge names from scores or judges_placements
            for key in ("scores", "judges_placements"):
                for jp in result.get(key, []):
                    name = jp.get("name", "")
                    if name:
                        names.add(name)

            # Competitor names and WSDC IDs
            dancer = result.get("dancer", {})
            for role in ("leader", "follower"):
                person = dancer.get(role, {})
                fullname = person.get("fullname", "")
                if fullname:
                    names.add(fullname)
                wsdc = person.get("wsdc", {})
                wsdc_id = wsdc.get("id")
                if wsdc_id:
                    wsdc_ids.add(str(wsdc_id))

    # Also find names in TITLE attributes (catches chief judge etc.)
    for elem in soup.find_all(attrs={"title": True}):
        title = elem["title"].strip()
        if title:
            # Remove "(Chiefjudge)" suffix if present
            cleaned = re.sub(r"\s*\(Chiefjudge\)\s*$", "", title)
            if cleaned and not cleaned.isdigit():
                names.add(cleaned)

    return names, wsdc_ids


def generate_fake_names(names: set[str], seed: int) -> dict[str, str]:
    """Generate a mapping of real names to fake names."""
    fake = Faker(["en_US", "en_GB", "de_DE", "fr_FR"])
    Faker.seed(seed)

    mapping: dict[str, str] = {}
    for name in sorted(names):  # Sort for determinism
        fake_name = fake.name()
        # Ensure no collisions with existing names or other fakes
        while fake_name in names or fake_name in mapping.values():
            fake_name = fake.name()
        mapping[name] = fake_name

    return mapping


def generate_fake_wsdc_ids(wsdc_ids: set[str], seed: int) -> dict[str, str]:
    """Generate a mapping of real WSDC IDs to fake ones."""
    fake = Faker()
    Faker.seed(seed + 1000)  # Different seed from names

    mapping: dict[str, str] = {}
    used: set[str] = set()
    for wsdc_id in sorted(wsdc_ids):
        fake_id = str(fake.random_int(min=10000, max=99999))
        while fake_id in wsdc_ids or fake_id in used:
            fake_id = str(fake.random_int(min=10000, max=99999))
        mapping[wsdc_id] = fake_id
        used.add(fake_id)

    return mapping


def apply_replacements(html: str, name_mapping: dict[str, str],
                       wsdc_mapping: dict[str, str]) -> str:
    """Apply all replacements to the HTML string.

    Replaces longer strings first to avoid partial matches.
    """
    # Replace names (longest first to avoid partial matches)
    for original in sorted(name_mapping, key=len, reverse=True):
        replacement = name_mapping[original]
        html = html.replace(original, replacement)
        # Also handle JSON-escaped versions (for unicode chars like \u00e1)
        json_original = json.dumps(original)[1:-1]  # Strip quotes
        json_replacement = json.dumps(replacement)[1:-1]
        if json_original != original:
            html = html.replace(json_original, json_replacement)

    # Replace WSDC IDs in known contexts to avoid false positives
    for original_id, fake_id in sorted(wsdc_mapping.items()):
        # In JSON: "id":"12345" or "id": "12345"
        html = html.replace(f'"id":"{original_id}"', f'"id":"{fake_id}"')
        html = html.replace(f'"id": "{original_id}"', f'"id": "{fake_id}"')
        # In URLs: /registry/12345.html
        html = html.replace(f"registry/{original_id}.html",
                            f"registry/{fake_id}.html")
        # In data attributes: data-wsdc="12345"
        html = html.replace(f'data-wsdc="{original_id}"',
                            f'data-wsdc="{fake_id}"')

    return html


def main():
    parser = argparse.ArgumentParser(
        description="Anonymize scoring.dance example HTML")
    parser.add_argument("input", help="Path to the input HTML file")
    parser.add_argument("-o", "--output", default=str(DEFAULT_OUTPUT),
                        help=f"Output path (default: {DEFAULT_OUTPUT})")
    args = parser.parse_args()

    html = Path(args.input).read_text(encoding="utf-8")

    names, wsdc_ids = discover_names(html)
    print(f"Found {len(names)} unique names and {len(wsdc_ids)} WSDC IDs")

    name_mapping = generate_fake_names(names, SEED)
    wsdc_mapping = generate_fake_wsdc_ids(wsdc_ids, SEED)

    for original, fake in sorted(name_mapping.items()):
        print(f"  {original} -> {fake}")

    result = apply_replacements(html, name_mapping, wsdc_mapping)

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
