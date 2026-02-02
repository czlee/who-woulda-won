"""Voting systems for ranking competitors."""

from .base import VotingSystem

# Voting system registry - import systems here to register them
_voting_systems: list[type[VotingSystem]] = []


def register_voting_system(system_class: type[VotingSystem]) -> type[VotingSystem]:
    """Decorator to register a voting system class."""
    _voting_systems.append(system_class)
    return system_class


def get_all_voting_systems() -> list[VotingSystem]:
    """Return instances of all registered voting systems."""
    return [system_class() for system_class in _voting_systems]
