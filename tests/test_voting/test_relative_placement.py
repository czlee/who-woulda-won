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

    # --- greater_majority detail tests ---

    def test_greater_majority_resolution_method(self, disagreement):
        """Place 3 in the disagreement dataset: D beats C via greater majority.

        At cutoff 3: D has 4 judges at 3rd or better, C has only 3.
        """
        result = self.system.calculate(disagreement)
        rounds = result.details["rounds"]
        place3 = rounds[2]
        assert place3["target_place"] == 3
        assert place3["winner"] == "D"
        assert place3["tied"] is False

        resolution = place3["resolution"]
        assert resolution["method"] == "greater_majority"
        assert resolution["final_cutoff"] == 3

    def test_greater_majority_cutoff_counts(self, disagreement):
        """Verify the cumulative counts that triggered the greater majority tiebreak.

        At cutoff 3: C has 3 judges, D has 4 judges. Both have majority (3),
        but D has more — that's the "greater" majority.
        """
        result = self.system.calculate(disagreement)
        place3 = result.details["rounds"][2]
        cutoff_step = place3["resolution"]["cutoff_progression"][-1]

        assert cutoff_step["cutoff"] == 3
        assert cutoff_step["counts"]["C"] == 3
        assert cutoff_step["counts"]["D"] == 4
        assert set(cutoff_step["with_majority"]) == {"C", "D"}
        assert cutoff_step["tiebreaker"] == "greater_majority"

    def test_greater_majority_custom_scoresheet_detail(self):
        """Verify greater majority details when B beats A at cutoff 2.

             J1  J2  J3  J4  J5
        A     1   1   2   3   3
        B     2   2   1   1   2
        C     3   3   3   2   1

        At cutoff 1: no majority. At cutoff 2: A has 3, B has 5.
        Both have majority (3), but B has more.
        """
        scoresheet = make_scoresheet("Greater Majority Detail", {
            "J1": {"A": 1, "B": 2, "C": 3},
            "J2": {"A": 1, "B": 2, "C": 3},
            "J3": {"A": 2, "B": 1, "C": 3},
            "J4": {"A": 3, "B": 1, "C": 2},
            "J5": {"A": 3, "B": 2, "C": 1},
        })
        result = self.system.calculate(scoresheet)
        place1 = result.details["rounds"][0]
        resolution = place1["resolution"]

        assert resolution["method"] == "greater_majority"
        assert resolution["final_cutoff"] == 2

        # Cutoff 1: no majority
        step1 = resolution["cutoff_progression"][0]
        assert step1["cutoff"] == 1
        assert step1["result"] == "no_majority"
        assert step1["counts"]["A"] == 2
        assert step1["counts"]["B"] == 2

        # Cutoff 2: both have majority, B has more
        step2 = resolution["cutoff_progression"][1]
        assert step2["cutoff"] == 2
        assert step2["counts"]["A"] == 3
        assert step2["counts"]["B"] == 5
        assert set(step2["with_majority"]) == {"A", "B"}
        assert step2["tiebreaker"] == "greater_majority"

    # --- quality_of_majority detail tests ---

    def test_quality_of_majority_tiebreak(self, quality_of_majority_scoresheet):
        """A wins 1st via quality of majority when greater majority is tied.

        At cutoff 2: A and B both have 4 judges (majority=4). Greater majority
        can't break the tie. A's best 4 placements sum to 5 (1+1+1+2), B's sum
        to 7 (1+2+2+2). Lower sum wins → A.
        """
        result = self.system.calculate(quality_of_majority_scoresheet)
        assert result.final_ranking[0] == "A"
        assert result.final_ranking == ["A", "B", "C", "D"]

    def test_quality_of_majority_resolution_method(self, quality_of_majority_scoresheet):
        """Verify the resolution method and cutoff for quality of majority."""
        result = self.system.calculate(quality_of_majority_scoresheet)
        place1 = result.details["rounds"][0]
        resolution = place1["resolution"]

        assert resolution["method"] == "quality_of_majority"
        assert resolution["final_cutoff"] == 2

    def test_quality_of_majority_scores(self, quality_of_majority_scoresheet):
        """Verify exact quality score values: sum of best `majority` placements.

        Majority = 4 (7 judges). A's sorted placements: [1,1,1,2,3,4,4],
        best 4 = [1,1,1,2] → sum 5. B's sorted: [1,2,2,2,3,3,4], best 4 =
        [1,2,2,2] → sum 7.
        """
        result = self.system.calculate(quality_of_majority_scoresheet)
        cutoff_step = result.details["rounds"][0]["resolution"]["cutoff_progression"][-1]

        assert cutoff_step["quality_scores"]["A"] == 5
        assert cutoff_step["quality_scores"]["B"] == 7
        assert cutoff_step["tiebreaker"] == "quality_of_majority"

    def test_quality_of_majority_equal_counts_before_quality(
        self, quality_of_majority_scoresheet
    ):
        """Verify both candidates had equal counts, confirming greater majority
        couldn't break the tie and quality of majority was needed.
        """
        result = self.system.calculate(quality_of_majority_scoresheet)
        cutoff_step = result.details["rounds"][0]["resolution"]["cutoff_progression"][-1]

        assert cutoff_step["cutoff"] == 2
        # Both A and B have 4 judges at cutoff 2 — equal, so greater majority fails
        assert cutoff_step["counts"]["A"] == 4
        assert cutoff_step["counts"]["B"] == 4
        assert set(cutoff_step["with_majority"]) == {"A", "B"}
