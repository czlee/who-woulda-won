"""Core data models for scoresheet and voting results."""

from dataclasses import dataclass, field
from typing import Any, Self


@dataclass
class Scoresheet:
    """Complete scoresheet from a competition.

    Attributes:
        competition_name: Name of the competition/event
        competitors: List of competitor identifiers (names or bib numbers)
        judges: List of judge identifiers (names or initials)
        rankings: Dict mapping judge_id -> dict mapping competitor_id -> rank (1 = best)

    Example:
        >>> scoresheet = Scoresheet(
        ...     competition_name="Novice J&J Finals",
        ...     competitors=["Alice & Bob", "Carol & Dave"],
        ...     judges=["J1", "J2", "J3"],
        ...     rankings={
        ...         "J1": {"Alice & Bob": 1, "Carol & Dave": 2},
        ...         "J2": {"Alice & Bob": 2, "Carol & Dave": 1},
        ...         "J3": {"Alice & Bob": 1, "Carol & Dave": 2},
        ...     }
        ... )
    """
    competition_name: str
    competitors: list[str]
    judges: list[str]
    rankings: dict[str, dict[str, int]]  # judge_id -> {competitor_id -> rank}

    @property
    def num_competitors(self) -> int:
        return len(self.competitors)

    @property
    def num_judges(self) -> int:
        return len(self.judges)

    def get_placement(self, judge: str, competitor: str) -> int:
        """Get the placement (1-indexed) a judge gave to a competitor."""
        return self.rankings[judge][competitor]

    def get_competitor_placements(self, competitor: str) -> list[int]:
        """Get all placements for a competitor across all judges."""
        return [self.rankings[judge][competitor] for judge in self.judges]

    def get_judge_ranking(self, judge: str) -> list[str]:
        """Get competitors in ranked order (1st to last) for a judge."""
        judge_rankings = self.rankings[judge]
        return sorted(self.competitors, key=lambda c: judge_rankings[c])


@dataclass
class Placement:
    """A competitor's placement in a voting result.

    Attributes:
        name: Competitor identifier
        rank: 1-indexed placement (tied competitors share the same rank)
        tied: Whether this competitor is tied with others at this rank
    """
    name: str
    rank: int
    tied: bool

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "rank": self.rank, "tied": self.tied}

    @classmethod
    def build_ranking(
        cls, ordered: list[str | list[str]]
    ) -> list[Self]:
        """Build a list of Placements from an ordered list.

        Args:
            ordered: Competitors in order from 1st to last place.
                Each element is either a single name (str) or a list of
                names (list[str]) for tied competitors.

        Returns:
            List of Placement objects with correct ranks and tied flags.
        """
        placements = []
        rank = 1
        for entry in ordered:
            if isinstance(entry, list):
                for name in entry:
                    placements.append(cls(name=name, rank=rank, tied=True))
                rank += len(entry)
            else:
                placements.append(cls(name=entry, rank=rank, tied=False))
                rank += 1

        return placements


@dataclass
class VotingResult:
    """Result from a voting system.

    Attributes:
        system_name: Human-readable name of the voting system
        final_ranking: Competitors in order from 1st to last place
        details: System-specific details for transparency/debugging
                 (e.g., point totals, elimination rounds, tiebreaker info)
    """
    system_name: str
    final_ranking: list[Placement]
    details: dict[str, Any] = field(default_factory=dict)

    def get_place(self, competitor: str) -> int | None:
        """Get the 1-indexed placement for a competitor, or None if not found."""
        for p in self.final_ranking:
            if p.name == competitor:
                return p.rank
        return None
