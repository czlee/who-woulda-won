"""Tests for core.summarize — controversy classification and sentence generation."""

import pytest

from core.analyze import AnalysisResult
from core.models import Placement, Scoresheet, VotingResult
from core.summarize import summarize


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(system_name: str, winner: str | list[str]) -> VotingResult:
    """Build a minimal VotingResult with the given winner(s) at rank 1."""
    if isinstance(winner, str):
        ranking = [Placement(name=winner, rank=1, tied=False)]
    else:
        ranking = [Placement(name=w, rank=1, tied=True) for w in winner]
    return VotingResult(system_name=system_name, final_ranking=ranking)


def _make_analysis(
    scoresheet: Scoresheet,
    rp_winner: str | list[str],
    borda_winner: str | list[str],
    schulze_winner: str | list[str],
    irv_winner: str | list[str],
) -> AnalysisResult:
    """Build an AnalysisResult with the given winners for each system."""
    return AnalysisResult(
        scoresheet=scoresheet,
        results=[
            _make_result("Relative Placement", rp_winner),
            _make_result("Borda Count", borda_winner),
            _make_result("Schulze Method", schulze_winner),
            _make_result("Sequential IRV", irv_winner),
        ],
    )


def _simple_scoresheet(
    competitors: list[str] | None = None,
    num_judges: int = 7,
) -> Scoresheet:
    """Build a scoresheet with uniform rankings (all judges rank in order).

    Good enough for tests that only care about the agreement pattern, not
    the actual judge data.
    """
    if competitors is None:
        competitors = ["A", "B", "C", "D", "E"]
    judges = [f"J{i}" for i in range(1, num_judges + 1)]
    rankings = {
        judge: {c: i + 1 for i, c in enumerate(competitors)}
        for judge in judges
    }
    return Scoresheet(
        competition_name="Test",
        competitors=competitors,
        judges=judges,
        rankings=rankings,
    )


def _polariser_scoresheet(
    polariser: str = "A",
    competitors: list[str] | None = None,
    polariser_rankings: list[int] | None = None,
) -> Scoresheet:
    """Build a scoresheet where one competitor has extreme, polarising rankings.

    The polariser gets rankings like [1, 1, 1, 12, 12, 11, 10] to trigger
    stdev > 4.0 and spread > 60% of field size.

    Pass custom polariser_rankings to control first-place vote count (e.g. to
    avoid triggering the one-short-of-majority condition).
    """
    if competitors is None:
        competitors = [
            "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L",
        ]
    num_judges = 7
    judges = [f"J{i}" for i in range(1, num_judges + 1)]

    # Default: everyone ranked in order
    rankings = {}
    for judge in judges:
        rankings[judge] = {c: i + 1 for i, c in enumerate(competitors)}

    # Override the polariser's rankings
    if polariser_rankings is None:
        polariser_rankings = [1, 1, 1, 12, 12, 11, 10]
    for j, judge in enumerate(judges):
        rankings[judge][polariser] = polariser_rankings[j]
        # Bump others down if needed to avoid duplicate ranks (simplified)
        if polariser_rankings[j] <= competitors.index(polariser) + 1:
            for c in competitors:
                if c != polariser and rankings[judge][c] >= polariser_rankings[j]:
                    rankings[judge][c] += 1

    return Scoresheet(
        competition_name="Polariser Test",
        competitors=competitors,
        judges=judges,
        rankings=rankings,
    )


# ---------------------------------------------------------------------------
# Consistent
# ---------------------------------------------------------------------------

