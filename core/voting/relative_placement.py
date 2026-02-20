"""Relative Placement voting system (WCS Standard)."""

from core.models import Placement, Scoresheet, VotingResult
from core.voting import register_voting_system
from core.voting.base import VotingSystem


@register_voting_system
class RelativePlacementSystem(VotingSystem):
    """Relative Placement voting system (also known as the Skating System).

    This is the official voting system used in West Coast Swing competitions.

    A competitor earns a placement when a majority of judges rank them at that
    place or better. When multiple competitors have a majority at the same
    cutoff, tiebreakers are applied.

    Tiebreakers (applied in order):
    1. Greater majority: more judges at cutoff or better
    2. Quality of majority: sum of placements from the majority judges (lower wins)
    3. Head-to-head comparison
    """

    @property
    def name(self) -> str:
        return "Relative Placement"

    @property
    def description(self) -> str:
        return "WCS standard: place when majority of judges rank you at that place or better"

    def calculate(self, scoresheet: Scoresheet) -> VotingResult:
        n = scoresheet.num_competitors
        m = scoresheet.num_judges
        majority = m // 2 + 1

        # Precompute cumulative placement counts for each competitor
        # cum_counts[competitor][place] = # of judges ranking at place or better
        cum_counts = self._compute_cumulative_counts(scoresheet)

        final_ranking: list[str | list[str]] = []
        unplaced = set(scoresheet.competitors)
        round_details = []

        # Process cutoffs methodically: at each cutoff, resolve ALL competitors
        # that have a majority before advancing. This ensures that a tiebreak
        # loser (who already has majority at this cutoff) is placed before any
        # new competitors who only gain majority at a higher cutoff.
        current_cutoff = 1

        while unplaced and current_cutoff <= n:
            # Find all unplaced competitors with majority at this cutoff,
            # preserving the original competitor order for determinism
            with_majority = [
                c for c in scoresheet.competitors
                if c in unplaced and cum_counts[c][current_cutoff] >= majority
            ]

            if not with_majority:
                current_cutoff += 1
                continue

            # Place all competitors with majority at this cutoff
            while with_majority:
                target_place = sum(
                    len(e) if isinstance(e, list) else 1
                    for e in final_ranking
                ) + 1

                round_info = {
                    "target_place": target_place,
                    "candidates": list(with_majority),
                    "majority_needed": majority,
                }

                if len(with_majority) == 1:
                    winner = with_majority[0]
                    round_info["winner"] = winner
                    round_info["tied"] = False
                    round_info["resolution"] = {
                        "method": "majority",
                        "final_cutoff": current_cutoff,
                        "cutoff_progression": [{
                            "cutoff": current_cutoff,
                            "counts": {
                                winner: cum_counts[winner][current_cutoff],
                            },
                            "with_majority": [winner],
                            "result": "single_majority",
                        }],
                    }
                    final_ranking.append(winner)
                    unplaced.discard(winner)
                    with_majority = []
                else:
                    winner, details = self._resolve_placement(
                        list(with_majority), current_cutoff, majority,
                        cum_counts, scoresheet,
                    )
                    round_info["resolution"] = details

                    if isinstance(winner, list):
                        # Unresolved tie
                        round_info["winners"] = winner
                        round_info["tied"] = True
                        final_ranking.append(list(winner))
                        placed = set(winner)
                        for w in winner:
                            unplaced.discard(w)
                        with_majority = [
                            c for c in with_majority if c not in placed
                        ]
                    else:
                        round_info["winner"] = winner
                        round_info["tied"] = False
                        final_ranking.append(winner)
                        unplaced.discard(winner)
                        with_majority.remove(winner)

                round_details.append(round_info)

            current_cutoff += 1

        return VotingResult(
            system_name=self.name,
            final_ranking=Placement.build_ranking(final_ranking),
            details={
                "majority_threshold": majority,
                "cumulative_counts": {
                    c: cum_counts[c] for c in scoresheet.competitors
                },
                "rounds": round_details,
            },
        )

    def _compute_cumulative_counts(
        self, scoresheet: Scoresheet
    ) -> dict[str, list[int]]:
        """Compute cumulative placement counts for each competitor.

        Returns dict mapping competitor -> list where list[i] is the count of
        judges who ranked this competitor at place i or better (1-indexed).
        """
        n = scoresheet.num_competitors
        cum_counts = {}

        for competitor in scoresheet.competitors:
            # counts[i] = number of judges ranking at exactly place i
            counts = [0] * (n + 1)  # 1-indexed
            for judge in scoresheet.judges:
                placement = scoresheet.get_placement(judge, competitor)
                counts[placement] += 1

            # Convert to cumulative: cum[i] = judges at place i or better
            cumulative = [0] * (n + 1)
            running_total = 0
            for i in range(1, n + 1):
                running_total += counts[i]
                cumulative[i] = running_total

            cum_counts[competitor] = cumulative

        return cum_counts

    def _resolve_placement(
        self,
        candidates: list[str],
        start_cutoff: int,
        majority: int,
        cum_counts: dict[str, list[int]],
        scoresheet: Scoresheet,
    ) -> tuple[str | list[str], dict]:
        """Resolve who wins a placement among candidates.

        Applies tiebreakers starting at start_cutoff and advancing if needed.
        Returns (winner, details) where winner may be a list if truly tied.
        """
        n = scoresheet.num_competitors
        current_cutoff = start_cutoff
        details = {"cutoff_progression": []}

        while len(candidates) > 1 and current_cutoff <= n:
            cutoff_info = {
                "cutoff": current_cutoff,
                "counts": {c: cum_counts[c][current_cutoff] for c in candidates},
            }

            # Find candidates with majority at this cutoff
            with_majority = [
                c for c in candidates
                if cum_counts[c][current_cutoff] >= majority
            ]

            cutoff_info["with_majority"] = with_majority

            if len(with_majority) == 0:
                # No one has majority yet, extend cutoff
                cutoff_info["result"] = "no_majority"
                details["cutoff_progression"].append(cutoff_info)
                current_cutoff += 1
                continue

            if len(with_majority) == 1:
                # Clear winner
                cutoff_info["result"] = "single_majority"
                details["cutoff_progression"].append(cutoff_info)
                details["method"] = "majority"
                details["final_cutoff"] = current_cutoff
                return with_majority[0], details

            # Multiple have majority - apply tiebreakers
            candidates = with_majority
            cutoff_info["result"] = "multiple_majority"

            # Tiebreaker 1: Greater majority (most judges at cutoff or better)
            max_count = max(cum_counts[c][current_cutoff] for c in candidates)
            best_count = [
                c for c in candidates
                if cum_counts[c][current_cutoff] == max_count
            ]

            if len(best_count) == 1:
                cutoff_info["tiebreaker"] = "greater_majority"
                details["cutoff_progression"].append(cutoff_info)
                details["method"] = "greater_majority"
                details["final_cutoff"] = current_cutoff
                return best_count[0], details

            candidates = best_count

            # Tiebreaker 2: Quality of majority (sum of best placements)
            quality = {}
            for c in candidates:
                placements = [scoresheet.get_placement(j, c) for j in scoresheet.judges]
                # Sum the placements that are part of the current majority
                quality[c] = sum(p for p in placements if p <= current_cutoff)

            min_quality = min(quality.values())
            best_quality = [c for c in candidates if quality[c] == min_quality]

            cutoff_info["quality_scores"] = quality

            if len(best_quality) == 1:
                cutoff_info["tiebreaker"] = "quality_of_majority"
                details["cutoff_progression"].append(cutoff_info)
                details["method"] = "quality_of_majority"
                details["final_cutoff"] = current_cutoff
                return best_quality[0], details

            candidates = best_quality
            details["cutoff_progression"].append(cutoff_info)
            current_cutoff += 1

        # Final fallback: head-to-head for exactly 2 candidates only
        if len(candidates) > 1:
            if len(candidates) == 2:
                winner, h2h_counts = self._head_to_head_tiebreak(candidates, scoresheet)
                details["method"] = "head_to_head"
                details["h2h_pair"] = candidates
                details["h2h_counts"] = h2h_counts
                if winner:
                    return winner, details
                else:
                    return candidates, details
            else:
                details["method"] = "unresolved_tie"
                return candidates, details

        details["method"] = "last_remaining"
        return candidates[0] if candidates else [], details

    def _head_to_head_tiebreak(
        self, candidates: list[str], scoresheet: Scoresheet
    ) -> tuple[str | None, dict]:
        """Compare two tied competitors head-to-head.

        Returns (winner, counts) where counts is {A: n_A, B: n_B} and
        winner is the competitor preferred by more judges, or None if tied.
        Only valid for exactly 2 candidates.
        """
        assert len(candidates) == 2
        a, b = candidates
        a_better = sum(
            1 for j in scoresheet.judges
            if scoresheet.get_placement(j, a) < scoresheet.get_placement(j, b)
        )
        b_better = scoresheet.num_judges - a_better
        counts = {a: a_better, b: b_better}
        if a_better > b_better:
            return a, counts
        elif b_better > a_better:
            return b, counts
        else:
            return None, counts
