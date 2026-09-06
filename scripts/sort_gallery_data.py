#!/usr/bin/env python3
"""Sort public/gallery-data.js in place.

Sort order:
1. Date, reverse chronological.
2. Event, alphabetically.
3. Non-Strictly divisions before Strictly divisions.
4. Level, in descending order: Champions, All-Star, Advanced, Intermediate,
   Novice, Newcomer, then any other level (e.g. All-American) alphabetically.
"""

import re
import sys
from datetime import date as date_cls
from pathlib import Path

GALLERY_DATA_PATH = Path(__file__).parent.parent / "public" / "gallery-data.js"

LEVEL_ORDER = ["champion", "allstar", "advanced", "intermediate", "novice", "newcomer"]

ENTRY_RE = re.compile(
    r"date:\s*'(?P<date>[^']*)'.*?event:\s*'(?P<event>[^']*)'.*?division:\s*'(?P<division>[^']*)'"
)


def normalize(text: str) -> str:
    letters_only = re.sub(r"[^a-z]", "", text.lower())
    return letters_only.rstrip("s")


def sort_key(line: str):
    match = ENTRY_RE.search(line)
    if not match:
        raise ValueError(f"Could not parse gallery entry: {line!r}")

    date_str = match.group("date")
    event = match.group("event")
    division = match.group("division")

    is_strictly = "strictly" in division.lower()
    base_division = re.sub(r"strictly", "", division, flags=re.IGNORECASE).strip()
    normalized_base = normalize(base_division)

    if normalized_base in LEVEL_ORDER:
        level_rank = LEVEL_ORDER.index(normalized_base)
        other_text = ""
    else:
        level_rank = len(LEVEL_ORDER)
        other_text = division.lower()

    reverse_date = -date_cls.fromisoformat(date_str).toordinal()
    return (reverse_date, event, is_strictly, level_rank, other_text)


def main():
    text = GALLERY_DATA_PATH.read_text()

    lines = text.splitlines(keepends=True)
    start = next(i for i, line in enumerate(lines) if "GALLERY_ITEMS" in line) + 1
    end = next(i for i, line in enumerate(lines) if line.strip() == "];")

    entries = lines[start:end]
    entries.sort(key=sort_key)

    lines[start:end] = entries
    GALLERY_DATA_PATH.write_text("".join(lines))
    print(f"Sorted {len(entries)} gallery entries.")


if __name__ == "__main__":
    sys.exit(main())