class TestConsistent:
    def test_all_agree(self):
        scoresheet = _simple_scoresheet()
        analysis = _make_analysis(scoresheet, "A", "A", "A", "A")
        result = summarize(analysis)
        assert result["level"] == "consistent"
        assert result["label"] == "\u2705 Consistent"
        assert "A" in result["sentence"]

    def test_all_agree_non_dominant_sentence(self):
        """Non-dominant winner gets the plain 'all systems' sentence."""
        competitors = ["A", "B", "C", "D", "E"]
        judges = ["J1", "J2", "J3", "J4", "J5", "J6", "J7"]
        # A gets 1st from only 3 of 7 judges (not more than half)
        rankings = {
            "J1": {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5},
            "J2": {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5},
            "J3": {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5},
            "J4": {"A": 2, "B": 1, "C": 3, "D": 4, "E": 5},
            "J5": {"A": 2, "B": 1, "C": 3, "D": 4, "E": 5},
            "J6": {"A": 2, "B": 1, "C": 3, "D": 4, "E": 5},
            "J7": {"A": 2, "B": 1, "C": 3, "D": 4, "E": 5},
        }
        scoresheet = Scoresheet(
            competition_name="Non-dominant", competitors=competitors,
            judges=judges, rankings=rankings,
        )
        analysis = _make_analysis(scoresheet, "A", "A", "A", "A")
        result = summarize(analysis)
        assert result["sentence"] == "All systems produced A as the winner."

    def test_dominant_winner(self):
        """Winner ranked 1st by more than half the judges."""
        competitors = ["A", "B", "C", "D", "E"]
        judges = ["J1", "J2", "J3", "J4", "J5", "J6", "J7"]
        rankings = {
            "J1": {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5},
            "J2": {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5},
            "J3": {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5},
            "J4": {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5},
            "J5": {"A": 2, "B": 1, "C": 3, "D": 4, "E": 5},
            "J6": {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5},
            "J7": {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5},
        }
        scoresheet = Scoresheet(
            competition_name="Dominant", competitors=competitors,
            judges=judges, rankings=rankings,
        )
        analysis = _make_analysis(scoresheet, "A", "A", "A", "A")
        result = summarize(analysis)
        assert result["level"] == "consistent"
        assert "dominant" in result["sentence"].lower()
        assert "A" in result["sentence"]

    def test_not_dominant_if_half(self):
        """Exactly half 1sts is NOT dominant (need more than half)."""
        competitors = ["A", "B", "C", "D"]
        judges = ["J1", "J2", "J3", "J4"]
        rankings = {
            "J1": {"A": 1, "B": 2, "C": 3, "D": 4},
            "J2": {"A": 1, "B": 2, "C": 3, "D": 4},
            "J3": {"A": 2, "B": 1, "C": 3, "D": 4},
            "J4": {"A": 2, "B": 1, "C": 3, "D": 4},
        }
        scoresheet = Scoresheet(
            competition_name="Half", competitors=competitors,
            judges=judges, rankings=rankings,
        )
        analysis = _make_analysis(scoresheet, "A", "A", "A", "A")
        result = summarize(analysis)
        assert result["level"] == "consistent"
        assert "dominant" not in result["sentence"].lower()


# ---------------------------------------------------------------------------
# Close call
# ---------------------------------------------------------------------------

class TestCloseCall:
    def test_one_dissenter(self):
        scoresheet = _simple_scoresheet()
        analysis = _make_analysis(scoresheet, "A", "A", "A", "B")
        result = summarize(analysis)
        assert result["level"] == "close_call"
        assert result["label"] == "\U0001f914 Close call"
        assert "A" in result["sentence"]
        assert "B" in result["sentence"]

    def test_one_dissenter_names_method(self):
        scoresheet = _simple_scoresheet()
        analysis = _make_analysis(scoresheet, "A", "A", "A", "B")
        result = summarize(analysis)
        assert "Sequential IRV" in result["sentence"]
        assert "most systems" in result["sentence"]

    def test_two_two_split(self):
        """2-2 split: RP + one agree, two disagree (same alt winner)."""
        scoresheet = _simple_scoresheet()
        analysis = _make_analysis(scoresheet, "A", "B", "A", "B")
        result = summarize(analysis)
        assert result["level"] == "close_call"
        assert "A" in result["sentence"]
        assert "B" in result["sentence"]
        # Should mention the agreeing system alongside RP
        assert "Schulze Method" in result["sentence"]

    def test_two_two_split_mentions_both_disagreeing(self):
        scoresheet = _simple_scoresheet()
        analysis = _make_analysis(scoresheet, "A", "B", "A", "B")
        result = summarize(analysis)
        assert "Borda Count" in result["sentence"]
        assert "Sequential IRV" in result["sentence"]


# ---------------------------------------------------------------------------
# Shakeup
# ---------------------------------------------------------------------------

