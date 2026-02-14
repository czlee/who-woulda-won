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

    Tiebreaker: Recursively apply Borda count among only the tied competitors
    using their relative rankings. For each judge, the tied competitors are
    re-ranked by their relative positions and awarded points accordingly. If all
    competitors still tie after re-ranking, the tie is declared unresolved.
    """

    @property
    def name(self) -> str:
        return "Borda Count"

    @property
    def description(self) -> str:
        return "Points-based system: 1st = n-1 pts, 2nd = n-2 pts, ..., last = 0 pts"

    @staticmethod
    def _compute_borda_scores(
        competitors: list[str], scoresheet: Scoresheet
    ) -> tuple[dict[str, int], dict[str, list[int]]]:
        """Compute Borda scores for a subset of competitors using relative rankings.

        For each judge, the given competitors are ranked by their relative
        positions (preserving the judge's original ordering among them) and
        awarded (k-1) points for 1st, (k-2) for 2nd, ..., 0 for last, where
        k is the number of competitors in the subset.

        Returns (scores dict, breakdowns dict mapping competitor -> per-judge points).
        """
        k = len(competitors)
        scores: dict[str, int] = {c: 0 for c in competitors}
        breakdowns: dict[str, list[int]] = {c: [] for c in competitors}

        for judge in scoresheet.judges:
            # Sort competitors by this judge's placement (relative ranking)
            ranked = sorted(competitors, key=lambda c: scoresheet.get_placement(judge, c))
            for position, competitor in enumerate(ranked):
                points = k - 1 - position  # 1st = k-1, last = 0
                scores[competitor] += points
                breakdowns[competitor].append(points)

        return scores, breakdowns

    def calculate(self, scoresheet: Scoresheet) -> VotingResult:
        scores, breakdowns = self._compute_borda_scores(
            scoresheet.competitors, scoresheet
        )

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
                "max_possible": (scoresheet.num_competitors - 1) * scoresheet.num_judges,
                "tiebreakers": tiebreaker_info,
            },
        )

    def _break_ties(
        self, tied: list[str], scoresheet: Scoresheet
    ) -> tuple[list[str], dict | None]:
        """Break ties among competitors with the same Borda score.

        Recursively applies relative Borda count among the tied competitors.
        Returns (ordered list, tiebreaker info dict or None if no tiebreaker needed).
        """
        if len(tied) <= 1:
            return tied, None

        # Compute relative Borda scores among only the tied competitors
        relative_scores, _ = self._compute_borda_scores(tied, scoresheet)

        # Group by relative score
        score_groups: dict[int, list[str]] = {}
        for competitor, score in relative_scores.items():
            if score not in score_groups:
                score_groups[score] = []
            score_groups[score].append(competitor)

        # Check if we made progress (more than one group)
        if len(score_groups) == 1:
            # All competitors still have the same relative score — unresolved
            return tied, {"method": "unresolved", "details": {"remaining_tied": tied}}

        info = {"method": "recursive-borda", "details": {"relative_scores": relative_scores}}

        # Order groups by score (highest first) and recurse on still-tied groups
        result = []
        for score in sorted(score_groups.keys(), reverse=True):
            group = score_groups[score]
            if len(group) == 1:
                result.append(group[0])
            else:
                resolved, _ = self._break_ties(group, scoresheet)
                result.extend(resolved)

        return result, info
