"""Tests for Borda count voting system."""

from core.voting.borda import BordaCountSystem


class TestBordaCount:
    def setup_method(self):
        self.system = BordaCountSystem()

    def test_name(self):
        assert self.system.name == "Borda Count"

    def test_clear_winner(self, clear_winner):
        """Dataset 1: A=8, B=6, C=4, D=0 → A, B, C, D."""
        result = self.system.calculate(clear_winner)
        assert result.final_ranking == ["A", "B", "C", "D"]

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
        """Dataset 2: A=9, B=9, C=6, D=6. H2H: A>B(3-2), C>D(3-2) → A, B, C, D."""
        result = self.system.calculate(disagreement)
        assert result.final_ranking == ["A", "B", "C", "D"]

    def test_disagreement_tied_scores(self, disagreement):
        """Verify the tied scores that trigger tiebreakers."""
        result = self.system.calculate(disagreement)
        scores = result.details["scores"]
        assert scores["A"] == scores["B"] == 9
        assert scores["C"] == scores["D"] == 6

    def test_unanimous(self, unanimous):
        result = self.system.calculate(unanimous)
        assert result.final_ranking == ["A", "B", "C"]

    def test_two_competitors(self, two_competitors):
        result = self.system.calculate(two_competitors)
        assert result.final_ranking == ["A", "B"]

    def test_perfect_cycle(self, perfect_cycle):
        """All Borda scores equal (3 each). All competitors should be present."""
        result = self.system.calculate(perfect_cycle)
        assert len(result.final_ranking) == 3
        assert set(result.final_ranking) == {"A", "B", "C"}

    def test_details_has_expected_keys(self, clear_winner):
        result = self.system.calculate(clear_winner)
        assert "scores" in result.details
        assert "breakdowns" in result.details
        assert "max_possible" in result.details
