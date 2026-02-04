"""Tests for Relative Placement (Skating System) voting system."""

from tests.conftest import make_scoresheet
from core.voting.relative_placement import RelativePlacementSystem


class TestRelativePlacement:
    def setup_method(self):
        self.system = RelativePlacementSystem()

    def test_name(self):
        assert self.system.name == "Relative Placement"

    def test_clear_winner(self, clear_winner):
        """Dataset 1: Clear majorities at each cutoff → A, B, C, D."""
        result = self.system.calculate(clear_winner)
        assert result.final_ranking == ["A", "B", "C", "D"]

    def test_disagreement_differs_from_others(self, disagreement):
        """Dataset 2: RP uniquely gives A, B, D, C.

        Place 3: D has greater majority at cutoff 3 (4 judges vs C's 3).
        """
        result = self.system.calculate(disagreement)
        assert result.final_ranking == ["A", "B", "D", "C"]

    def test_unanimous(self, unanimous):
        result = self.system.calculate(unanimous)
        assert result.final_ranking == ["A", "B", "C"]

    def test_two_competitors(self, two_competitors):
        result = self.system.calculate(two_competitors)
        assert result.final_ranking == ["A", "B"]

    def test_perfect_cycle(self, perfect_cycle):
        """Symmetric case — all cumulative counts identical."""
        result = self.system.calculate(perfect_cycle)
        assert len(result.final_ranking) == 3
        assert set(result.final_ranking) == {"A", "B", "C"}

    def test_majority_threshold(self, clear_winner):
        """3 judges → majority = 2."""
        result = self.system.calculate(clear_winner)
        assert result.details["majority_threshold"] == 2

    def test_majority_threshold_five_judges(self, disagreement):
        """5 judges → majority = 3."""
        result = self.system.calculate(disagreement)
        assert result.details["majority_threshold"] == 3

    def test_greater_majority_tiebreak(self):
        """Test that greater majority count breaks ties.

             J1  J2  J3  J4  J5
        A     1   1   2   3   3
        B     2   2   1   1   2
        C     3   3   3   2   1

        Place 1 at cutoff 2: A has 3 judges, B has 4 judges.
        B should win 1st via greater majority.
        """
        scoresheet = make_scoresheet("Greater Majority Test", {
            "J1": {"A": 1, "B": 2, "C": 3},
            "J2": {"A": 1, "B": 2, "C": 3},
            "J3": {"A": 2, "B": 1, "C": 3},
            "J4": {"A": 3, "B": 1, "C": 2},
            "J5": {"A": 3, "B": 2, "C": 1},
        })
        result = self.system.calculate(scoresheet)
        assert result.final_ranking[0] == "B"

    def test_details_has_expected_keys(self, clear_winner):
        result = self.system.calculate(clear_winner)
        assert "majority_threshold" in result.details
        assert "cumulative_counts" in result.details
        assert "rounds" in result.details