class TestShakeup:
    def test_all_three_disagree_same_alt(self):
        scoresheet = _simple_scoresheet()
        analysis = _make_analysis(scoresheet, "A", "B", "B", "B")
        result = summarize(analysis)
        assert result["level"] == "shakeup"
        assert result["label"] == "\U0001f62e Shakeup"
        assert "A" in result["sentence"]
        assert "B" in result["sentence"]

    def test_default_sentence(self):
        scoresheet = _simple_scoresheet()
        analysis = _make_analysis(scoresheet, "A", "B", "B", "B")
        result = summarize(analysis)
        assert "every other system" in result["sentence"]

    def test_polariser_rp_winner(self):
        """RP's winner is a polariser — sentence mentions polarising scores."""
        scoresheet = _polariser_scoresheet(polariser="A")
        analysis = _make_analysis(scoresheet, "A", "B", "B", "B")
        result = summarize(analysis)
        assert result["level"] == "shakeup"
        assert "polarising" in result["sentence"].lower()
        assert "A" in result["sentence"]
        assert "B" in result["sentence"]

    def test_polariser_alt_winner(self):
        """Alternative winner is a polariser (without one-short-of-majority)."""
        # Use 2 first-place votes so one-short-of-majority (= 3 in 7-judge panel)
        # doesn't fire, letting the polariser check take precedence.
        scoresheet = _polariser_scoresheet(
            polariser="B", polariser_rankings=[1, 1, 12, 12, 11, 10, 9],
        )
        analysis = _make_analysis(scoresheet, "A", "B", "B", "B")
        result = summarize(analysis)
        assert result["level"] == "shakeup"
        assert "polarising" in result["sentence"].lower()

    def test_one_short_beats_polariser_alt_winner(self):
        """One-short-of-majority takes precedence over polariser alt winner."""
        # B has 3 first-place votes (one short of majority=4 in a 7-judge panel)
        # and is also a polariser; the one-short check fires first.
        scoresheet = _polariser_scoresheet(polariser="B")
        analysis = _make_analysis(scoresheet, "A", "B", "B", "B")
        result = summarize(analysis)
        assert result["level"] == "shakeup"
        assert "one short" in result["sentence"]
        assert "polarising" not in result["sentence"].lower()

    def test_polariser_sentence_includes_ordinals(self):
        """Polariser sentence should mention ranking extremes."""
        scoresheet = _polariser_scoresheet(polariser="A")
        analysis = _make_analysis(scoresheet, "A", "B", "B", "B")
        result = summarize(analysis)
        assert "1st" in result["sentence"]
        # Should mention worst ranking too
        assert "12th" in result["sentence"] or "11th" in result["sentence"]


# ---------------------------------------------------------------------------
# Drama
# ---------------------------------------------------------------------------

class TestDrama:
    def test_three_way_split(self):
        """Each of the three non-RP systems picks a different winner."""
        scoresheet = _simple_scoresheet()
        analysis = _make_analysis(scoresheet, "A", "B", "C", "D")
        result = summarize(analysis)
        assert result["level"] == "drama"
        assert result["label"] == "\U0001f631 Drama!"

    def test_three_way_sentence(self):
        scoresheet = _simple_scoresheet()
        analysis = _make_analysis(scoresheet, "A", "B", "C", "D")
        result = summarize(analysis)
        assert "No consensus" in result["sentence"]
        assert "A" in result["sentence"]
        assert "B" in result["sentence"]
        assert "C" in result["sentence"]
        assert "D" in result["sentence"]

    def test_two_disagree_different_winners(self):
        """Two systems disagree with different alt winners (one agrees)."""
        scoresheet = _simple_scoresheet()
        analysis = _make_analysis(scoresheet, "A", "B", "A", "C")
        result = summarize(analysis)
        assert result["level"] == "drama"
        assert "three ways" in result["sentence"]

    def test_partial_drama_with_agreement(self):
        """Drama case where one system agrees with RP."""
        scoresheet = _simple_scoresheet()
        analysis = _make_analysis(scoresheet, "A", "B", "A", "C")
        result = summarize(analysis)
        # Should mention the agreeing system alongside RP
        assert "Schulze Method" in result["sentence"]
        assert "relative placement" in result["sentence"].lower()

    def test_three_disagree_two_unique_alts(self):
        """Three disagree, but two share the same alt winner."""
        scoresheet = _simple_scoresheet()
        analysis = _make_analysis(scoresheet, "A", "B", "B", "C")
        result = summarize(analysis)
        assert result["level"] == "drama"
        assert "three ways" in result["sentence"]


# ---------------------------------------------------------------------------
# RP tie
# ---------------------------------------------------------------------------

