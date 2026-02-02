"""Schulze method voting system."""

from core.models import Scoresheet, VotingResult
from core.voting import register_voting_system
from core.voting.base import VotingSystem


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
                if i != j and p[i][j] > p[j][i]:
                    wins[i] += 1

        # Create ranking by sorting by wins (descending)
        indexed_results = [(competitors[i], wins[i]) for i in range(n)]
        indexed_results.sort(key=lambda x: x[1], reverse=True)

        final_ranking = [c for c, _ in indexed_results]

        # Detect ties (same number of wins)
        ties = []
        i = 0
        while i < n:
            tie_group = [indexed_results[i][0]]
            j = i + 1
            while j < n and indexed_results[j][1] == indexed_results[i][1]:
                tie_group.append(indexed_results[j][0])
                j += 1
            if len(tie_group) > 1:
                ties.append(tie_group)
            i = j

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

        return VotingResult(
            system_name=self.name,
            final_ranking=final_ranking,
            details={
                "pairwise_preferences": pairwise_matrix,
                "path_strengths": path_strengths,
                "schulze_wins": {competitors[i]: wins[i] for i in range(n)},
                "ties": ties,
                "explanation": (
                    "Each cell d[A][B] shows judges preferring A over B. "
                    "Path strengths use Floyd-Warshall to find strongest "
                    "indirect paths. A beats B if path A→B > path B→A."
                ),
            },
        )
