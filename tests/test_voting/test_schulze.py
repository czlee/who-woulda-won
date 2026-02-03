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
