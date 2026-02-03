"""Shared test helpers."""

from core.models import Scoresheet


def make_scoresheet(name: str, rankings_table: dict[str, dict[str, int]]) -> Scoresheet:
    """Build a Scoresheet from a compact rankings table.

    Args:
        name: Competition name
        rankings_table: {judge_id: {competitor_id: rank}}

    Returns:
        Scoresheet with judges, competitors, and rankings populated.
    """
    judges = list(rankings_table.keys())
    # Get competitors from first judge's rankings
    competitors = list(next(iter(rankings_table.values())).keys())
    return Scoresheet(
        competition_name=name,
        competitors=competitors,
        judges=judges,
        rankings=rankings_table,
    )
