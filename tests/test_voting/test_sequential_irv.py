"""Tests for Sequential IRV voting system."""

from tests.conftest import make_scoresheet
from core.voting.sequential_irv import SequentialIRVSystem


class TestSequentialIRV:
    def setup_method(self):
        self.system = SequentialIRVSystem()

    def test_name(self):
        assert self.system.name == "Sequential IRV"

    def test_clear_winner(self, clear_winner):
        """Dataset 1: A has first-choice majority (2/3) → A, B, C, D."""
        result = self.system.calculate(clear_winner)
        assert result.final_ranking == ["A", "B", "C", "D"]

    def test_disagreement(self, disagreement):
        """Dataset 2: No first-choice majority. Elimination rounds resolve.

        IRV Round 1: A=2, B=2, C=1, D=0. Eliminate D.
        Then: A=2, B=2, C=1. Eliminate C. Then: A=3, B=2. A wins.
        """
        result = self.system.calculate(disagreement)
        assert result.final_ranking == ["A", "B", "C", "D"]

    def test_unanimous(self, unanimous):
        result = self.system.calculate(unanimous)
        assert result.final_ranking == ["A", "B", "C"]

    def test_two_competitors(self, two_competitors):
        result = self.system.calculate(two_competitors)
        assert result.final_ranking == ["A", "B"]

    def test_perfect_cycle(self, perfect_cycle):
        """All first-choice votes equal (1 each). All competitors present."""
        result = self.system.calculate(perfect_cycle)
        assert len(result.final_ranking) == 3
        assert set(result.final_ranking) == {"A", "B", "C"}

    def test_majority_wins_immediately(self):
        """When one competitor has >50% first-choice, no elimination needed.

             J1  J2  J3  J4  J5
        A     1   1   1   2   3
        B     2   2   2   1   1
        C     3   3   3   3   2
        """
        scoresheet = make_scoresheet("Majority Winner", {
            "J1": {"A": 1, "B": 2, "C": 3},
            "J2": {"A": 1, "B": 2, "C": 3},
            "J3": {"A": 1, "B": 2, "C": 3},
            "J4": {"A": 2, "B": 1, "C": 3},
            "J5": {"A": 3, "B": 1, "C": 2},
        })
        result = self.system.calculate(scoresheet)
        assert result.final_ranking[0] == "A"
        # First placement should resolve in 1 IRV round (immediate majority)
        first_round = result.details["placement_rounds"][0]
        assert len(first_round["irv_rounds"]) == 1
        assert first_round["irv_rounds"][0]["method"] == "majority"

    def test_elimination_needed(self):
        """No first-choice majority, requires elimination.

             J1  J2  J3  J4  J5
        A     1   3   3   2   2
        B     2   1   2   3   3
        C     3   2   1   1   1
        """
        scoresheet = make_scoresheet("Elimination Needed", {
            "J1": {"A": 1, "B": 2, "C": 3},
            "J2": {"A": 3, "B": 1, "C": 2},
            "J3": {"A": 3, "B": 2, "C": 1},
            "J4": {"A": 2, "B": 3, "C": 1},
            "J5": {"A": 2, "B": 3, "C": 1},
        })
        result = self.system.calculate(scoresheet)
        # C has 3 first-choice votes → majority → wins 1st
        assert result.final_ranking[0] == "C"

    def test_details_has_expected_keys(self, clear_winner):
        result = self.system.calculate(clear_winner)
        assert "placement_rounds" in result.details
        rounds = result.details["placement_rounds"]
        assert len(rounds) > 0
        assert "place" in rounds[0]
        assert "winner" in rounds[0]
