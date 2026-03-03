"""Generate controversy summary for analysis results."""

from __future__ import annotations

import statistics
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.analyze import AnalysisResult
    from core.models import VotingResult

RP_SYSTEM_NAME = "Relative Placement"

LABELS = {
    "consistent": "\u2705 Consistent",
    "close_call": "\U0001f914 Close call",
    "shakeup": "\U0001f62e Shakeup",
    "drama": "\U0001f631 Drama!",
}


def summarize(analysis_result: AnalysisResult) -> dict:
    """Generate a controversy label and one-sentence summary.

    Compares the relative placement winner against the other voting systems'
    winners and classifies the level of agreement/disagreement.

    Returns:
        {
            "level": "consistent" | "close_call" | "shakeup" | "drama",
            "label": "...",
            "sentence": "..."
        }
    """
    rp_result = _find_rp_result(analysis_result)
    if rp_result is None:
        return _make_summary(
            "consistent",
            "Could not determine relative placement result for comparison.",
        )

    other_results = [
        r for r in analysis_result.results
        if r.system_name != RP_SYSTEM_NAME and r.final_ranking
    ]
    if not other_results:
        return _make_summary(
            "consistent",
            "No other voting systems available for comparison.",
        )

    rp_winners = _get_winners(rp_result)
    rp_winner_name = _format_names(rp_winners)
    rp_has_tie = len(rp_winners) > 1

    # Classify each other system as agreeing or disagreeing with RP
    agreeing = []
    disagreeing = []
    for r in other_results:
        if _get_winners(r) == rp_winners:
            agreeing.append(r)
        else:
            disagreeing.append(r)

    num_disagreeing = len(disagreeing)

    # --- All agree ---
    if num_disagreeing == 0:
        if _is_dominant_winner(analysis_result, rp_winners):
            sentence = (
                f"A dominant performance \u2014 {rp_winner_name} was the "
                f"clear winner under every method."
            )
        else:
            sentence = f"All methods produced {rp_winner_name} as the winner."
        return _make_summary("consistent", sentence)

    # --- RP has tied winners with some disagreement ---
    if rp_has_tie:
        return _summarize_rp_tie(
            analysis_result, rp_winners, rp_winner_name,
            agreeing, disagreeing,
        )

    # --- Some disagreement: classify pattern ---
    # Map each unique alternative winner set to the system names that picked it
    disagreeing_winner_map: dict[frozenset[str], list[str]] = {}
    for r in disagreeing:
        winners = _get_winners(r)
        disagreeing_winner_map.setdefault(winners, []).append(r.system_name)

    unique_alt_sets = list(disagreeing_winner_map.keys())
    all_same_alt = len(unique_alt_sets) == 1

    # Determine level
    if num_disagreeing == len(other_results) and all_same_alt:
        level = "shakeup"
    elif all_same_alt:
        level = "close_call"
    else:
        level = "drama"

    # Generate sentence
    if level == "shakeup":
        alt_winners = unique_alt_sets[0]
        alt_winner_name = _format_names(alt_winners)
        sentence = _shakeup_sentence(
            analysis_result, rp_winner_name, alt_winner_name,
            rp_winners, alt_winners,
        )
    elif level == "close_call":
        alt_winners = unique_alt_sets[0]
        alt_winner_name = _format_names(alt_winners)
        sentence = _close_call_sentence(
            rp_winner_name, alt_winner_name, agreeing, disagreeing,
        )
    else:
        sentence = _drama_sentence(
            rp_winner_name, disagreeing_winner_map, agreeing,
        )

    return _make_summary(level, sentence)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_summary(level: str, sentence: str) -> dict:
    return {"level": level, "label": LABELS[level], "sentence": sentence}


def _find_rp_result(analysis_result: AnalysisResult) -> VotingResult | None:
    for r in analysis_result.results:
        if r.system_name == RP_SYSTEM_NAME:
            return r
    return None


def _get_winners(result: VotingResult) -> frozenset[str]:
    """Get the set of rank-1 competitors from a voting result."""
    return frozenset(p.name for p in result.final_ranking if p.rank == 1)


