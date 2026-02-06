"""Tests for Schulze method voting system."""

from tests.conftest import make_scoresheet
from core.voting.schulze import SchulzeSystem


class TestSchulze:
    def setup_method(self):
        self.system = SchulzeSystem()

    def test_name(self):
        assert self.system.name == "Schulze Method"

    def test_clear_winner(self, clear_winner):
        """Dataset 1: A beats all, B beats C and D, C beats D → A, B, C, D."""
        result = self.system.calculate(clear_winner)
        assert result.final_ranking == ["A", "B", "C", "D"]

    def test_clear_winner_schulze_wins(self, clear_winner):
        """Verify Schulze win counts."""
        result = self.system.calculate(clear_winner)
        wins = result.details["schulze_wins"]
        assert wins["A"] == 3
        assert wins["B"] == 2
        assert wins["C"] == 1
        assert wins["D"] == 0

    def test_disagreement(self, disagreement):
        """Dataset 2: A beats all 3-2, B beats C(4-1) and D(3-2), C beats D(3-2)."""
        result = self.system.calculate(disagreement)
        assert result.final_ranking == ["A", "B", "C", "D"]

    def test_disagreement_pairwise(self, disagreement):
        """Verify pairwise preference counts for dataset 2."""
        result = self.system.calculate(disagreement)
        prefs = result.details["pairwise_preferences"]
        # A vs B: 3 judges prefer A (J1, J3, J4)
        assert prefs["A"]["B"] == 3
        assert prefs["B"]["A"] == 2
        # B vs C: 4 judges prefer B (J1, J2, J4, J5)
        assert prefs["B"]["C"] == 4
        assert prefs["C"]["B"] == 1

    def test_unanimous(self, unanimous):
        result = self.system.calculate(unanimous)
        assert result.final_ranking == ["A", "B", "C"]

    def test_two_competitors(self, two_competitors):
        result = self.system.calculate(two_competitors)
        assert result.final_ranking == ["A", "B"]

    def test_perfect_cycle(self, perfect_cycle):
        """All pairwise matchups are 2-1. All path strengths equal.

        All Schulze wins should be 0 (no one definitively beats anyone).
        """
        result = self.system.calculate(perfect_cycle)
        assert len(result.final_ranking) == 3
        assert set(result.final_ranking) == {"A", "B", "C"}

        wins = result.details["schulze_wins"]
        # In a perfect cycle, after Floyd-Warshall, all path strengths
        # should be equal (2), so no one beats anyone → all wins = 0
        assert all(w == 0 for w in wins.values())

    def test_condorcet_winner(self):
        """A beats everyone pairwise — should always be 1st.

             J1  J2  J3
        A     1   1   1
        B     2   3   2
        C     3   2   3
        """
        scoresheet = make_scoresheet("Condorcet", {
            "J1": {"A": 1, "B": 2, "C": 3},
            "J2": {"A": 1, "B": 3, "C": 2},
            "J3": {"A": 1, "B": 2, "C": 3},
        })
        result = self.system.calculate(scoresheet)
        assert result.final_ranking[0] == "A"
        assert result.details["schulze_wins"]["A"] == 2

    def test_details_has_expected_keys(self, clear_winner):
        result = self.system.calculate(clear_winner)
        assert "pairwise_preferences" in result.details
        assert "path_strengths" in result.details
        assert "schulze_wins" in result.details
        assert "ties" in result.details

    # --- path_strengths tests ---

    def test_clear_winner_path_strengths(self, clear_winner):
        """No cycles: path strengths equal direct defeat strengths.

        Pairwise: A>B(2-1), A>C(3-0), A>D(3-0), B>C(2-1), B>D(3-0), C>D(3-0).
        No indirect path can improve on any direct defeat.
        """
        result = self.system.calculate(clear_winner)
        p = result.details["path_strengths"]
        # A beats everyone directly
        assert p["A"]["B"] == 2
        assert p["A"]["C"] == 3
        assert p["A"]["D"] == 3
        # B beats C and D directly
        assert p["B"]["C"] == 2
        assert p["B"]["D"] == 3
        # C beats D directly
        assert p["C"]["D"] == 3
        # No reverse paths (no cycles)
        assert p["B"]["A"] == 0
        assert p["C"]["A"] == 0
        assert p["C"]["B"] == 0
        assert p["D"]["A"] == 0
        assert p["D"]["B"] == 0
        assert p["D"]["C"] == 0

    def test_disagreement_path_strengths(self, disagreement):
        """No cycles: A>B(3-2), A>C(3-2), A>D(3-2), B>C(4-1), B>D(3-2), C>D(3-2).

        B→C has the strongest single defeat (4). No indirect paths improve anything.
        """
        result = self.system.calculate(disagreement)
        p = result.details["path_strengths"]
        assert p["A"]["B"] == 3
        assert p["A"]["C"] == 3
        assert p["A"]["D"] == 3
        assert p["B"]["C"] == 4
        assert p["B"]["D"] == 3
        assert p["C"]["D"] == 3
        # No reverse paths
        assert p["B"]["A"] == 0
        assert p["C"]["A"] == 0
        assert p["C"]["B"] == 0
        assert p["D"]["A"] == 0
        assert p["D"]["B"] == 0
        assert p["D"]["C"] == 0

    def test_perfect_cycle_path_strengths(self, perfect_cycle):
        """Cycle A>B(2-1), B>C(2-1), C>A(2-1). Floyd-Warshall propagates.

        After Floyd-Warshall, all off-diagonal path strengths become 2:
        - p[B][A] starts at 0 but reaches 2 via B→C→A
        - p[C][B] starts at 0 but reaches 2 via C→A→B
        - p[A][C] starts at 0 but reaches 2 via A→B→C
        """
        result = self.system.calculate(perfect_cycle)
        p = result.details["path_strengths"]
        for source in ["A", "B", "C"]:
            for target in ["A", "B", "C"]:
                if source == target:
                    assert p[source][target] == 0
                else:
                    assert p[source][target] == 2, (
                        f"p[{source}][{target}] should be 2, got {p[source][target]}"
                    )

    def test_unanimous_path_strengths(self, unanimous):
        """All 3 judges agree: A=1, B=2, C=3.

        All defeats are 3-0 with no cycles.
        """
        result = self.system.calculate(unanimous)
        p = result.details["path_strengths"]
        assert p["A"]["B"] == 3
        assert p["A"]["C"] == 3
        assert p["B"]["C"] == 3
        assert p["B"]["A"] == 0
        assert p["C"]["A"] == 0
        assert p["C"]["B"] == 0

    def test_two_competitors_path_strengths(self, two_competitors):
        """A beats B 2-1. Simplest possible case."""
        result = self.system.calculate(two_competitors)
        p = result.details["path_strengths"]
        assert p["A"]["B"] == 2
        assert p["B"]["A"] == 0

    def test_indirect_path_beats_direct_defeat(self):
        """Indirect paths through a cycle produce stronger paths than direct defeats.

        9 judges, 3 competitors. Cycle: A>B(5-4), B>C(6-3), C>A(6-3).

                 J1  J2  J3  J4  J5  J6  J7  J8  J9
            A     1   1   2   3   3   3   2   2   2
            B     2   2   1   1   1   1   3   3   3
            C     3   3   3   2   2   2   1   1   1

        Direct defeats: p[A][B]=5, p[B][C]=6, p[C][A]=6.
        After Floyd-Warshall, indirect paths fill in:
        - p[B][A]=6 via B→C→A (min(6,6)=6) — B doesn't beat A directly!
        - p[A][C]=5 via A→B→C (min(5,6)=5) — A doesn't beat C directly!
        - p[C][B]=5 via C→A→B (min(6,5)=5) — C doesn't beat B directly!
        Result: B wins (2 wins), then C (1 win), then A (0 wins).
        """
        scoresheet = make_scoresheet("Indirect Paths", {
            # 2× ABC
            "J1": {"A": 1, "B": 2, "C": 3},
            "J2": {"A": 1, "B": 2, "C": 3},
            # 1× BAC
            "J3": {"A": 2, "B": 1, "C": 3},
            # 3× BCA
            "J4": {"A": 3, "B": 1, "C": 2},
            "J5": {"A": 3, "B": 1, "C": 2},
            "J6": {"A": 3, "B": 1, "C": 2},
            # 3× CAB
            "J7": {"A": 2, "B": 3, "C": 1},
            "J8": {"A": 2, "B": 3, "C": 1},
            "J9": {"A": 2, "B": 3, "C": 1},
        })
        result = self.system.calculate(scoresheet)
        p = result.details["path_strengths"]

        # Direct defeats only
        assert p["A"]["B"] == 5  # direct: 5 judges prefer A over B
        assert p["B"]["C"] == 6  # direct: 6 judges prefer B over C
        assert p["C"]["A"] == 6  # direct: 6 judges prefer C over A

        # Indirect paths (Floyd-Warshall computed)
        assert p["B"]["A"] == 6  # via B→C→A: min(6, 6) = 6
        assert p["A"]["C"] == 5  # via A→B→C: min(5, 6) = 5
        assert p["C"]["B"] == 5  # via C→A→B: min(6, 5) = 5

        # Ranking: B (2 wins), C (1 win), A (0 wins)
        assert result.final_ranking == ["B", "C", "A"]

    def test_path_strengths_diagonal_is_zero(self, clear_winner, disagreement,
                                             unanimous, two_competitors,
                                             perfect_cycle):
        """Self-comparison path strengths must always be zero."""
        for scoresheet in [clear_winner, disagreement, unanimous,
                           two_competitors, perfect_cycle]:
            result = self.system.calculate(scoresheet)
            p = result.details["path_strengths"]
            for comp in p:
                assert p[comp][comp] == 0, (
                    f"p[{comp}][{comp}] should be 0 in {scoresheet.name}"
                )
