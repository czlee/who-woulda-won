"""Tests for Relative Placement (Skating System) voting system."""

import pytest

from tests.conftest import make_scoresheet, ranking_names
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
        assert ranking_names(result) == ["A", "B", "C", "D"]

    def test_disagreement_differs_from_others(self, disagreement):
        """Dataset 2: RP uniquely gives A, B, D, C.

        Place 3: D has greater majority at cutoff 3 (4 judges vs C's 3).
        """
        result = self.system.calculate(disagreement)
        assert ranking_names(result) == ["A", "B", "D", "C"]

    def test_unanimous(self, unanimous):
        result = self.system.calculate(unanimous)
        assert ranking_names(result) == ["A", "B", "C"]

    def test_two_competitors(self, two_competitors):
        result = self.system.calculate(two_competitors)
        assert ranking_names(result) == ["A", "B"]

    def test_perfect_cycle(self, perfect_cycle):
        """Symmetric case — all cumulative counts identical."""
        result = self.system.calculate(perfect_cycle)
        assert len(result.final_ranking) == 3
        assert set(ranking_names(result)) == {"A", "B", "C"}

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
        assert ranking_names(result)[0] == "B"

        place1 = result.details["rounds"][0]
        resolution = place1["resolution"]
        assert {
            "method": "greater_majority",
            "final_cutoff": 2
        }.items() <= resolution.items()

        # Cutoff 2: A and B both have majority, B has more
        step = resolution["cutoff_progression"][0]
        assert {
            "cutoff": 2,
            "result": "multiple_majority",
            "counts": {"A": 3, "B": 5},
            "tiebreaker": "greater_majority",
        }.items() <= step.items()
        assert set(step["with_majority"]) == {"A", "B"}

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
        assert ranking_names(result) == ["A", "B", "C", "D"]

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
            "counts": {"A": 4, "B": 4},
            "quality_scores": {"A": 5, "B": 7},
            "tiebreaker": "quality_of_majority",
        }.items() <= cutoff_step.items()
        assert set(cutoff_step["with_majority"]) == {"A", "B"}

    def test_quality_of_majority_tied_twice(self):
        """A and B tie on quality of majority twice, then resolve on greater
        majority on the next one.

             J1  J2  J3  J4  J5
        A     1   1   2   3   5
        B     4   2   1   1   3
        C     3   3   3   4   1
        D     2   4   5   5   2
        E     5   5   4   2   4

        At cutoff 1: no majority.
        At cutoff 2: A and B both have 3. Quality of majority both 4.
        At cutoff 3: A and B both have 4. Quality of majority both 7.
        At cutoff 4: A has 4, B has 5. B wins on greater majority.

        Note that C has a majority at cutoff 3, but this shouldn't count,
        because C is not in the tiebreak.
        """
        scoresheet = make_scoresheet("Quality of Majority Tied Twice", {
            "J1": {"A": 1, "B": 4, "C": 3, "D": 2, "E": 5},
            "J2": {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5},
            "J3": {"A": 2, "B": 1, "C": 3, "D": 5, "E": 4},
            "J4": {"A": 3, "B": 1, "C": 4, "D": 5, "E": 2},
            "J5": {"A": 5, "B": 3, "C": 1, "D": 2, "E": 4},
        })
        result = self.system.calculate(scoresheet)
        assert ranking_names(result) == ["B", "A", "C", "D", "E"]

        place1 = result.details["rounds"][0]
        resolution = place1["resolution"]
        assert {
            "method": "greater_majority",
            "final_cutoff": 4,
        }.items() <= resolution.items()

        assert len(resolution["cutoff_progression"]) == 3

        cutoff_step1 = resolution["cutoff_progression"][0]
        assert {
            "cutoff": 2,
            "result": "multiple_majority",
            "counts": {"A": 3, "B": 3},
            "quality_scores": {"A": 4, "B": 4},
        }.items() <= cutoff_step1.items()
        assert set(cutoff_step1["with_majority"]) == {"A", "B"}

        cutoff_step2 = resolution["cutoff_progression"][1]
        assert {
            "cutoff": 3,
            "result": "multiple_majority",
            "counts": {"A": 4, "B": 4},
            "quality_scores": {"A": 7, "B": 7},
        }.items() <= cutoff_step2.items()
        assert set(cutoff_step2["with_majority"]) == {"A", "B"}

        # C should not be swept in just because it has a majority of 3
        assert "C" not in cutoff_step2["quality_scores"]

        cutoff_step3 = resolution["cutoff_progression"][2]
        assert {
            "cutoff": 4,
            "result": "multiple_majority",
            "counts": {"A": 4, "B": 5},
            "tiebreaker": "greater_majority",
        }.items() <= cutoff_step3.items()
        assert set(cutoff_step3["with_majority"]) == {"A", "B"}


    # --- head-to-head tiebreak tests ---

    def test_head_to_head_resolved(self):
        """B beats A via head-to-head tiebreak when all other tiebreakers are
        exhausted.

             J1  J2  J3  J4  J5
        A     1   2   2   3   1
        B     2   1   1   2   3
        C     3   3   3   1   2

        Cumulative counts (A and B identical):
            cutoff 1: A=2, B=2
            cutoff 2: A=4, B=4
            cutoff 3: A=5, B=5

        Majority = 3. At cutoff 2, A and B both have majority (4).
        Greater majority tied, quality of majority tied (both sum to 6).
        At cutoff 3, still tied (both 5, sum 9).
        H2H: J1→A, J2→B, J3→B, J4→B, J5→A → B wins 3-2.
        """
        scoresheet = make_scoresheet("H2H Resolved Test", {
            "J1": {"A": 1, "B": 2, "C": 3},
            "J2": {"A": 2, "B": 1, "C": 3},
            "J3": {"A": 2, "B": 1, "C": 3},
            "J4": {"A": 3, "B": 2, "C": 1},
            "J5": {"A": 1, "B": 3, "C": 2},
        })
        result = self.system.calculate(scoresheet)
        assert ranking_names(result) == ["B", "A", "C"]

        place1 = result.details["rounds"][0]
        resolution = place1["resolution"]
        assert resolution["method"] == "head_to_head"
        assert set(resolution["h2h_pair"]) == {"A", "B"}
        assert resolution["h2h_counts"] == {"A": 2, "B": 3}

    def test_three_way_unresolved_tie(self, perfect_cycle):
        """Three-way tie after all tiebreakers → unresolved, no H2H attempted.

        Uses the perfect_cycle fixture (3 judges, 3 competitors, perfectly
        symmetric). All cumulative counts, quality scores are identical.
        With 3 candidates, H2H should not be attempted.
        """
        result = self.system.calculate(perfect_cycle)
        assert len(result.final_ranking) == 3
        assert set(ranking_names(result)) == {"A", "B", "C"}

        # All three should be in a single tied round
        place1 = result.details["rounds"][0]
        assert place1["tied"] is True
        resolution = place1["resolution"]
        assert resolution["method"] == "unresolved_tie"
        assert "h2h_pair" not in resolution
        assert "h2h_counts" not in resolution

    def test_head_to_head_tied(self):
        """H2H itself is tied (even number of judges, even split).

             J1  J2  J3  J4
        A     1   1   2   2
        B     2   2   1   1
        C     3   3   3   3

        Majority = 3. At cutoff 2, A and B both have 4 (majority).
        Greater majority tied, quality tied (both sum to 6).
        At cutoff 3, still tied.
        H2H: J1→A, J2→A, J3→B, J4→B → 2-2 tie.
        Result: A and B tied at 1st place.
        """
        scoresheet = make_scoresheet("H2H Tied Test", {
            "J1": {"A": 1, "B": 2, "C": 3},
            "J2": {"A": 1, "B": 2, "C": 3},
            "J3": {"A": 2, "B": 1, "C": 3},
            "J4": {"A": 2, "B": 1, "C": 3},
        })
        result = self.system.calculate(scoresheet)

        # A and B should be tied (order among them is unspecified)
        names = ranking_names(result)
        assert set(names[:2]) == {"A", "B"}
        assert names[2] == "C"
        # Both should have rank 1 (tied)
        a_rank = next(p.rank for p in result.final_ranking if p.name == "A")
        b_rank = next(p.rank for p in result.final_ranking if p.name == "B")
        assert a_rank == b_rank == 1

        place1 = result.details["rounds"][0]
        assert place1["tied"] is True
        resolution = place1["resolution"]
        assert resolution["method"] == "head_to_head"
        assert set(resolution["h2h_pair"]) == {"A", "B"}
        assert resolution["h2h_counts"] == {"A": 2, "B": 2}


