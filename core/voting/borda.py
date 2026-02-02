"""Borda count voting system."""

from core.models import Scoresheet, VotingResult
from core.voting import register_voting_system
from core.voting.base import VotingSystem


@register_voting_system
class BordaCountSystem(VotingSystem):
    """Borda count voting system.

    Each rank position awards points:
    - 1st place = n-1 points
    - 2nd place = n-2 points
    - ...
    - Last place = 0 points

    Where n is the number of competitors. Points are summed across all judges.

    Tiebreakers (applied in order):
    1. Head-to-head comparison among tied competitors
    2. Most first-place votes
    3. Best (lowest) single placement from any judge
    """

    @property
    def name(self) -> str:
        return "Borda Count"

    @property
    def description(self) -> str:
        return "Points-based system: 1st = n-1 pts, 2nd = n-2 pts, ..., last = 0 pts"

    def calculate(self, scoresheet: Scoresheet) -> VotingResult:
        n = scoresheet.num_competitors

        # Calculate Borda scores
        scores: dict[str, int] = {}
        breakdowns: dict[str, list[int]] = {}

        for competitor in scoresheet.competitors:
            points_per_judge = []
            total = 0
            for judge in scoresheet.judges:
                placement = scoresheet.get_placement(judge, competitor)
                points = n - placement  # 1st = n-1, last = 0
                points_per_judge.append(points)
                total += points
            scores[competitor] = total
            breakdowns[competitor] = points_per_judge

        # Group by score
        score_groups: dict[int, list[str]] = {}
        for competitor, score in scores.items():
            if score not in score_groups:
                score_groups[score] = []
            score_groups[score].append(competitor)

        # Build final ranking with tiebreaking
        final_ranking = []
        tiebreaker_info = []

        for score in sorted(score_groups.keys(), reverse=True):
            group = score_groups[score]

            if len(group) == 1:
                final_ranking.append(group[0])
            else:
                # Apply tiebreakers
                resolved, info = self._break_ties(group, scoresheet)
                final_ranking.extend(resolved)
                if info:
                    tiebreaker_info.append({
                        "tied_competitors": group,
                        "score": score,
                        "resolution": info,
                    })

        return VotingResult(
            system_name=self.name,
            final_ranking=final_ranking,
            details={
                "scores": scores,
                "breakdowns": {c: {"judges": scoresheet.judges, "points": breakdowns[c]}
                              for c in scoresheet.competitors},
                "max_possible": (n - 1) * scoresheet.num_judges,
                "tiebreakers": tiebreaker_info,
            },
        )

    def _break_ties(
        self, tied: list[str], scoresheet: Scoresheet
    ) -> tuple[list[str], dict | None]:
        """Break ties among competitors with the same Borda score.

        Returns (ordered list, tiebreaker info dict or None if no tiebreaker needed).
        """
        if len(tied) <= 1:
            return tied, None

        info = {"method": None, "details": {}}

        # Tiebreaker 1: Head-to-head among tied
        h2h_wins = {c: 0 for c in tied}
        for i, a in enumerate(tied):
            for b in tied[i + 1:]:
                a_wins = sum(
                    1 for j in scoresheet.judges
                    if scoresheet.get_placement(j, a) < scoresheet.get_placement(j, b)
                )
                if a_wins > scoresheet.num_judges / 2:
                    h2h_wins[a] += 1
                elif a_wins < scoresheet.num_judges / 2:
                    h2h_wins[b] += 1

        max_wins = max(h2h_wins.values())
        best_h2h = [c for c in tied if h2h_wins[c] == max_wins]

        if len(best_h2h) == 1:
            # H2H resolved it, but we still need to order the rest
            info["method"] = "head-to-head"
            info["details"] = {"wins": h2h_wins}
            remaining = [c for c in tied if c != best_h2h[0]]
            rest, _ = self._break_ties(remaining, scoresheet)
            return [best_h2h[0]] + rest, info

        # Continue with remaining tiebreakers on best_h2h subset
        tied = best_h2h

        # Tiebreaker 2: Most first-place votes
        first_counts = {c: 0 for c in tied}
        for judge in scoresheet.judges:
            ranking = scoresheet.get_judge_ranking(judge)
            if ranking[0] in first_counts:
                first_counts[ranking[0]] += 1

        max_firsts = max(first_counts.values())
        best_firsts = [c for c in tied if first_counts[c] == max_firsts]

        if len(best_firsts) == 1:
            info["method"] = "most-first-place-votes"
            info["details"] = {"first_place_counts": first_counts}
            remaining = [c for c in tied if c != best_firsts[0]]
            rest, _ = self._break_ties(remaining, scoresheet)
            return [best_firsts[0]] + rest, info

        tied = best_firsts

        # Tiebreaker 3: Best single placement
        best_placements = {
            c: min(scoresheet.get_placement(j, c) for j in scoresheet.judges)
            for c in tied
        }
        min_placement = min(best_placements.values())
        best_single = [c for c in tied if best_placements[c] == min_placement]

        if len(best_single) == 1:
            info["method"] = "best-single-placement"
            info["details"] = {"best_placements": best_placements}
            remaining = [c for c in tied if c != best_single[0]]
            rest, _ = self._break_ties(remaining, scoresheet)
            return [best_single[0]] + rest, info

        # Still tied - return in original order (or could randomize)
        info["method"] = "unresolved"
        info["details"] = {"remaining_tied": tied}
        return tied, info
