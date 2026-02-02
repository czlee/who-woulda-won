"""Abstract base class for scoresheet parsers."""

from abc import ABC, abstractmethod

from core.models import Scoresheet


class ScoresheetParser(ABC):
    """Abstract base class for parsing competition scoresheets.

    Each parser implementation handles a specific source (e.g., a particular
    website's format). Parsers are registered via the @register_parser decorator
    in core/parsers/__init__.py.
    """

    @abstractmethod
    def can_parse(self, source: str) -> bool:
        """Check if this parser can handle the given source.

        Args:
            source: URL or filename to check

        Returns:
            True if this parser can handle the source, False otherwise
        """
        pass

    @abstractmethod
    def parse(self, source: str, content: bytes) -> Scoresheet:
        """Parse the content into a Scoresheet.

        Args:
            source: Original URL or filename (for context)
            content: Raw bytes of the file/page content

        Returns:
            Parsed Scoresheet object

        Raises:
            ValueError: If the content cannot be parsed
        """
        pass