class TestRelativePlacementRealData:
    """Integration tests using real competition data to verify correctness."""

    def setup_method(self):
        self.system = RelativePlacementSystem()

    def test_real_competition_7_judges_9_competitors(self):
        """Real WCS competition: 7 judges, 9 competitors.

        Regression test for tiebreak-loser placement bug. At cutoff 5, LC_HR
        and MD_AH both have majority (4). LC_HR wins via quality of majority
        (11 vs 14). MD_AH must be placed next (still at cutoff 5) before
        advancing. Then at cutoff 6, TN_TS is the only one with majority and
        should get 7th, before TL_LD who only reaches majority at cutoff 7.

        The old bug started the cutoff search at target_place for each
        placement, which allowed TL_LD to overtake TN_TS at cutoff 7.
        """
        scoresheet = make_scoresheet("Real Competition 1", {
            "TK": {"SS_GW": 7, "CL_EA": 3, "JP_FF": 8, "AW_DP": 9, "LC_HR": 1, "MD_AH": 2, "TL_LD": 4, "TN_TS": 5, "TM_RP": 6},
            "ZS": {"SS_GW": 2, "CL_EA": 3, "JP_FF": 1, "AW_DP": 4, "LC_HR": 6, "MD_AH": 5, "TL_LD": 8, "TN_TS": 9, "TM_RP": 7},
            "RC": {"SS_GW": 3, "CL_EA": 1, "JP_FF": 4, "AW_DP": 5, "LC_HR": 9, "MD_AH": 2, "TL_LD": 7, "TN_TS": 6, "TM_RP": 8},
            "CP": {"SS_GW": 1, "CL_EA": 5, "JP_FF": 2, "AW_DP": 4, "LC_HR": 8, "MD_AH": 6, "TL_LD": 7, "TN_TS": 3, "TM_RP": 9},
            "KO": {"SS_GW": 2, "CL_EA": 1, "JP_FF": 4, "AW_DP": 8, "LC_HR": 3, "MD_AH": 5, "TL_LD": 7, "TN_TS": 6, "TM_RP": 9},
            "JT": {"SS_GW": 2, "CL_EA": 4, "JP_FF": 3, "AW_DP": 1, "LC_HR": 5, "MD_AH": 6, "TL_LD": 7, "TN_TS": 8, "TM_RP": 9},
            "MP": {"SS_GW": 4, "CL_EA": 1, "JP_FF": 5, "AW_DP": 3, "LC_HR": 2, "MD_AH": 8, "TL_LD": 6, "TN_TS": 7, "TM_RP": 9},
        })
        result = self.system.calculate(scoresheet)
        assert ranking_names(result) == [
            "SS_GW", "CL_EA", "JP_FF", "AW_DP", "LC_HR",
            "MD_AH", "TN_TS", "TL_LD", "TM_RP",
        ]

    def test_real_competition_5_judges_10_competitors(self):
        """Real WCS competition: 5 judges, 10 competitors.

        Regression test for tiebreak-loser placement bug. At cutoff 7, HC_CB
        and TM both have majority (3). HC_CB wins via quality of majority
        (13 vs 18). TM must be placed next (still at cutoff 7) before
        advancing. The old bug let JP_SVH overtake TM at cutoff 8 via
        greater majority (4 vs 3).
        """
        scoresheet = make_scoresheet("Real Competition 2", {
            "AF": {"MD_FF": 4, "DR_CH": 7, "DS_JZ": 3, "CL_GW": 1, "NE_LJ": 2, "CJ_CH": 5, "HC_CB": 9, "JP_SVH": 6, "TL_AS": 8, "TM": 10},
            "AM": {"MD_FF": 2, "DR_CH": 3, "DS_JZ": 8, "CL_GW": 1, "NE_LJ": 6, "CJ_CH": 10, "HC_CB": 7, "JP_SVH": 4, "TL_AS": 9, "TM": 5},
            "SP": {"MD_FF": 2, "DR_CH": 6, "DS_JZ": 3, "CL_GW": 5, "NE_LJ": 10, "CJ_CH": 4, "HC_CB": 1, "JP_SVH": 8, "TL_AS": 7, "TM": 9},
            "EG": {"MD_FF": 5, "DR_CH": 2, "DS_JZ": 1, "CL_GW": 4, "NE_LJ": 3, "CJ_CH": 6, "HC_CB": 10, "JP_SVH": 8, "TL_AS": 9, "TM": 7},
            "AV": {"MD_FF": 2, "DR_CH": 1, "DS_JZ": 10, "CL_GW": 4, "NE_LJ": 8, "CJ_CH": 7, "HC_CB": 5, "JP_SVH": 9, "TL_AS": 3, "TM": 6},
        })
        result = self.system.calculate(scoresheet)
        assert ranking_names(result) == [
            "MD_FF", "DR_CH", "DS_JZ", "CL_GW", "NE_LJ",
            "CJ_CH", "HC_CB", "TM", "JP_SVH", "TL_AS",
        ]
