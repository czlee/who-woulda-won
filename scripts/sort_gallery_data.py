#!/usr/bin/env python3
"""Sort public/gallery-data.js in place.

Sort order:
1. Date, reverse chronological.
2. Event, alphabetically.
3. Non-Strictly divisions before Strictly divisions.
4. Level, in descending order: Champions, All-Star, Advanced, Intermediate,
   Novice, Newcomer, then any other level (e.g. All-American) alphabetically.
   A joint division (e.g. "Nov/Int") ranks just below its highest
   constituent level.
"""

import re
import sys
from datetime import date as date_cls
from pathlib import Path

GALLERY_DATA_PATH = Path(__file__).parent.parent / "public" / "gallery-data.js"

LEVEL_ORDER = ["champion", "allstar", "advanced", "intermediate", "novice", "newcomer"]

# Tokens (after splitting a division on non-letters and singularizing) that
# identify a level, including the abbreviations used in joint-level names
# (e.g. "Nov/Int", "Adv/AllStar" — see ALL_STAR_PHRASE_RE below for how
# "All-Star"/"All Stars" get folded into a single "AllStar" token first).
TOKEN_RANK = {level: rank for rank, level in enumerate(LEVEL_ORDER)}
TOKEN_RANK.update(champ=0, adv=2, int=3, nov=4, new=5)

# Matches "All-Star"/"All Stars"/"All Star" so it becomes a single "AllStar"
# token instead of splitting into a bare, ambiguous "All" (which would
# otherwise wrongly match unrelated divisions like "All-European").
ALL_STAR_PHRASE_RE = re.compile(r"all[\s-]?stars?", re.IGNORECASE)

ENTRY_RE = re.compile(
    r"date:\s*'(?P<date>[^']*)'.*?event:\s*'(?P<event>[^']*)'.*?division:\s*'(?P<division>[^']*)'"
)


def singularize(token: str) -> str:
    return token.lower().rstrip("s")


def level_rank(division: str):
    """Rank a division by skill level, lower is higher (Champions=0, All-Star=1,
    ..., Newcomer=5). A joint division (e.g. "Nov/Int") ranks just below its
    highest constituent level, so it sits between that level and the next.
    Returns None if no recognized level token is found."""
    text = ALL_STAR_PHRASE_RE.sub("AllStar", division)
    tokens = re.split(r"[^A-Za-z]+", text)
    ranks = {TOKEN_RANK[singularize(t)] for t in tokens if singularize(t) in TOKEN_RANK}
    if not ranks:
        return None
    return min(ranks) if len(ranks) == 1 else min(ranks) + 0.5


def sort_key(line: str):
    match = ENTRY_RE.search(line)
    if not match:
        raise ValueError(f"Could not parse gallery entry: {line!r}")

    date_str = match.group("date")
    event = match.group("event")
    division = match.group("division")

    is_strictly = "strictly" in division.lower()
    base_division = re.sub(r"strictly", "", division, flags=re.IGNORECASE).strip()
    rank = level_rank(base_division)

    if rank is not None:
        other_text = ""
    else:
        rank = len(LEVEL_ORDER)
        other_text = division.lower()

    reverse_date = -date_cls.fromisoformat(date_str).toordinal()
    return (reverse_date, event, is_strictly, rank, other_text)


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