def _format_names(names: frozenset[str] | set[str]) -> str:
    """Format a set of competitor names for use in a sentence."""
    sorted_names = sorted(names)
    if len(sorted_names) == 1:
        return sorted_names[0]
    elif len(sorted_names) == 2:
        return f"{sorted_names[0]} and {sorted_names[1]}"
    else:
        return ", ".join(sorted_names[:-1]) + f", and {sorted_names[-1]}"


def _ordinal(n: int) -> str:
    """Return the ordinal string for an integer (1 -> '1st', 2 -> '2nd', etc.)."""
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    suffixes = {1: "st", 2: "nd", 3: "rd"}
    return f"{n}{suffixes.get(n % 10, 'th')}"


def _number_word(n: int) -> str:
    words = {2: "two", 3: "three", 4: "four"}
    return words.get(n, str(n))


def _is_dominant_winner(
    analysis_result: AnalysisResult, winners: frozenset[str],
) -> bool:
    """Check if the winner was ranked 1st by more than half the judges."""
    if len(winners) != 1:
        return False
    winner = next(iter(winners))
    placements = analysis_result.scoresheet.get_competitor_placements(winner)
    num_first = sum(1 for p in placements if p == 1)
    return num_first > len(placements) / 2


def _detect_polariser(
    analysis_result: AnalysisResult, candidates: frozenset[str] | set[str],
) -> dict | None:
    """Check if any of the given competitors are polarisers.

    A competitor is a polariser if their judge rankings have stdev > 4.0
    or a spread (max - min) greater than 60% of the field size.

    Returns info about the most polarising competitor, or None.
    """
    scoresheet = analysis_result.scoresheet
    n = scoresheet.num_competitors
    spread_threshold = 0.6 * n

    polarisers = []
    for name in candidates:
        placements = scoresheet.get_competitor_placements(name)
        if len(placements) < 2:
            continue
        stdev = statistics.stdev(placements)
        spread = max(placements) - min(placements)
        if stdev > 4.0 or spread > spread_threshold:
            polarisers.append({
                "name": name,
                "stdev": stdev,
                "spread": spread,
                "best": min(placements),
                "worst": max(placements),
            })

    if not polarisers:
        return None
    # Return the most polarising (highest stdev)
    return max(polarisers, key=lambda p: p["stdev"])


def _detect_one_short_majority(
    analysis_result: AnalysisResult, candidates: frozenset[str],
) -> dict | None:
    """Check if any candidate has exactly one fewer 1st-place vote than majority.

    This catches the case where a competitor wins every other system but loses
    RP because they fell one first-place vote short of the majority threshold.

    Returns info about the first such competitor found, or None.
    """
    scoresheet = analysis_result.scoresheet
    n = scoresheet.num_judges
    majority = n // 2 + 1
    one_short = majority - 1

    if one_short < 2:  # not meaningful with very small panels
        return None

    for name in candidates:
        placements = scoresheet.get_competitor_placements(name)
        num_first = sum(1 for p in placements if p == 1)
        if num_first == one_short:
            return {"name": name, "num_first": num_first, "majority": majority, "total": n}

    return None


# ---------------------------------------------------------------------------
# Sentence generators
# ---------------------------------------------------------------------------

def _shakeup_sentence(
    analysis_result: AnalysisResult,
    rp_winner_name: str,
    alt_winner_name: str,
    rp_winners: frozenset[str],
    alt_winners: frozenset[str],
) -> str:
    """Sentence for shakeup: every other method picks a different winner."""
    # Check if the RP winner is a polariser
    rp_polariser = _detect_polariser(analysis_result, rp_winners)
    if rp_polariser:
        best = _ordinal(rp_polariser["best"])
        worst = _ordinal(rp_polariser["worst"])
        return (
            f"{rp_winner_name} won under relative placement, but their "
            f"polarising scores \u2014 ranked as high as {best} but as low "
            f"as {worst} \u2014 meant every other method produced "
            f"{alt_winner_name} as the winner instead."
        )

    # Check if the alternative winner is a polariser
    alt_polariser = _detect_polariser(analysis_result, alt_winners)
    if alt_polariser:
        best = _ordinal(alt_polariser["best"])
        worst = _ordinal(alt_polariser["worst"])
        return (
            f"{alt_winner_name} had polarising scores \u2014 ranked as high "
            f"as {best} but as low as {worst} \u2014 yet won under every "
            f"method except relative placement, which produced "
            f"{rp_winner_name} instead."
        )

    # Check if the alternative winner fell one first-place vote short of majority
    one_short = _detect_one_short_majority(analysis_result, alt_winners)
    if one_short:
        num_first = one_short["num_first"]
        majority = one_short["majority"]
        total = one_short["total"]
        return (
            f"{alt_winner_name} had {num_first} of {total} first-place votes "
            f"\u2014 one short of the majority of {majority} needed to win "
            f"under relative placement \u2014 allowing {rp_winner_name} to "
            f"prevail instead. Every other method produced {alt_winner_name} "
            f"as the winner."
        )

    # Default shakeup sentence
    return (
        f"Under relative placement {rp_winner_name} won, but every other "
        f"method produced {alt_winner_name} as the winner instead."
    )


