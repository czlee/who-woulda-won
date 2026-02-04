"""Shared fixtures for voting system tests."""

import pytest
from tests.conftest import make_scoresheet


@pytest.fixture
def clear_winner():
    """Dataset 1: Clear winner, 3 judges, 4 competitors.

         J1  J2  J3
    A     1   1   2
    B     2   3   1
    C     3   2   3
    D     4   4   4

    All systems should agree: A, B, C, D
    """
    return make_scoresheet("Clear Winner", {
        "J1": {"A": 1, "B": 2, "C": 3, "D": 4},
        "J2": {"A": 1, "B": 3, "C": 2, "D": 4},
        "J3": {"A": 2, "B": 1, "C": 3, "D": 4},
    })


@pytest.fixture
def disagreement():
    """Dataset 2: Systems disagree, 5 judges, 4 competitors.

         J1  J2  J3  J4  J5
    A     1   2   3   1   4
    B     2   1   4   3   1
    C     3   4   1   4   2
    D     4   3   2   2   3

    RP gives A, B, D, C. Others give A, B, C, D.
    """
    return make_scoresheet("Disagreement", {
        "J1": {"A": 1, "B": 2, "C": 3, "D": 4},
        "J2": {"A": 2, "B": 1, "C": 4, "D": 3},
        "J3": {"A": 3, "B": 4, "C": 1, "D": 2},
        "J4": {"A": 1, "B": 3, "C": 4, "D": 2},
        "J5": {"A": 4, "B": 1, "C": 2, "D": 3},
    })


@pytest.fixture
def unanimous():
    """Dataset 3: Unanimous judges, 3 judges, 3 competitors.

         J1  J2  J3
    A     1   1   1
    B     2   2   2
    C     3   3   3

    All systems: A, B, C
    """
    return make_scoresheet("Unanimous", {
        "J1": {"A": 1, "B": 2, "C": 3},
        "J2": {"A": 1, "B": 2, "C": 3},
        "J3": {"A": 1, "B": 2, "C": 3},
    })


@pytest.fixture
def two_competitors():
    """Dataset 4: Two competitors, 3 judges.

         J1  J2  J3
    A     1   2   1
    B     2   1   2

    All systems: A, B
    """
    return make_scoresheet("Two Competitors", {
        "J1": {"A": 1, "B": 2},
        "J2": {"A": 2, "B": 1},
        "J3": {"A": 1, "B": 2},
    })


@pytest.fixture
def perfect_cycle():
    """Dataset 5: Perfect cycle, 3 judges, 3 competitors.

         J1  J2  J3
    A     1   3   2
    B     2   1   3
    C     3   2   1

    Perfectly symmetric. All systems should include all 3 competitors.
    Exact order is implementation-dependent.
    """
    return make_scoresheet("Perfect Cycle", {
        "J1": {"A": 1, "B": 2, "C": 3},
        "J2": {"A": 3, "B": 1, "C": 2},
        "J3": {"A": 2, "B": 3, "C": 1},
    })
