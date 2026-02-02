"""Orchestrator: parse scoresheet and run all voting systems."""

from dataclasses import dataclass
from typing import Any

from core.models import Scoresheet, VotingResult
from core.parsers import detect_parser, get_all_parsers
from core.voting import get_all_voting_systems


@dataclass
class AnalysisResult:
    """Complete analysis result with scoresheet and all voting outcomes."""
    scoresheet: Scoresheet
    results: list[VotingResult]

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return {
            "competition_name": self.scoresheet.competition_name,
            "competitors": self.scoresheet.competitors,
            "judges": self.scoresheet.judges,
            "num_competitors": self.scoresheet.num_competitors,
            "num_judges": self.scoresheet.num_judges,
            "results": [
                {
                    "system_name": r.system_name,
                    "final_ranking": r.final_ranking,
                    "details": r.details,
                }
                for r in self.results
            ],
        }


class AnalysisError(Exception):
    """Error during scoresheet analysis."""
    pass


def analyze_scoresheet(source: str, content: bytes) -> AnalysisResult:
    """Parse a scoresheet and run all voting systems on it.

    Args:
        source: URL or filename (used to detect the appropriate parser)
        content: Raw bytes of the scoresheet file/page

    Returns:
        AnalysisResult with the parsed scoresheet and all voting results

    Raises:
        AnalysisError: If no parser is found or parsing fails
    """
    # Find appropriate parser
    parser = detect_parser(source)
    if parser is None:
        available = [p.__class__.__name__ for p in [p() for p in get_all_parsers()]]
        raise AnalysisError(
            f"No parser found for source: {source}. "
            f"Available parsers: {available or 'none registered'}"
        )

    # Parse the scoresheet
    try:
        scoresheet = parser.parse(source, content)
    except Exception as e:
        raise AnalysisError(f"Failed to parse scoresheet: {e}") from e

    # Run all voting systems
    results = []
    for voting_system in get_all_voting_systems():
        try:
            result = voting_system.calculate(scoresheet)
            results.append(result)
        except Exception as e:
            # Include error in results rather than failing entirely
            results.append(VotingResult(
                system_name=voting_system.name,
                final_ranking=[],
                details={"error": str(e)},
            ))

    return AnalysisResult(scoresheet=scoresheet, results=results)
