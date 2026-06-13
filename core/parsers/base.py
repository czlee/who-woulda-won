"""Abstract base class for scoresheet parsers."""

import re
from abc import ABC, abstractmethod

from core.models import Scoresheet

_ROUND_SUFFIX_RE = re.compile(
    r'\s+(?:Finals|Prelims|Semis|Quarters|Final|Prelim|Semi|Quarter)\b.*$', re.IGNORECASE
)


def _common_word_prefix(names: list[str]) -> str:
    """Return the longest common word-level prefix across all names."""
    if not names:
        return ""
    word_lists = [name.split() for name in names]
    prefix_words = []
    for words in zip(*word_lists):
        if len({w.lower() for w in words}) == 1:
            prefix_words.append(words[0])
        else:
            break
    return " ".join(prefix_words)


def _get_division_core(name: str, prefix: str) -> str:
    """Strip the common prefix and round suffix from a division name, returning the lowercased core."""
    core = name
    if prefix and core.lower().startswith(prefix.lower()):
        core = core[len(prefix):].lstrip()
    return _ROUND_SUFFIX_RE.sub("", core).lower()


def shorten_division_name(name: str, all_names: list[str]) -> str:
    """Return a display-friendly short form of a division name.

    Strips the longest common word prefix shared by all names in the list,
    and strips the round-type suffix (Finals, Prelims, etc.) and anything
    following it. Preserves original capitalisation.
    """
    prefix = _common_word_prefix(all_names)
    core = name
    if prefix and core.lower().startswith(prefix.lower()):
        core = core[len(prefix):].lstrip()
    return _ROUND_SUFFIX_RE.sub("", core).strip()


class PrelimsError(ValueError):
    """Raised when a scoresheet is detected as a prelims/callback round.

    This tool only supports finals scoresheets where judges give rankings.
    """
    pass


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

    def can_parse_content(self, content: bytes, filename: str) -> bool:
        """Check if this parser can handle the given file content.

        Used for file uploads where there is no URL to match against.
        Subclasses should override this to inspect file content for
        tell-tale signs of their format.

        Args:
            content: Raw bytes of the uploaded file
            filename: Original filename (may help with basic filtering)

        Returns:
            True if this parser can likely handle the content, False otherwise
        """
        return False

    @abstractmethod
    def parse(self, source: str, content: bytes, division: str | None = None) -> Scoresheet:
        """Parse the content into a Scoresheet.

        Args:
            source: Original URL or filename (for context)
            content: Raw bytes of the file/page content
            division: Optional division name (or substring) to select.
                      Only used by parsers that support multiple divisions.

        Returns:
            Parsed Scoresheet object

        Raises:
            ValueError: If the content cannot be parsed
        """
        pass
