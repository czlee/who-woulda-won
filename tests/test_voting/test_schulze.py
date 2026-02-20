"""Tests for Schulze method voting system."""

from tests.conftest import make_scoresheet, ranking_names
from core.voting.schulze import SchulzeSystem


class TestSchulze:
    def setup_method(self):
        self.system = SchulzeSystem()

    def test_name(self):
        assert self.system.name == "Schulze Method"

    def test_clear_winner(self, clear_winner):
        """Dataset 1: A beats all, B beats C and D, C beats D → A, B, C, D."""
        result = self.system.calculate(clear_winner)
        assert ranking_names(result) == ["A", "B", "C", "D"]

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
        assert ranking_names(result) == ["A", "B", "C", "D"]

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
        assert ranking_names(result) == ["A", "B", "C"]

    def test_two_competitors(self, two_competitors):
        result = self.system.calculate(two_competitors)
        assert ranking_names(result) == ["A", "B"]

    def test_perfect_cycle(self, perfect_cycle):
        """All pairwise matchups are 2-1. All path strengths equal.

        All Schulze wins should be 2 ties * 0.5 = 1.
        """
        result = self.system.calculate(perfect_cycle)
        assert len(result.final_ranking) == 3
        assert set(ranking_names(result)) == {"A", "B", "C"}

        wins = result.details["schulze_wins"]
        # In a perfect cycle, after Floyd-Warshall, all path strengths
        # should be equal (2), so no one beats anyone → all wins = 0
        assert all(w == 1 for w in wins.values())

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
        assert ranking_names(result)[0] == "A"
        assert result.details["schulze_wins"]["A"] == 2

    def test_details_has_expected_keys(self, clear_winner):
        result = self.system.calculate(clear_winner)
        assert "pairwise_preferences" in result.details
        assert "path_strengths" in result.details
        assert "schulze_wins" in result.details
        assert "ties" in result.details
        assert "winning_beatpath_sums" in result.details

    # --- path_strengths tests ---

    def test_clear_winner_path_strengths(self, clear_winner):
        """No cycles: path strengths equal direct defeat strengths.

        Pairwise: A>B(2-1), A>C(3-0), A>D(3-0), B>C(2-1), B>D(3-0), C>D(3-0).
        No indirect path can improve on any direct defeat.
        """
        result = self.system.calculate(clear_winner)
        assert result.details["path_strengths"] == {
            "A": {"A": 0, "B": 2, "C": 3, "D": 3},
            "B": {"A": 0, "B": 0, "C": 2, "D": 3},
            "C": {"A": 0, "B": 0, "C": 0, "D": 3},
            "D": {"A": 0, "B": 0, "C": 0, "D": 0},
        }

    def test_disagreement_path_strengths(self, disagreement):
        """No cycles: A>B(3-2), A>C(3-2), A>D(3-2), B>C(4-1), B>D(3-2), C>D(3-2).

        B→C has the strongest single defeat (4). No indirect paths improve anything.
        """
        result = self.system.calculate(disagreement)
        assert result.details["path_strengths"] == {
            "A": {"A": 0, "B": 3, "C": 3, "D": 3},
            "B": {"A": 0, "B": 0, "C": 4, "D": 3},
            "C": {"A": 0, "B": 0, "C": 0, "D": 3},
            "D": {"A": 0, "B": 0, "C": 0, "D": 0},
        }

    def test_perfect_cycle_path_strengths(self, perfect_cycle):
        """Cycle A>B(2-1), B>C(2-1), C>A(2-1). Floyd-Warshall propagates.

        After Floyd-Warshall, all off-diagonal path strengths become 2:
        - p[B][A] starts at 0 but reaches 2 via B→C→A
        - p[C][B] starts at 0 but reaches 2 via C→A→B
        - p[A][C] starts at 0 but reaches 2 via A→B→C
        """
        result = self.system.calculate(perfect_cycle)
        assert result.details["path_strengths"] == {
            "A": {"A": 0, "B": 2, "C": 2},
            "B": {"A": 2, "B": 0, "C": 2},
            "C": {"A": 2, "B": 2, "C": 0},
        }

    def test_unanimous_path_strengths(self, unanimous):
        """All 3 judges agree: A=1, B=2, C=3.

        All defeats are 3-0 with no cycles.
        """
        result = self.system.calculate(unanimous)
        assert result.details["path_strengths"] == {
            "A": {"A": 0, "B": 3, "C": 3},
            "B": {"A": 0, "B": 0, "C": 3},
            "C": {"A": 0, "B": 0, "C": 0},
        }

    def test_two_competitors_path_strengths(self, two_competitors):
        """A beats B 2-1. Simplest possible case."""
        result = self.system.calculate(two_competitors)
        assert result.details["path_strengths"] == {
            "A": {"A": 0, "B": 2},
            "B": {"A": 0, "B": 0},
        }

    def test_indirect_path_beats_direct_defeat(self):
        """Indirect paths through a cycle produce stronger paths than direct defeats.

        9 judges, 3 competitors. Cycle: A>B(5-4), B>C(6-3), C>A(6-3).

                 J1  J2  J3  J4  J5  J6  J7  J8  J9
            A     1   1   2   3   3   3   2   2   2
            B     2   2   1   1   1   1   3   3   3
            C     3   3   3   2   2   2   1   1   1

        Direct defeats: p[A][B]=5, p[B][C]=6, p[C][A]=6.
        After Floyd-Warshall, indirect paths fill in:
        - p[B][A]=6 via B→C→A (min(6,6)=6) — B doesn't beat A directly!
        - p[A][C]=5 via A→B→C (min(5,6)=5) — A doesn't beat C directly!
        - p[C][B]=5 via C→A→B (min(6,5)=5) — C doesn't beat B directly!
        Result: B wins (2 wins), then C (1 win), then A (0 wins).
        """
        scoresheet = make_scoresheet("Indirect Paths", {
            # 2× ABC
            "J1": {"A": 1, "B": 2, "C": 3},
            "J2": {"A": 1, "B": 2, "C": 3},
            # 1× BAC
            "J3": {"A": 2, "B": 1, "C": 3},
            # 3× BCA
            "J4": {"A": 3, "B": 1, "C": 2},
            "J5": {"A": 3, "B": 1, "C": 2},
            "J6": {"A": 3, "B": 1, "C": 2},
            # 3× CAB
            "J7": {"A": 2, "B": 3, "C": 1},
            "J8": {"A": 2, "B": 3, "C": 1},
            "J9": {"A": 2, "B": 3, "C": 1},
        })
        result = self.system.calculate(scoresheet)
        # Direct defeats on diagonal: A→B=5, B→C=6, C→A=6
        # Indirect paths fill the rest: B→A=6 (via C), A→C=5 (via B), C→B=5 (via A)
        assert result.details["path_strengths"] == {
            "A": {"A": 0, "B": 5, "C": 5},
            "B": {"A": 6, "B": 0, "C": 6},
            "C": {"A": 6, "B": 5, "C": 0},
        }
        assert ranking_names(result) == ["B", "C", "A"]

    # --- beatpath tests ---

    def test_beatpaths_in_details(self, clear_winner):
        """Verify that beatpaths key exists in details."""
        result = self.system.calculate(clear_winner)
        assert "beatpaths" in result.details

    def test_beatpaths_direct_only(self, clear_winner):
        """No cycles: all beatpaths are direct (two-node paths)."""
        result = self.system.calculate(clear_winner)
        bp = result.details["beatpaths"]
        # A beats B directly with strength 2
        assert bp["A"]["B"] == [
            {"node": "A", "strength": 2},
            {"node": "B"},
        ]
        # No path from D to anyone (D loses all)
        assert bp["D"] == {}

    def test_beatpaths_indirect_paths(self):
        """Indirect paths through a cycle produce multi-step beatpaths.

        Uses the same 9-judge scenario from test_indirect_path_beats_direct_defeat.
        A>B(5), B>C(6), C>A(6). After Floyd-Warshall:
        - B→A goes via C: B ─[6]→ C ─[6]→ A (strength 6)
        - A→C goes via B: A ─[5]→ B ─[6]→ C (strength 5)
        - C→B goes via A: C ─[6]→ A ─[5]→ B (strength 5)
        """
        scoresheet = make_scoresheet("Indirect Paths", {
            "J1": {"A": 1, "B": 2, "C": 3},
            "J2": {"A": 1, "B": 2, "C": 3},
            "J3": {"A": 2, "B": 1, "C": 3},
            "J4": {"A": 3, "B": 1, "C": 2},
            "J5": {"A": 3, "B": 1, "C": 2},
            "J6": {"A": 3, "B": 1, "C": 2},
            "J7": {"A": 2, "B": 3, "C": 1},
            "J8": {"A": 2, "B": 3, "C": 1},
            "J9": {"A": 2, "B": 3, "C": 1},
        })
        result = self.system.calculate(scoresheet)
        bp = result.details["beatpaths"]

        # B→A via C (indirect): B ─[6]→ C ─[6]→ A
        assert bp["B"]["A"] == [
            {"node": "B", "strength": 6},
            {"node": "C", "strength": 6},
            {"node": "A"},
        ]
        # A→C via B (indirect): A ─[5]→ B ─[6]→ C
        assert bp["A"]["C"] == [
            {"node": "A", "strength": 5},
            {"node": "B", "strength": 6},
            {"node": "C"},
        ]
        # C→B via A (indirect): C ─[6]→ A ─[5]→ B
        assert bp["C"]["B"] == [
            {"node": "C", "strength": 6},
            {"node": "A", "strength": 5},
            {"node": "B"},
        ]

        # Direct paths still exist too
        assert bp["A"]["B"] == [
            {"node": "A", "strength": 5},
            {"node": "B"},
        ]

    # --- tie handling tests ---

    def test_half_integer_wins(self):
        """Two competitors with a 1-1 split produce half-integer wins.

             J1  J2
        A     1   2
        B     2   1

        d[A][B]=1, d[B][A]=1 → p[A][B]=0, p[B][A]=0 (tie).
        Each gets 0.5 wins.
        """
        scoresheet = make_scoresheet("Even Split", {
            "J1": {"A": 1, "B": 2},
            "J2": {"A": 2, "B": 1},
        })
        result = self.system.calculate(scoresheet)
        wins = result.details["schulze_wins"]
        assert wins["A"] == 0.5
        assert wins["B"] == 0.5

    def test_ties_detail_content(self, perfect_cycle, clear_winner):
        """Verify the ties detail lists groups of tied competitors."""
        # Perfect cycle: all three competitors are tied (tiebreak can't help)
        result = self.system.calculate(perfect_cycle)
        ties = result.details["ties"]
        assert len(ties) == 1
        assert set(ties[0]) == {"A", "B", "C"}

        # Clear winner: no ties
        result = self.system.calculate(clear_winner)
        assert result.details["ties"] == []

    def test_perfect_cycle_winning_beatpath_sums(self, perfect_cycle):
        """Perfect cycle: all strengths equal, winning_beatpath_sums are all equal."""
        result = self.system.calculate(perfect_cycle)
        assert "winning_beatpath_sums" in result.details
        sums = result.details["winning_beatpath_sums"]
        assert len(set(sums.values())) == 1  # all equal

    # --- tiebreak tests ---

    def test_asymmetric_ties(self):
        """Competitors with different numbers of ties get different win counts.

             J1  J2  J3  J4
        A     1   3   2   2
        B     2   1   3   1
        C     3   2   1   3

        Pairwise: A vs B: 2-2 (tie), A vs C: 2-2 (tie), B vs C: 3-1 (B wins).
        Path strengths: p[B][C]=3, all others 0.
        Wins: B=1.5 (1 win + 1 tie), A=1.0 (2 ties), C=0.5 (1 tie).
        Without half-points A and C would both have 0 wins (tied);
        half-points break that tie.
        """
        scoresheet = make_scoresheet("Asymmetric Ties", {
            "J1": {"A": 1, "B": 2, "C": 3},
            "J2": {"A": 3, "B": 1, "C": 2},
            "J3": {"A": 2, "B": 3, "C": 1},
            "J4": {"A": 2, "B": 1, "C": 3},
        })
        result = self.system.calculate(scoresheet)
        wins = result.details["schulze_wins"]
        assert wins["B"] == 1.5
        assert wins["A"] == 1.0
        assert wins["C"] == 0.5
        assert ranking_names(result) == ["B", "A", "C"]
        # No ties remain — half-points resolved them all
        assert result.details["ties"] == []

    def test_winning_beatpath_strength_tiebreak(self):
        """Three-way tie on wins resolved by winning beatpath strength sums.

             J1  J2  J3  J4  J5  J6
        A     1   3   2   1   3   2
        B     2   1   3   2   1   4
        C     4   2   1   4   2   1
        D     3   4   4   3   4   3

        A, B, C each have 2 Schulze wins, D has 0. Winning beatpath
        strength sums break the tie: A=6, B=5, C=4 → A, B, C, D.
        """
        scoresheet = make_scoresheet("Winning Beatpath Strength Tiebreak", {
            "J1": {"A": 1, "B": 2, "C": 4, "D": 3},
            "J2": {"A": 3, "B": 1, "C": 2, "D": 4},
            "J3": {"A": 2, "B": 3, "C": 1, "D": 4},
            "J4": {"A": 1, "B": 2, "C": 4, "D": 3},
            "J5": {"A": 3, "B": 1, "C": 2, "D": 4},
            "J6": {"A": 2, "B": 4, "C": 1, "D": 3},
        })
        result = self.system.calculate(scoresheet)
        wins = result.details["schulze_wins"]
        assert wins["A"] == 2
        assert wins["B"] == 2
        assert wins["C"] == 2
        assert wins["D"] == 0

        names = ranking_names(result)
        assert names == ["A", "B", "C", "D"]

        beatpath_sums = result.details["winning_beatpath_sums"]
        assert beatpath_sums["A"] == 6
        assert beatpath_sums["B"] == 5
        assert beatpath_sums["C"] == 4

    def test_winning_beatpath_strength_partial_tiebreak(self):
        """Three-way tie on wins only partially resolved by winning beatpath strength.

             J1  J2  J3  J4  J5  J6
        A     1   3   2   1   3   2
        B     2   1   3   2   1   3
        C     4   2   1   4   2   1
        D     3   4   4   3   4   4

        Same as above but J6 ranks B 3rd instead of 4th. A, B, C each
        have 2 Schulze wins. Winning beatpath strength sums: A=6, B=6,
        C=4. C is resolved to 3rd, but A and B remain tied at 1st.
        """
        scoresheet = make_scoresheet("Winning Beatpath Strength Partial Tiebreak", {
            "J1": {"A": 1, "B": 2, "C": 4, "D": 3},
            "J2": {"A": 3, "B": 1, "C": 2, "D": 4},
            "J3": {"A": 2, "B": 3, "C": 1, "D": 4},
            "J4": {"A": 1, "B": 2, "C": 4, "D": 3},
            "J5": {"A": 3, "B": 1, "C": 2, "D": 4},
            "J6": {"A": 2, "B": 3, "C": 1, "D": 4},
        })
        result = self.system.calculate(scoresheet)
        wins = result.details["schulze_wins"]
        assert wins["A"] == 2
        assert wins["B"] == 2
        assert wins["C"] == 2
        assert wins["D"] == 0

        assert {r.name for r in result.final_ranking[0:2]} == {"A", "B"}
        assert all(r.rank == 1 for r in result.final_ranking[0:2])
        assert all(r.tied == True for r in result.final_ranking[0:2])
        assert result.final_ranking[2].to_dict() == {"name": "C", "rank": 3, "tied": False}
        assert result.final_ranking[3].to_dict() == {"name": "D", "rank": 4, "tied": False}

        beatpath_sums = result.details["winning_beatpath_sums"]
        assert beatpath_sums["A"] == 6
        assert beatpath_sums["B"] == 6
        assert beatpath_sums["C"] == 4
