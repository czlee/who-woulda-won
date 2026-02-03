"""Scoresheet parsers for various competition result sources."""

from .base import ScoresheetParser

# Parser registry - import parsers here to register them
_parsers: list[type[ScoresheetParser]] = []


def register_parser(parser_class: type[ScoresheetParser]) -> type[ScoresheetParser]:
    """Decorator to register a parser class."""
    _parsers.append(parser_class)
    return parser_class


def get_all_parsers() -> list[type[ScoresheetParser]]:
    """Return all registered parser classes."""
    return _parsers.copy()


def detect_parser(source: str) -> ScoresheetParser | None:
    """Auto-detect and return an appropriate parser instance for the given source."""
    for parser_class in _parsers:
        parser = parser_class()
        if parser.can_parse(source):
            return parser
    return None


def get_supported_url_formats() -> str:
    """Return a user-friendly description of supported URL formats."""
    lines = ["We currently support scoresheets from:"]
    for parser_class in _parsers:
        example = getattr(parser_class, "EXAMPLE_URL", None)
        if example:
            lines.append(f"  - {example}")
    return "\n".join(lines)