class TestRPTie:
    def test_rp_tie_all_agree(self):
        """When all systems agree on a tie, it's still consistent."""
        scoresheet = _simple_scoresheet()
        analysis = _make_analysis(
            scoresheet, ["A", "B"], ["A", "B"], ["A", "B"], ["A", "B"],
        )
        result = summarize(analysis)
        # All systems agree, even on a tie — that's consistent
        assert result["level"] == "consistent"

    def test_rp_tie_others_break_it(self):
        scoresheet = _simple_scoresheet()
        analysis = _make_analysis(
            scoresheet, ["A", "B"], "A", "A", "A",
        )
        result = summarize(analysis)
        assert result["level"] == "close_call"
        assert "broke the tie" in result["sentence"]
        assert "A" in result["sentence"]

    def test_rp_tie_others_divided(self):
        scoresheet = _simple_scoresheet()
        analysis = _make_analysis(
            scoresheet, ["A", "B"], "A", "B", "C",
        )
        result = summarize(analysis)
        assert result["level"] == "close_call"
        assert "equally divided" in result["sentence"]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_no_rp_result(self):
        scoresheet = _simple_scoresheet()
        analysis = AnalysisResult(
            scoresheet=scoresheet,
            results=[
                _make_result("Borda Count", "A"),
                _make_result("Schulze Method", "A"),
            ],
        )
        result = summarize(analysis)
        assert result["level"] == "consistent"
        assert "Could not determine" in result["sentence"]

    def test_only_rp_result(self):
        scoresheet = _simple_scoresheet()
        analysis = AnalysisResult(
            scoresheet=scoresheet,
            results=[_make_result("Relative Placement", "A")],
        )
        result = summarize(analysis)
        assert result["level"] == "consistent"
        assert "No other voting systems" in result["sentence"]

    def test_errored_system_excluded(self):
        """A system with empty final_ranking (error) is excluded."""
        scoresheet = _simple_scoresheet()
        analysis = AnalysisResult(
            scoresheet=scoresheet,
            results=[
                _make_result("Relative Placement", "A"),
                _make_result("Borda Count", "A"),
                _make_result("Schulze Method", "A"),
                VotingResult(
                    system_name="Sequential IRV",
                    final_ranking=[],
                    details={"error": "something broke"},
                ),
            ],
        )
        result = summarize(analysis)
        # Only 2 other systems, both agree → consistent
        assert result["level"] == "consistent"

    def test_summary_keys(self):
        """Summary dict always has level, label, and sentence."""
        scoresheet = _simple_scoresheet()
        analysis = _make_analysis(scoresheet, "A", "A", "A", "A")
        result = summarize(analysis)
        assert set(result.keys()) == {"level", "label", "sentence"}


# ---------------------------------------------------------------------------
# Polariser detection
# ---------------------------------------------------------------------------

class TestPolariserDetection:
    def test_high_stdev_detected(self):
        """Competitor with stdev > 4.0 is detected as a polariser."""
        from core.summarize import _detect_polariser

        scoresheet = _polariser_scoresheet(polariser="A")
        analysis = AnalysisResult(scoresheet=scoresheet, results=[])
        result = _detect_polariser(analysis, {"A"})
        assert result is not None
        assert result["name"] == "A"
        assert result["stdev"] > 4.0

    def test_consistent_not_detected(self):
        """Competitor with consistent rankings is NOT a polariser."""
        from core.summarize import _detect_polariser

        scoresheet = _simple_scoresheet()
        analysis = AnalysisResult(scoresheet=scoresheet, results=[])
        result = _detect_polariser(analysis, {"A"})
        assert result is None

    def test_most_polarising_returned(self):
        """When multiple polarisers exist, the one with highest stdev is returned."""
        from core.summarize import _detect_polariser

        competitors = [
            "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L",
        ]
        judges = ["J1", "J2", "J3", "J4", "J5", "J6", "J7"]
        rankings = {}
        for judge in judges:
            rankings[judge] = {c: i + 1 for i, c in enumerate(competitors)}
        # A: moderately polarising
        for j, val in enumerate([1, 2, 1, 10, 9, 2, 11]):
            rankings[judges[j]]["A"] = val
        # B: extremely polarising
        for j, val in enumerate([1, 1, 1, 12, 12, 12, 1]):
            rankings[judges[j]]["B"] = val

        scoresheet = Scoresheet(
            competition_name="Multi", competitors=competitors,
            judges=judges, rankings=rankings,
        )
        analysis = AnalysisResult(scoresheet=scoresheet, results=[])
        result = _detect_polariser(analysis, {"A", "B"})
        assert result is not None
        assert result["name"] == "B"
