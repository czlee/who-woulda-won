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

    def test_h2h_elimination_tiebreak(self):
        """Two candidates tied for fewest votes, head-to-head resolves.

             J1  J2  J3  J4  J5  J6  J7
        A     1   1   1   2   2   3   3
        B     2   3   2   1   3   1   2
        C     3   2   3   3   1   2   1

        Round 1: A=3, B=2, C=2. B and C tied.
        H2H: B preferred by 4, C by 3 → C eliminated.
        Round 2: A=4, B=3 → A wins.
        """
        scoresheet = make_scoresheet("H2H Elimination", {
            "J1": {"A": 1, "B": 2, "C": 3},
            "J2": {"A": 1, "B": 3, "C": 2},
            "J3": {"A": 1, "B": 2, "C": 3},
            "J4": {"A": 2, "B": 1, "C": 3},
            "J5": {"A": 2, "B": 3, "C": 1},
            "J6": {"A": 3, "B": 1, "C": 2},
            "J7": {"A": 3, "B": 2, "C": 1},
        })
        result = self.system.calculate(scoresheet)
        assert result.final_ranking[0] == "A"
        assert result.final_ranking == ["A", "B", "C"]

    def test_h2h_elimination_tiebreak_details(self):
        """Verify tiebreak details structure for h2h elimination."""
        scoresheet = make_scoresheet("H2H Elimination Details", {
            "J1": {"A": 1, "B": 2, "C": 3},
            "J2": {"A": 1, "B": 3, "C": 2},
            "J3": {"A": 1, "B": 2, "C": 3},
            "J4": {"A": 2, "B": 1, "C": 3},
            "J5": {"A": 2, "B": 3, "C": 1},
            "J6": {"A": 3, "B": 1, "C": 2},
            "J7": {"A": 3, "B": 2, "C": 1},
        })
        result = self.system.calculate(scoresheet)
        first_placement = result.details["placement_rounds"][0]
        irv_rounds = first_placement["irv_rounds"]

        # Round 1 should have elimination with tiebreak
        round1 = irv_rounds[0]
        assert round1["method"] == "elimination"
        assert round1["eliminated"] == "C"
        assert "tiebreak" in round1

        tb = round1["tiebreak"]
        assert tb["type"] == "elimination"
        assert set(tb["tied_candidates"]) == {"B", "C"}
        assert len(tb["steps"]) == 1

        step = tb["steps"][0]
        assert step["method"] == "head_to_head"
        assert step["resolved"] is True
        assert step["eliminated"] == "C"

        h2h = step["head_to_head"]
        assert h2h["winner"] == "B"
        assert h2h["counts"]["B"] == 4
        assert h2h["counts"]["C"] == 3

    def test_irv_elimination_tiebreak(self):
        """Three candidates tied for fewest, sub-IRV resolves elimination.

             J1  J2  J3  J4  J5  J6  J7  J8  J9
        A     1   1   1   2   3   4   2   4   3
        B     2   2   3   1   1   3   4   4   4
        C     4   3   2   2   2   1   1   3   3
        D     3   4   4   4   4   2   3   1   1

        Main round 1: A=3, B=2, C=2, D=2.
        B, C, D tied → sub-IRV among {B,C,D}.
        Sub-IRV: B=4, C=3, D=2 → D eliminated first → D eliminated.
        """
        scoresheet = make_scoresheet("IRV Elimination", {
            "J1": {"A": 1, "B": 2, "C": 4, "D": 3},
            "J2": {"A": 1, "B": 2, "C": 3, "D": 4},
            "J3": {"A": 1, "B": 3, "C": 2, "D": 4},
            "J4": {"A": 2, "B": 1, "C": 2, "D": 4},
            "J5": {"A": 3, "B": 1, "C": 2, "D": 4},
            "J6": {"A": 4, "B": 3, "C": 1, "D": 2},
            "J7": {"A": 2, "B": 4, "C": 1, "D": 3},
            "J8": {"A": 4, "B": 4, "C": 3, "D": 1},
            "J9": {"A": 3, "B": 4, "C": 3, "D": 1},
        })
        result = self.system.calculate(scoresheet)
        assert result.final_ranking[0] == "A"

    def test_irv_elimination_tiebreak_details(self):
        """Verify tiebreak details when sub-IRV resolves 3-way elimination tie."""
        scoresheet = make_scoresheet("IRV Elimination Details", {
            "J1": {"A": 1, "B": 2, "C": 4, "D": 3},
            "J2": {"A": 1, "B": 2, "C": 3, "D": 4},
            "J3": {"A": 1, "B": 3, "C": 2, "D": 4},
            "J4": {"A": 2, "B": 1, "C": 2, "D": 4},
            "J5": {"A": 3, "B": 1, "C": 2, "D": 4},
            "J6": {"A": 4, "B": 3, "C": 1, "D": 2},
            "J7": {"A": 2, "B": 4, "C": 1, "D": 3},
            "J8": {"A": 4, "B": 4, "C": 3, "D": 1},
            "J9": {"A": 3, "B": 4, "C": 3, "D": 1},
        })
        result = self.system.calculate(scoresheet)
        first_placement = result.details["placement_rounds"][0]
        round1 = first_placement["irv_rounds"][0]

        assert round1["method"] == "elimination"
        assert "tiebreak" in round1

        tb = round1["tiebreak"]
        assert tb["type"] == "elimination"
        assert len(tb["tied_candidates"]) == 3
        assert len(tb["steps"]) >= 1

        step = tb["steps"][0]
        assert step["method"] == "irv"
        assert "irv_rounds" in step
        assert len(step["irv_rounds"]) > 0

    def test_winner_tiebreak_with_sub_irv(self):
        """All candidates tied, sub-IRV resolves winner (randomly if needed).

             J1  J2  J3  J4  J5  J6
        A     1   1   2   3   3   3
        B     2   3   1   1   2   2
        C     3   2   3   2   1   1

        First-choice: A=2, B=2, C=2. All tied → winner tiebreak.
        Sub-IRV also all tied → resolved at random.
        """
        scoresheet = make_scoresheet("Winner Tiebreak", {
            "J1": {"A": 1, "B": 2, "C": 3},
            "J2": {"A": 1, "B": 3, "C": 2},
            "J3": {"A": 2, "B": 1, "C": 3},
            "J4": {"A": 3, "B": 1, "C": 2},
            "J5": {"A": 3, "B": 2, "C": 1},
            "J6": {"A": 3, "B": 2, "C": 1},
        })
        result = self.system.calculate(scoresheet)
        first_placement = result.details["placement_rounds"][0]
        round1 = first_placement["irv_rounds"][0]

        assert round1["method"] == "all_tied_tiebreak"
        assert "tiebreak" in round1

        tb = round1["tiebreak"]
        assert tb["type"] == "winner"

        # First step should be sub-IRV
        step = tb["steps"][0]
        assert step["method"] == "irv"
        assert "irv_rounds" in step

    def test_perfect_cycle_has_tiebreak_details(self, perfect_cycle):
        """Perfect cycle should produce tiebreak details at every level."""
        result = self.system.calculate(perfect_cycle)
        first_placement = result.details["placement_rounds"][0]
        irv_rounds = first_placement["irv_rounds"]
        assert len(irv_rounds) > 0

        # Should hit the all_tied_tiebreak case
        round1 = irv_rounds[0]
        assert round1["method"] == "all_tied_tiebreak"
        assert "tiebreak" in round1

        tb = round1["tiebreak"]
        assert tb["type"] == "winner"
        assert len(tb["steps"]) > 0

    def test_random_fallback_in_winner_tiebreak(self):
        """When h2h and sub-IRV can't resolve, random fallback is used.

        Perfect 3-way cycle: all h2h are tied via sub-IRV, falls back to
        random once max recursion depth is reached.
        """
        scoresheet = make_scoresheet("Random Fallback", {
            "J1": {"A": 1, "B": 2, "C": 3},
            "J2": {"A": 3, "B": 1, "C": 2},
            "J3": {"A": 2, "B": 3, "C": 1},
        })
        result = self.system.calculate(scoresheet)
        first_placement = result.details["placement_rounds"][0]
        round1 = first_placement["irv_rounds"][0]

        assert round1["method"] == "all_tied_tiebreak"
        tb = round1["tiebreak"]

        # Walk down the recursive sub-IRV chain until we find a random step
        def find_random_step(tiebreak):
            for step in tiebreak.get("steps", []):
                if step["method"] == "random":
                    return step
                if step["method"] == "irv":
                    for rd in step.get("irv_rounds", []):
                        if "tiebreak" in rd:
                            found = find_random_step(rd["tiebreak"])
                            if found:
                                return found
            return None

        random_step = find_random_step(tb)
        assert random_step is not None, "Expected a random step somewhere in tiebreak chain"
        assert random_step["winner"] in ["A", "B", "C"]
        assert set(random_step["remaining_tied"]) == {"A", "B", "C"}

    def test_no_tiebreak_when_clear(self, clear_winner):
        """When there's no tie, no tiebreak details should appear."""
        result = self.system.calculate(clear_winner)
        first_placement = result.details["placement_rounds"][0]
        for rd in first_placement["irv_rounds"]:
            assert "tiebreak" not in rd
