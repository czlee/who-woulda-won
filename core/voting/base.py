"""Abstract base class for voting systems."""

from abc import ABC, abstractmethod

from core.models import Scoresheet, VotingResult


class VotingSystem(ABC):
    """Abstract base class for voting systems.

    Each voting system implementation calculates a final ranking from
    a scoresheet using its own algorithm. Systems are registered via
    the @register_voting_system decorator in core/voting/__init__.py.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this voting system."""
        pass

    @property
    def description(self) -> str:
        """Optional description of how this voting system works."""
        return ""

    @abstractmethod
    def calculate(self, scoresheet: Scoresheet) -> VotingResult:
        """Calculate the final ranking using this voting system.

        Args:
            scoresheet: The competition scoresheet with all judge rankings

        Returns:
            VotingResult with the final ranking and calculation details
        """
        pass
