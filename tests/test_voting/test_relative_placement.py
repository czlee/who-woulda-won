"""Tests for Relative Placement (Skating System) voting system."""

import pytest

from tests.conftest import make_scoresheet
from core.voting.relative_placement import RelativePlacementSystem


@pytest.fixture
def quality_of_majority_scoresheet():
    """7 judges, 4 competitors. Quality of majority needed for 1st place.

    At cutoff 2: A and B both have 4 judges (majority=4), so greater majority
    is tied. A's best 4 placements sum to 5 (1+1+1+2), B's sum to 7 (1+2+2+2).
    A wins 1st via quality of majority.

             J1  J2  J3  J4  J5  J6  J7
        A     1   1   1   2   3   4   4
        B     2   2   2   1   4   3   3
        C     3   4   3   3   1   2   1
        D     4   3   4   4   2   1   2
    """
    return make_scoresheet("Quality of Majority", {
        "J1": {"A": 1, "B": 2, "C": 3, "D": 4},
        "J2": {"A": 1, "B": 2, "C": 4, "D": 3},
        "J3": {"A": 1, "B": 2, "C": 3, "D": 4},
        "J4": {"A": 2, "B": 1, "C": 3, "D": 4},
        "J5": {"A": 3, "B": 4, "C": 1, "D": 2},
        "J6": {"A": 4, "B": 3, "C": 2, "D": 1},
        "J7": {"A": 4, "B": 3, "C": 1, "D": 2},
    })


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
        """B beats A via greater majority: at cutoff 2, B has 5 judges vs A's 3.

             J1  J2  J3  J4  J5
        A     1   1   2   3   3
        B     2   2   1   1   2
        C     3   3   3   2   1

        At cutoff 1: no majority. At cutoff 2: A has 3, B has 5.
        Both have majority (3), but B has more.
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

        place1 = result.details["rounds"][0]
        resolution = place1["resolution"]
        assert {
            "method": "greater_majority",
            "final_cutoff": 2
        }.items() <= resolution.items()

        # Cutoff 1: no majority
        assert {
            "cutoff": 1,
            "result": "no_majority",
            "counts": {"A": 2, "B": 2, "C": 1},
        }.items() <= resolution["cutoff_progression"][0].items()

        # Cutoff 2: both have majority, B has more
        step2 = resolution["cutoff_progression"][1]
        assert {
            "cutoff": 2,
            "result": "multiple_majority",
            "counts": {"A": 3, "B": 5, "C": 2},
            "tiebreaker": "greater_majority",
        }.items() <= step2.items()
        assert set(step2["with_majority"]) == {"A", "B"}

    def test_details_has_expected_keys(self, clear_winner):
        result = self.system.calculate(clear_winner)
        assert "majority_threshold" in result.details
        assert "cumulative_counts" in result.details
        assert "rounds" in result.details

    # --- greater_majority detail tests ---

    def test_greater_majority_detail(self, disagreement):
        """Place 3: D beats C via greater majority at cutoff 3.

        At cutoff 3: D has 4 judges at 3rd or better, C has only 3.
        Both have majority (3), but D has more.
        """
        result = self.system.calculate(disagreement)
        place3 = result.details["rounds"][2]
        assert {
            "target_place": 3,
            "winner": "D",
            "tied": False,
        }.items() <= place3.items()

        resolution = place3["resolution"]
        assert {
            "method": "greater_majority",
            "final_cutoff": 3,
        }.items() <= resolution.items()

        cutoff_step = resolution["cutoff_progression"][-1]
        assert {
            "cutoff": 3,
            "result": "multiple_majority",
            "counts": {"C": 3, "D": 4},
            "tiebreaker": "greater_majority",
        }.items() <= cutoff_step.items()
        assert set(cutoff_step["with_majority"]) == {"C", "D"}

    # --- quality_of_majority detail tests ---

    def test_quality_of_majority_tiebreak(self, quality_of_majority_scoresheet):
        """A wins 1st via quality of majority when greater majority is tied.

        At cutoff 2: A and B both have 4 judges (majority=4). Greater majority
        can't break the tie (both have count 4). A's best 4 placements sum to
        5 (1+1+1+2), B's sum to 7 (1+2+2+2). Lower sum wins → A.
        """
        result = self.system.calculate(quality_of_majority_scoresheet)
        assert result.final_ranking == ["A", "B", "C", "D"]

        place1 = result.details["rounds"][0]
        resolution = place1["resolution"]
        assert {
            "method": "quality_of_majority",
            "final_cutoff": 2,
        }.items() <= resolution.items()

        cutoff_step = resolution["cutoff_progression"][-1]
        assert {
            "cutoff": 2,
            "result": "multiple_majority",
            "counts": {"A": 4, "B": 4, "C": 3, "D": 3},
            "quality_scores": {"A": 5, "B": 7},
            "tiebreaker": "quality_of_majority",
        }.items() <= cutoff_step.items()
        assert set(cutoff_step["with_majority"]) == {"A", "B"}
