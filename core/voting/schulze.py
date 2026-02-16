"""Schulze method voting system."""

from core.models import Placement, Scoresheet, VotingResult
from core.voting import register_voting_system
from core.voting.base import VotingSystem


def _sub_sort(group: list[str], metric: dict[str, int | float]) -> list[list[str]]:
    """Sort a tie group by a metric, returning sub-groups (preserving ties)."""
    group_sorted = sorted(group, key=lambda c: metric[c], reverse=True)
    sub_groups: list[list[str]] = []
    i = 0
    while i < len(group_sorted):
        sg = [group_sorted[i]]
        j = i + 1
        while j < len(group_sorted) and metric[group_sorted[j]] == metric[group_sorted[i]]:
            sg.append(group_sorted[j])
            j += 1
        sub_groups.append(sg)
        i = j
    return sub_groups


@register_voting_system
class SchulzeSystem(VotingSystem):
    """Schulze method voting system.

    A Condorcet method that uses "beatpath" strengths to determine rankings.
    It handles cyclic preferences gracefully by finding the strongest path
    between each pair of candidates.

    Algorithm:
    1. Build pairwise preference matrix: d[A][B] = judges preferring A over B
    2. Calculate strongest path strengths using Floyd-Warshall variant
    3. A beats B (in Schulze sense) if path strength A→B > path strength B→A
    4. Rank by number of Schulze wins

    Complexity: O(n³) where n is the number of competitors.
    """

    @property
    def name(self) -> str:
        return "Schulze Method"

    @property
    def description(self) -> str:
        return "Condorcet method using beatpath strengths to handle cyclic preferences"

    def calculate(self, scoresheet: Scoresheet) -> VotingResult:
        competitors = scoresheet.competitors
        n = len(competitors)
        comp_idx = {c: i for i, c in enumerate(competitors)}

        # Step 1: Build pairwise preference matrix
        # d[i][j] = number of judges who prefer competitor i over competitor j
        d = [[0] * n for _ in range(n)]

        for judge in scoresheet.judges:
            ranking = scoresheet.get_judge_ranking(judge)
            for i, comp_a in enumerate(ranking):
                for comp_b in ranking[i + 1:]:
                    # comp_a is ranked higher (better) than comp_b
                    d[comp_idx[comp_a]][comp_idx[comp_b]] += 1

        # Step 2: Calculate strongest path strengths
        # Using "winning votes" as the strength measure
        p = [[0] * n for _ in range(n)]

        # Initialize with direct defeats
        for i in range(n):
            for j in range(n):
                if i != j:
                    if d[i][j] > d[j][i]:
                        p[i][j] = d[i][j]
                    # else p[i][j] stays 0

        # Floyd-Warshall to find strongest paths
        for k in range(n):
            for i in range(n):
                if i == k:
                    continue
                for j in range(n):
                    if j == i or j == k:
                        continue
                    # Strength of path through k is min of the two links
                    strength_via_k = min(p[i][k], p[k][j])
                    p[i][j] = max(p[i][j], strength_via_k)

        # Step 3: Count Schulze wins
        # A beats B if p[A][B] > p[B][A]
        wins = [0] * n
        for i in range(n):
            for j in range(n):
                if i != j:
                    if p[i][j] > p[j][i]:
                        wins[i] += 1
                    if p[i][j] == p[j][i]:
                        wins[i] += 0.5

        # Compute tiebreak metrics
        winning_strength = {}
        total_strength = {}
        for i in range(n):
            ws = 0
            ts = 0
            for j in range(n):
                if i != j:
                    ts += p[i][j]
                    if p[i][j] > p[j][i]:
                        ws += p[i][j]
            winning_strength[competitors[i]] = ws
            total_strength[competitors[i]] = ts

        # Create ranking by sorting by wins (descending)
        indexed_results = [(competitors[i], wins[i]) for i in range(n)]
        indexed_results.sort(key=lambda x: x[1], reverse=True)

        # Build ranking, grouping ties and applying tiebreakers
        ordered: list[str | list[str]] = []
        ties = []
        used_winning = False
        used_total = False
        i = 0
        while i < n:
            # Collect group with same win count
            j = i + 1
            while j < n and indexed_results[j][1] == indexed_results[i][1]:
                j += 1
            group = [indexed_results[k][0] for k in range(i, j)]

            if len(group) == 1:
                ordered.append(group[0])
            else:
                # Tiebreak level 1: winning beatpath strength sum
                sub_groups = _sub_sort(group, winning_strength)
                if sub_groups != [group]:
                    used_winning = True
                # Tiebreak level 2: total beatpath strength sum
                resolved: list[list[str]] = []
                for sg in sub_groups:
                    if len(sg) == 1:
                        resolved.append(sg)
                    else:
                        sub2 = _sub_sort(sg, total_strength)
                        if sub2 != [sg]:
                            used_total = True
                        resolved.extend(sub2)
                # Flatten into ordered
                for sg in resolved:
                    if len(sg) == 1:
                        ordered.append(sg[0])
                    else:
                        ordered.append(sg)
                        ties.append(sg)
            i = j

        # Determine deepest tiebreak level used
        if used_total:
            tiebreak_used = "total"
        elif used_winning:
            tiebreak_used = "winning"
        else:
            tiebreak_used = "none"

        final_ranking = Placement.build_ranking(ordered)

        # Build readable matrices for details
        pairwise_matrix = {
            competitors[i]: {
                competitors[j]: d[i][j]
                for j in range(n)
            }
            for i in range(n)
        }

        path_strengths = {
            competitors[i]: {
                competitors[j]: p[i][j]
                for j in range(n)
            }
            for i in range(n)
        }

        details: dict = {
            "pairwise_preferences": pairwise_matrix,
            "path_strengths": path_strengths,
            "schulze_wins": {competitors[i]: wins[i] for i in range(n)},
            "ties": ties,
            "tiebreak_used": tiebreak_used,
            "explanation": (
                "Each cell d[A][B] shows judges preferring A over B. "
                "Path strengths use Floyd-Warshall to find strongest "
                "indirect paths. A beats B if path A→B > path B→A. "
                "Ties (equal path strengths) count as half a win for each side."
            ),
        }

        if tiebreak_used in ("winning", "total"):
            details["winning_beatpath_sums"] = winning_strength
            details["explanation"] += (
                " Ties in win count are broken by the sum of winning "
                "beatpath strengths."
            )
        if tiebreak_used == "total":
            details["total_beatpath_sums"] = total_strength
            details["explanation"] += (
                " If still tied, the sum of all beatpath strengths is used."
            )

        return VotingResult(
            system_name=self.name,
            final_ranking=final_ranking,
            details=details,
        )
