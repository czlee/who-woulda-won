"""Tests for Borda count voting system."""

from tests.conftest import make_scoresheet, ranking_names

from core.voting.borda import BordaCountSystem


class TestBordaCount:
    def setup_method(self):
        self.system = BordaCountSystem()

    def test_name(self):
        assert self.system.name == "Borda Count"

    def test_clear_winner(self, clear_winner):
        """Dataset 1: A=8, B=6, C=4, D=0 → A, B, C, D."""
        result = self.system.calculate(clear_winner)
        assert ranking_names(result) == ["A", "B", "C", "D"]

    def test_clear_winner_scores(self, clear_winner):
        """Verify individual Borda scores for dataset 1."""
        result = self.system.calculate(clear_winner)
        scores = result.details["scores"]
        # n=4, points = 4 - rank
        # A: (3+3+2)=8, B: (2+1+3)=6, C: (1+2+1)=4, D: (0+0+0)=0
        assert scores["A"] == 8
        assert scores["B"] == 6
        assert scores["C"] == 4
        assert scores["D"] == 0

    def test_disagreement(self, disagreement):
        """Dataset 2: A=9, B=9, C=6, D=6. Recursive Borda: A>B(3-2), C>D(3-2)."""
        result = self.system.calculate(disagreement)
        assert ranking_names(result) == ["A", "B", "C", "D"]

    def test_disagreement_tied_scores(self, disagreement):
        """Verify the tied scores that trigger tiebreakers."""
        result = self.system.calculate(disagreement)
        scores = result.details["scores"]
        assert scores["A"] == scores["B"] == 9
        assert scores["C"] == scores["D"] == 6

    def test_disagreement_tiebreaker_info(self, disagreement):
        """Verify tiebreaker entries have breakdowns for both tie groups."""
        result = self.system.calculate(disagreement)
        tbs = result.details["tiebreakers"]
        assert len(tbs) == 2
        # First tiebreak: A and B tied at 9
        tb1 = tbs[0]
        assert set(tb1["tied_competitors"]) == {"A", "B"}
        assert tb1["score"] == 9
        assert tb1["level"] == 1
        assert tb1["resolution"]["method"] == "recursive-borda"
        assert "breakdowns" in tb1["resolution"]["details"]
        # Second tiebreak: C and D tied at 6
        tb2 = tbs[1]
        assert set(tb2["tied_competitors"]) == {"C", "D"}
        assert tb2["score"] == 6
        assert tb2["level"] == 1
        assert "breakdowns" in tb2["resolution"]["details"]

    def test_unanimous(self, unanimous):
        result = self.system.calculate(unanimous)
        assert ranking_names(result) == ["A", "B", "C"]

    def test_two_competitors(self, two_competitors):
        result = self.system.calculate(two_competitors)
        assert ranking_names(result) == ["A", "B"]

    def test_perfect_cycle(self, perfect_cycle):
        """All Borda scores equal (3 each). All competitors should be present."""
        result = self.system.calculate(perfect_cycle)
        assert len(result.final_ranking) == 3
        assert set(ranking_names(result)) == {"A", "B", "C"}

    def test_details_has_expected_keys(self, clear_winner):
        result = self.system.calculate(clear_winner)
        assert "scores" in result.details
        assert "breakdowns" in result.details
        assert "max_possible" in result.details

    def test_three_way_tie_recursive_borda(self):
        """Three-way Borda tie resolved by recursive relative Borda.

        Full Borda scores (n=4): A=9, B=9, C=9, D=3.
        Relative Borda among {A,B,C} (k=3): B=6, A=5, C=4.
        Expected: B, A, C, D.

             J1  J2  J3  J4  J5
        A     1   1   2   4   3
        B     2   4   1   3   1
        C     3   2   3   1   2
        D     4   3   4   2   4
        """
        scoresheet = make_scoresheet("Three-Way Tie", {
            "J1": {"A": 1, "B": 2, "C": 3, "D": 4},
            "J2": {"A": 1, "B": 4, "C": 2, "D": 3},
            "J3": {"A": 2, "B": 1, "C": 3, "D": 4},
            "J4": {"A": 4, "B": 3, "C": 1, "D": 2},
            "J5": {"A": 3, "B": 1, "C": 2, "D": 4},
        })
        result = self.system.calculate(scoresheet)
        scores = result.details["scores"]
        assert scores["A"] == scores["B"] == scores["C"] == 9
        assert scores["D"] == 3
        assert ranking_names(result) == ["B", "A", "C", "D"]

        # Verify tiebreaker info reports recursive-borda
        assert len(result.details["tiebreakers"]) == 1
        tb = result.details["tiebreakers"][0]
        assert tb["tied_competitors"] == ["A", "B", "C"]
        assert tb["score"] == 9
        assert tb["level"] == 1
        assert tb["resolution"]["method"] == "recursive-borda"
        assert tb["resolution"]["details"]["relative_scores"] == {"A": 5, "B": 6, "C": 4}
        assert "breakdowns" in tb["resolution"]["details"]
        for c in ["A", "B", "C"]:
            bd = tb["resolution"]["details"]["breakdowns"][c]
            assert "judges" in bd
            assert "points" in bd
            assert len(bd["points"]) == 5
            assert sum(bd["points"]) == tb["resolution"]["details"]["relative_scores"][c]
