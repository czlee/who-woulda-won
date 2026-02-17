"""Tests for the analyze orchestrator."""

from unittest.mock import MagicMock, patch

import pytest
from core.analyze import AnalysisError, analyze_scoresheet
from core.parsers.base import PrelimsError


class TestPrelimsErrorHandling:
    def test_prelims_error_becomes_analysis_error(self):
        """PrelimsError from a parser should become AnalysisError with friendly message."""
        mock_parser = MagicMock()
        mock_parser.parse.side_effect = PrelimsError("prelims detected")

        with patch("core.analyze.detect_parser", return_value=mock_parser):
            with pytest.raises(AnalysisError, match="prelims scoresheet"):
                analyze_scoresheet("https://example.com/scores", b"content")

    def test_prelims_error_message_mentions_finals(self):
        """The error message should tell the user to use finals scoresheets."""
        mock_parser = MagicMock()
        mock_parser.parse.side_effect = PrelimsError("prelims detected")

        with patch("core.analyze.detect_parser", return_value=mock_parser):
            with pytest.raises(AnalysisError, match="finals scoresheets"):
                analyze_scoresheet("https://example.com/scores", b"content")

    def test_prelims_error_not_prefixed_with_failed_to_parse(self):
        """PrelimsError should NOT get the generic 'Failed to parse' prefix."""
        mock_parser = MagicMock()
        mock_parser.parse.side_effect = PrelimsError("prelims detected")

        with patch("core.analyze.detect_parser", return_value=mock_parser):
            with pytest.raises(AnalysisError) as exc_info:
                analyze_scoresheet("https://example.com/scores", b"content")
            assert "Failed to parse" not in str(exc_info.value)
