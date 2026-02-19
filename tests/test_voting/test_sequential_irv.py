"""Tests for Sequential IRV voting system."""

from tests.conftest import make_scoresheet, ranking_names
from core.voting.sequential_irv import SequentialIRVSystem


class TestSequentialIRV:
    def setup_method(self):
        self.system = SequentialIRVSystem()

    def test_name(self):
        assert self.system.name == "Sequential IRV"

    def test_clear_winner(self, clear_winner):
        """Dataset 1: A has first-choice majority (2/3) → A, B, C, D."""
        result = self.system.calculate(clear_winner)
        assert ranking_names(result) == ["A", "B", "C", "D"]

    def test_disagreement(self, disagreement):
        """Dataset 2: No first-choice majority. Elimination rounds resolve.

        IRV Round 1: A=2, B=2, C=1, D=0. Eliminate D.
        Then: A=2, B=2, C=1. Eliminate C. Then: A=3, B=2. A wins.
        """
        result = self.system.calculate(disagreement)
        assert ranking_names(result) == ["A", "B", "C", "D"]

    def test_unanimous(self, unanimous):
        result = self.system.calculate(unanimous)
        assert ranking_names(result) == ["A", "B", "C"]

    def test_two_competitors(self, two_competitors):
        result = self.system.calculate(two_competitors)
        assert ranking_names(result) == ["A", "B"]

    def test_perfect_cycle(self, perfect_cycle):
        """All first-choice votes equal (1 each). All competitors present."""
        result = self.system.calculate(perfect_cycle)
        assert len(result.final_ranking) == 3
        assert set(ranking_names(result)) == {"A", "B", "C"}

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
        assert ranking_names(result)[0] == "A"
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
        assert ranking_names(result)[0] == "C"

    def test_details_has_expected_keys(self, clear_winner):
        result = self.system.calculate(clear_winner)
        assert "placement_rounds" in result.details
        rounds = result.details["placement_rounds"]
        assert len(rounds) > 0
        assert "place" in rounds[0]
        assert "winner" in rounds[0]

    def test_two_way_elimination_tiebreak(self):
        """Two candidates tied for fewest votes, restricted vote resolves.

             J1  J2  J3  J4  J5  J6  J7
        A     1   1   1   2   2   3   3
        B     2   3   2   1   3   1   2
        C     3   2   3   3   1   2   1

        Round 1: A=3, B=2, C=2. B and C tied.
        Restricted vote among {B,C}: B=4, C=3 → C eliminated.
        Round 2: A=4, B=3 → A wins.
        """
        scoresheet = make_scoresheet("Two-Way Elimination", {
            "J1": {"A": 1, "B": 2, "C": 3},
            "J2": {"A": 1, "B": 3, "C": 2},
            "J3": {"A": 1, "B": 2, "C": 3},
            "J4": {"A": 2, "B": 1, "C": 3},
            "J5": {"A": 2, "B": 3, "C": 1},
            "J6": {"A": 3, "B": 1, "C": 2},
            "J7": {"A": 3, "B": 2, "C": 1},
        })
        result = self.system.calculate(scoresheet)
        assert ranking_names(result)[0] == "A"
        assert ranking_names(result) == ["A", "B", "C"]

    def test_two_way_elimination_tiebreak_details(self):
        """Verify tiebreak details structure for 2-way elimination."""
        scoresheet = make_scoresheet("Two-Way Elimination Details", {
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
        assert step["method"] == "restricted_vote"
        assert step["resolved"] is True
        assert step["eliminated"] == "C"
        assert step["votes"]["B"] == 4
        assert step["votes"]["C"] == 3

    def test_restricted_vote_elimination_tiebreak(self):
        """Three candidates tied for fewest, restricted vote resolves.

             J1  J2  J3  J4  J5  J6  J7  J8  J9
        A     1   1   1   2   3   4   2   4   3
        B     2   2   3   1   1   3   4   4   4
        C     4   3   2   2   2   1   1   3   3
        D     3   4   4   4   4   2   3   1   1

        Main round 1: A=3, B=2, C=2, D=2.
        B, C, D tied → restricted vote among {B,C,D}.
        Restricted: B=4, C=3, D=2 → D eliminated (fewest).
        """
        scoresheet = make_scoresheet("Restricted Vote Elimination", {
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
        assert ranking_names(result)[0] == "A"

    def test_restricted_vote_elimination_tiebreak_details(self):
        """Verify tiebreak details for restricted vote elimination."""
        scoresheet = make_scoresheet("Restricted Vote Details", {
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
        assert round1["eliminated"] == "D"
        assert "tiebreak" in round1

        tb = round1["tiebreak"]
        assert tb["type"] == "elimination"
        assert set(tb["tied_candidates"]) == {"B", "C", "D"}
        assert len(tb["steps"]) == 1

        step = tb["steps"][0]
        assert step["method"] == "restricted_vote"
        assert step["resolved"] is True
        assert step["eliminated"] == "D"
        assert step["votes"]["B"] == 4
        assert step["votes"]["C"] == 3
        assert step["votes"]["D"] == 2

    def test_restricted_vote_resolves_with_second_preference(self):
        """Restricted vote finds all equal at 1st pref → 2nd pref resolves.

             J1  J2  J3  J4  J5  J6  J7  J8  J9
        A     1   1   1   2   3   4   4   4   4
        B     2   4   4   1   1   2   3   3   3
        C     3   2   3   4   4   1   1   2   2
        D     4   3   2   3   2   3   2   1   1

        Main round 1: A=3, B=2, C=2, D=2.
        B, C, D tied → restricted vote among {B,C,D}: B=3, C=3, D=3.
        All equal at 1st pref → 2nd pref: B=1, C=4, D=4. B eliminated.
        """
        scoresheet = make_scoresheet("All Equal Random", {
            "J1": {"A": 1, "B": 2, "C": 3, "D": 4},
            "J2": {"A": 1, "B": 4, "C": 2, "D": 3},
            "J3": {"A": 1, "B": 4, "C": 3, "D": 2},
            "J4": {"A": 2, "B": 1, "C": 4, "D": 3},
            "J5": {"A": 3, "B": 1, "C": 4, "D": 2},
            "J6": {"A": 4, "B": 2, "C": 1, "D": 3},
            "J7": {"A": 4, "B": 3, "C": 1, "D": 2},
            "J8": {"A": 4, "B": 3, "C": 2, "D": 1},
            "J9": {"A": 4, "B": 3, "C": 2, "D": 1},
        })
        result = self.system.calculate(scoresheet)
        assert set(ranking_names(result)) == {"A", "B", "C", "D"}

        first_placement = result.details["placement_rounds"][0]
        round1 = first_placement["irv_rounds"][0]
        assert round1["method"] == "elimination"
        assert round1["eliminated"] == "B"
        tb = round1["tiebreak"]
        assert set(tb["tied_candidates"]) == {"B", "C", "D"}
        assert len(tb["steps"]) == 2

        # First step: restricted_vote at 1st pref, all equal
        step0 = tb["steps"][0]
        assert step0["method"] == "restricted_vote"
        assert step0["resolved"] is False
        assert step0.get("all_equal") is True

        # Second step: restricted_vote at 2nd pref, resolved
        step1 = tb["steps"][1]
        assert step1["method"] == "restricted_vote"
        assert step1.get("preference") == 2
        assert step1["resolved"] is True
        assert step1["eliminated"] == "B"

    def test_restricted_vote_second_preference_details(self):
        """Verify step details when 2nd-preference restricted vote breaks the tie.

        Uses same scoresheet as test_restricted_vote_resolves_with_second_preference.
        step[0]: restricted_vote at 1st pref, all_equal, votes={B:3, C:3, D:3}
        step[1]: restricted_vote at 2nd pref, resolved, eliminated=B, votes={B:1, C:4, D:4}
        """
        scoresheet = make_scoresheet("All Equal Random", {
            "J1": {"A": 1, "B": 2, "C": 3, "D": 4},
            "J2": {"A": 1, "B": 4, "C": 2, "D": 3},
            "J3": {"A": 1, "B": 4, "C": 3, "D": 2},
            "J4": {"A": 2, "B": 1, "C": 4, "D": 3},
            "J5": {"A": 3, "B": 1, "C": 4, "D": 2},
            "J6": {"A": 4, "B": 2, "C": 1, "D": 3},
            "J7": {"A": 4, "B": 3, "C": 1, "D": 2},
            "J8": {"A": 4, "B": 3, "C": 2, "D": 1},
            "J9": {"A": 4, "B": 3, "C": 2, "D": 1},
        })
        result = self.system.calculate(scoresheet)
        first_placement = result.details["placement_rounds"][0]
        round1 = first_placement["irv_rounds"][0]
        tb = round1["tiebreak"]

        step0 = tb["steps"][0]
        assert step0["method"] == "restricted_vote"
        assert step0["resolved"] is False
        assert step0["all_equal"] is True
        assert step0["votes"] == {"B": 3, "C": 3, "D": 3}

        step1 = tb["steps"][1]
        assert step1["method"] == "restricted_vote"
        assert step1["preference"] == 2
        assert step1["resolved"] is True
        assert step1["eliminated"] == "B"
        assert step1["votes"] == {"B": 1, "C": 4, "D": 4}

    def test_restricted_vote_narrows_then_resolves(self):
        """Restricted vote narrows 3-way to 2-way, then resolves.

             J1   J2   J3   J4   J5   J6   J7   J8   J9   J10
        A     1    1    1    1    2    2    2    2    2    2
        B     2    2    3    4    1    1    3    4    3    4
        C     3    4    2    3    3    3    1    1    4    3
        D     4    3    4    2    4    4    4    3    1    1

        Main round 1: A=4, B=2, C=2, D=2.
        B, C, D tied → restricted vote among {B,C,D}: B=4, C=3, D=3.
        C, D tied for fewest → narrow to {C,D} → restricted vote: C=6, D=4.
        D eliminated (fewest).
        """
        scoresheet = make_scoresheet("Narrows then Resolves", {
            "J1":  {"A": 1, "B": 2, "C": 3, "D": 4},
            "J2":  {"A": 1, "B": 2, "C": 4, "D": 3},
            "J3":  {"A": 1, "B": 3, "C": 2, "D": 4},
            "J4":  {"A": 1, "B": 4, "C": 3, "D": 2},
            "J5":  {"A": 2, "B": 1, "C": 3, "D": 4},
            "J6":  {"A": 2, "B": 1, "C": 3, "D": 4},
            "J7":  {"A": 2, "C": 1, "B": 3, "D": 4},
            "J8":  {"A": 2, "C": 1, "D": 3, "B": 4},
            "J9":  {"A": 2, "D": 1, "B": 3, "C": 4},
            "J10": {"A": 2, "D": 1, "C": 3, "B": 4},
        })
        result = self.system.calculate(scoresheet)
        assert ranking_names(result)[0] == "A"

        first_placement = result.details["placement_rounds"][0]
        round1 = first_placement["irv_rounds"][0]
        assert round1["method"] == "elimination"
        assert round1["eliminated"] == "D"
        tb = round1["tiebreak"]
        assert set(tb["tied_candidates"]) == {"B", "C", "D"}

        # Step 1: restricted_vote, narrows to C,D
        step0 = tb["steps"][0]
        assert step0["method"] == "restricted_vote"
        assert step0["resolved"] is False
        assert set(step0["remaining_tied"]) == {"C", "D"}
        assert step0["votes"]["B"] == 4
        assert step0["votes"]["C"] == 3
        assert step0["votes"]["D"] == 3

        # Step 2: restricted_vote between C and D
        step1 = tb["steps"][1]
        assert step1["method"] == "restricted_vote"
        assert step1["resolved"] is True
        assert step1["eliminated"] == "D"
        assert step1["votes"]["C"] == 6
        assert step1["votes"]["D"] == 4

    def test_second_choice_vote_count(self):
        """All candidates tied, go to second choice.

             J1  J2  J3  J4  J5  J6
        A     1   1   2   3   3   3
        B     2   3   1   1   2   2
        C     3   2   3   2   1   1

        First choice: A=2, B=2, C=2. All tied → go to second choice.
        Second choice: A=1, B=3, C=2. Eliminate A.
        """
        scoresheet = make_scoresheet("Second Choice", {
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

        assert round1["method"] == "elimination"
        assert round1["tiebreak_choice"] == 2
        assert round1["eliminated"] == "A"
        assert round1["tiebreak_choice_votes"] == {"A": 1, "B": 3, "C": 2}

    def test_third_choice_vote_count(self):
        """All candidates tied, go to third choice.

             J1  J2  J3  J4
        A     1   3   3   2
        B     2   1   4   3
        C     3   2   1   4
        D     4   4   2   1

        First choice: A=1, B=1, C=1, D=1. All tied → go to second choice.
        Second choice: A=1, B=1, C=1, D=1. All tied → go to third choice.
        Third choice: A=2, B=1, C=1, D=0. D is eliminated.
        """
        scoresheet = make_scoresheet("Third Choice", {
            "J1": {"A": 1, "B": 2, "C": 3, "D": 4},
            "J2": {"A": 3, "B": 1, "C": 2, "D": 4},
            "J3": {"A": 3, "B": 4, "C": 1, "D": 2},
            "J4": {"A": 2, "B": 3, "C": 4, "D": 1},
        })
        result = self.system.calculate(scoresheet)
        first_placement = result.details["placement_rounds"][0]
        round1 = first_placement["irv_rounds"][0]

        assert round1["method"] == "elimination"
        assert round1["tiebreak_choice"] == 3
        assert round1["eliminated"] == "D"
        assert round1["tiebreak_choice_votes"] == {"A": 2, "B": 1, "C": 1, "D": 0}
        assert "tiebreak" not in round1

    def test_third_choice_vote_count_restricted_vote_random(self):
        """All candidates tied, go to third choice, then restricted vote, then random.

             J1  J2  J3  J4
        A     1   2   4   4
        B     2   1   3   3
        C     4   4   1   2
        D     3   3   2   1

        First choice: A=1, B=1, C=1, D=1. All tied → go to second choice.
        Second choice: A=1, B=1, C=1, D=1. All tied → go to third choice.
        Third choice: A=0, B=2, C=0, D=2. A and C tied → restricted vote.
        Restricted 1st pref: A=2, C=2 → all equal → try 2nd pref.
        Restricted 2nd pref: A=2, C=2 → all equal → fall back to random.
        """
        scoresheet = make_scoresheet("Third Choice Head-to-Head Random", {
            "J1": {"A": 1, "B": 2, "C": 4, "D": 3},
            "J2": {"A": 2, "B": 1, "C": 4, "D": 3},
            "J3": {"A": 4, "B": 3, "C": 1, "D": 2},
            "J4": {"A": 4, "B": 3, "C": 2, "D": 1},
        })
        result = self.system.calculate(scoresheet)
        first_placement = result.details["placement_rounds"][0]
        round1 = first_placement["irv_rounds"][0]

        assert round1["method"] == "elimination"
        assert round1["tiebreak_choice"] == 3
        assert round1["tiebreak_choice_votes"] == {"A": 0, "B": 2, "C": 0, "D": 2}
        assert round1["eliminated"] in ["A", "C"]

        tiebreak_info = round1["tiebreak"]
        assert set(tiebreak_info["tied_candidates"]) == {"A", "C"}

        assert len(tiebreak_info["steps"]) == 3

        assert tiebreak_info["steps"][0]["method"] == "restricted_vote"
        assert tiebreak_info["steps"][0]["resolved"] == False
        assert tiebreak_info["steps"][0]["all_equal"] == True
        assert tiebreak_info["steps"][0]["preference"] == 1

        assert tiebreak_info["steps"][1]["method"] == "restricted_vote"
        assert tiebreak_info["steps"][1]["resolved"] == False
        assert tiebreak_info["steps"][1]["all_equal"] == True
        assert tiebreak_info["steps"][1]["preference"] == 2

        assert tiebreak_info["steps"][2]["method"] == "random"
        assert set(tiebreak_info["steps"][2]["remaining_tied"]) == {"A", "C"}

    def test_perfect_cycle_has_all_tied_equal(self, perfect_cycle):
        """Perfect cycle has no way to run IRV, so just declare all tied equal."""
        result = self.system.calculate(perfect_cycle)
        first_placement = result.details["placement_rounds"][0]
        irv_rounds = first_placement["irv_rounds"]
        assert len(irv_rounds) == 1

        # Should hit the all_tied_tiebreak case
        round1 = irv_rounds[0]
        assert round1["method"] == "all_tied_equal"
        assert round1["all_tied"] == True
        assert set(round1["winner"]) == {"A", "B", "C"}

    def test_no_tiebreak_when_clear(self, clear_winner):
        """When there's no tie, no tiebreak details should appear."""
        result = self.system.calculate(clear_winner)
        first_placement = result.details["placement_rounds"][0]
        for rd in first_placement["irv_rounds"]:
            assert "tiebreak" not in rd
