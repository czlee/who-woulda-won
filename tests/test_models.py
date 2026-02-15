"""Tests for core data models."""

from core.models import Placement


class TestBuildRanking:
    def test_no_ties(self):
        result = Placement.build_ranking(["A", "B", "C"])
        assert [(p.name, p.rank, p.tied) for p in result] == [
            ("A", 1, False),
            ("B", 2, False),
            ("C", 3, False),
        ]

    def test_tie_in_middle(self):
        result = Placement.build_ranking(["A", ["B", "C"], "D"])
        assert [(p.name, p.rank, p.tied) for p in result] == [
            ("A", 1, False),
            ("B", 2, True),
            ("C", 2, True),
            ("D", 4, False),
        ]

    def test_tie_at_start(self):
        result = Placement.build_ranking([["A", "B"], "C"])
        assert [(p.name, p.rank, p.tied) for p in result] == [
            ("A", 1, True),
            ("B", 1, True),
            ("C", 3, False),
        ]

    def test_tie_at_end(self):
        result = Placement.build_ranking(["A", ["B", "C"]])
        assert [(p.name, p.rank, p.tied) for p in result] == [
            ("A", 1, False),
            ("B", 2, True),
            ("C", 2, True),
        ]

    def test_multiple_ties(self):
        result = Placement.build_ranking([["A", "B"], "C", ["D", "E"]])
        assert [(p.name, p.rank, p.tied) for p in result] == [
            ("A", 1, True),
            ("B", 1, True),
            ("C", 3, False),
            ("D", 4, True),
            ("E", 4, True),
        ]

    def test_three_way_tie(self):
        result = Placement.build_ranking(["A", ["B", "C", "D"], "E"])
        assert [(p.name, p.rank, p.tied) for p in result] == [
            ("A", 1, False),
            ("B", 2, True),
            ("C", 2, True),
            ("D", 2, True),
            ("E", 5, False),
        ]

    def test_all_tied(self):
        result = Placement.build_ranking([["A", "B", "C"]])
        assert [(p.name, p.rank, p.tied) for p in result] == [
            ("A", 1, True),
            ("B", 1, True),
            ("C", 1, True),
        ]

    def test_single_competitor(self):
        result = Placement.build_ranking(["A"])
        assert [(p.name, p.rank, p.tied) for p in result] == [
            ("A", 1, False),
        ]

    def test_empty(self):
        result = Placement.build_ranking([])
        assert result == []

    def test_to_dict(self):
        result = Placement.build_ranking(["A", ["B", "C"]])
        assert [p.to_dict() for p in result] == [
            {"name": "A", "rank": 1, "tied": False},
            {"name": "B", "rank": 2, "tied": True},
            {"name": "C", "rank": 2, "tied": True},
        ]