def _close_call_sentence(
    rp_winner_name: str,
    alt_winner_name: str,
    agreeing: list[VotingResult],
    disagreeing: list[VotingResult],
) -> str:
    """Sentence for close_call: 1 or 2 other systems disagree."""
    if len(disagreeing) == 1:
        method_name = disagreeing[0].system_name
        return (
            f"{rp_winner_name} won under most methods, but {method_name} "
            f"produced {alt_winner_name} as the winner instead."
        )
    else:
        # 2-2 split: RP + one agree vs two disagree
        disagreeing_names = " and ".join(r.system_name for r in disagreeing)
        if agreeing:
            agreeing_name = " and ".join(r.system_name for r in agreeing)
            return (
                f"Relative placement and {agreeing_name} produced "
                f"{rp_winner_name} as the winner, but {disagreeing_names} "
                f"produced {alt_winner_name} instead."
            )
        else:
            return (
                f"{rp_winner_name} won under relative placement, but "
                f"{disagreeing_names} produced {alt_winner_name} instead."
            )


def _drama_sentence(
    rp_winner_name: str,
    disagreeing_winner_map: dict[frozenset[str], list[str]],
    agreeing: list[VotingResult],
) -> str:
    """Sentence for drama: multiple different winners across systems."""
    total_winners = 1 + len(disagreeing_winner_map)

    # Build the RP part, including any systems that agree with RP
    if agreeing:
        rp_methods = (
            "relative placement and "
            + " and ".join(r.system_name for r in agreeing)
        )
    else:
        rp_methods = "relative placement"

    parts = [f"{rp_methods} produced {rp_winner_name}"]
    for winners, system_names in disagreeing_winner_map.items():
        winner_name = _format_names(winners)
        methods = " and ".join(system_names)
        parts.append(f"{methods} produced {winner_name}")

    if len(parts) == 2:
        parts_text = f"{parts[0]}, and {parts[1]}"
    else:
        parts_text = ", ".join(parts[:-1]) + f", and {parts[-1]}"

    return (
        f"No consensus \u2014 the methods split "
        f"{_number_word(total_winners)} ways: {parts_text}."
    )


def _summarize_rp_tie(
    analysis_result: AnalysisResult,
    rp_winners: frozenset[str],
    rp_winner_name: str,
    agreeing: list[VotingResult],
    disagreeing: list[VotingResult],
) -> dict:
    """Handle the case where RP has tied winners."""
    if not disagreeing:
        sentence = (
            f"Relative placement couldn't separate {rp_winner_name}, "
            f"and the other methods agreed on the tie."
        )
        return _make_summary("close_call", sentence)

    # Check if all disagreeing systems agree on a single alternative
    disagreeing_winner_sets = [_get_winners(r) for r in disagreeing]
    unique_sets = list(dict.fromkeys(disagreeing_winner_sets))

    if len(unique_sets) == 1 and len(unique_sets[0]) == 1:
        alt_winner = _format_names(unique_sets[0])
        sentence = (
            f"Relative placement couldn't separate {rp_winner_name}, "
            f"but the other methods broke the tie in favour of {alt_winner}."
        )
    else:
        sentence = (
            f"Relative placement couldn't separate {rp_winner_name}, "
            f"and the other methods were equally divided."
        )
    return _make_summary("close_call", sentence)
