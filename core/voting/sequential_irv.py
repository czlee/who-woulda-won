"""Sequential Instant Runoff Voting (IRV) system."""

import random

from core.models import Scoresheet, VotingResult
from core.voting import register_voting_system
from core.voting.base import VotingSystem


MAX_TIEBREAK_DEPTH = 5


@register_voting_system
class SequentialIRVSystem(VotingSystem):
    """Sequential Instant Runoff Voting system.

    Runs IRV repeatedly to produce a full ranking:
    1. Run IRV to find the winner (1st place)
    2. Remove the winner from consideration
    3. Run IRV again to find 2nd place
    4. Repeat until all positions are filled

    For each IRV round:
    1. Count first-choice votes among remaining candidates
    2. If someone has a majority (>50%), they win
    3. Otherwise, eliminate the candidate with fewest votes and redistribute
    4. Repeat until a majority winner emerges

    Tiebreakers:
    - Elimination: Head-to-head (2 tied), or restricted vote counting
      among tied candidates (3+), narrowing the tied set until resolved.
    - If all candidates are tied, count second-choice votes, and so on,
      until the candidates are not all tied.
    - If still unresolved, choose at random.
    """

    @property
    def name(self) -> str:
        return "Sequential IRV"

    @property
    def description(self) -> str:
        return "Run Instant Runoff Voting repeatedly: find winner, remove, repeat"

    def calculate(self, scoresheet: Scoresheet) -> VotingResult:
        final_ranking = []
        remaining = set(scoresheet.competitors)
        placement_rounds = []

        place = 1
        while remaining:
            if len(remaining) == 1:
                winner = remaining.pop()
                final_ranking.append(winner)
                placement_rounds.append({
                    "place": place,
                    "winner": winner,
                    "method": "last_remaining",
                    "irv_rounds": [],
                })
                break

            winner, irv_details = self._run_irv(remaining, scoresheet)

            placement_rounds.append({
                "place": place,
                "winner": winner,
                "irv_rounds": irv_details,
            })

            if isinstance(winner, list):
                # Tie - add all tied competitors
                for w in winner:
                    final_ranking.append(w)
                    remaining.discard(w)
                place += len(winner)
            else:
                final_ranking.append(winner)
                remaining.discard(winner)
                place += 1

        return VotingResult(
            system_name=self.name,
            final_ranking=final_ranking,
            details={
                "placement_rounds": placement_rounds,
            },
        )

    def _count_votes(self, scoresheet: Scoresheet, among: set[str], choice: int = 1) -> dict[str, int]:
        votes = {c: 0 for c in among}
        assert choice <= len(among)

        for judge in scoresheet.judges:
            ranking = scoresheet.get_judge_ranking(judge)
            found = 0
            for comp in ranking:
                if comp in among:
                    found += 1
                    if found == choice:
                        votes[comp] += 1
                        break

        return votes

    def _run_irv(
        self, candidates: set[str], scoresheet: Scoresheet,
        tiebreak_depth: int = 0,
    ) -> tuple[str | list[str], list[dict]]:
        """Run IRV to find a single winner among candidates.

        Returns (winner, list of round details).
        Winner may be a list if there's an unresolvable tie.
        """
        active = set(candidates)
        m = scoresheet.num_judges
        majority_threshold = m // 2 + 1
        round_details = []
        excluded_zero_vote: list[str] = []

        round_num = 0
        while len(active) > 1:
            round_num += 1

            # Count first-choice votes among active candidates
            first_place_votes = self._count_votes(scoresheet, active)

            # In round 1, exclude candidates with zero first-choice votes.
            # They would be eliminated one-by-one without affecting vote
            # counts, so removing them all at once is equivalent.
            if round_num == 1:
                zero_vote = [c for c in active if first_place_votes[c] == 0]
                if zero_vote and len(zero_vote) < len(active):
                    excluded_zero_vote = sorted(zero_vote)
                    for c in zero_vote:
                        active.discard(c)
                        del first_place_votes[c]

                    # If only one remains after excluding zero-vote, they win
                    if len(active) == 1:
                        winner = list(active)[0]
                        round_info = {
                            "round": round_num,
                            "active_candidates": list(active),
                            "votes": dict(first_place_votes),
                            "majority_needed": majority_threshold,
                            "excluded_zero_vote": excluded_zero_vote,
                            "winner": winner,
                            "method": "majority",
                        }
                        round_details.append(round_info)
                        return winner, round_details

            round_info = {
                "round": round_num,
                "active_candidates": list(active),
                "votes": dict(first_place_votes),
                "majority_needed": majority_threshold,
            }

            if round_num == 1 and excluded_zero_vote:
                round_info["excluded_zero_vote"] = excluded_zero_vote

            # Check for majority winner
            for comp in active:
                if first_place_votes[comp] >= majority_threshold:
                    round_info["winner"] = comp
                    round_info["method"] = "majority"
                    round_details.append(round_info)
                    return comp, round_details

            # No majority - find candidate(s) to eliminate
            min_votes = min(first_place_votes.values())
            to_eliminate = [c for c in active if first_place_votes[c] == min_votes]

            if len(to_eliminate) == len(active):
                # Everyone tied - look at second-choice votes, and so on.
                for choice in range(2, len(active)):
                    nth_place_votes = self._count_votes(scoresheet, active, choice)
                    min_nth_place_votes = min(nth_place_votes.values())
                    nth_place_fewest = [c for c in active if nth_place_votes[c] == min_nth_place_votes]
                    if len(nth_place_fewest) < len(active):
                        to_eliminate = nth_place_fewest
                        round_info["tiebreak_choice"] = choice
                        break

                else:
                    # Perfect tie - declare all equal
                    round_info["all_tied"] = True
                    round_info["winner"] = list(active)
                    round_info["method"] = "all_tied_equal"
                    round_details.append(round_info)
                    return list(active), round_details

            # Break elimination tie if needed
            if len(to_eliminate) > 1:
                eliminated, tiebreak_info = self._elimination_tiebreak(
                    to_eliminate, scoresheet
                )
                round_info["tiebreak"] = tiebreak_info
            else:
                eliminated = to_eliminate[0]

            round_info["eliminated"] = eliminated
            round_info["method"] = "elimination"
            round_details.append(round_info)

            active.remove(eliminated)

        # One candidate remaining
        winner = list(active)[0]
        return winner, round_details

    def _head_to_head(
        self, a: str, b: str, scoresheet: Scoresheet
    ) -> dict:
        """Compute head-to-head result between two candidates.

        Returns dict with candidates, counts, and winner (None if tied).
        """
        a_pref = sum(
            1 for j in scoresheet.judges
            if scoresheet.get_placement(j, a) < scoresheet.get_placement(j, b)
        )
        b_pref = scoresheet.num_judges - a_pref

        result = {
            "candidates": [a, b],
            "counts": {a: a_pref, b: b_pref},
        }
        if a_pref > b_pref:
            result["winner"] = a
        elif b_pref > a_pref:
            result["winner"] = b
        else:
            result["winner"] = None
        return result

    def _elimination_tiebreak(
        self, tied: list[str], scoresheet: Scoresheet,
    ) -> tuple[str, dict]:
        """Determine who to eliminate when multiple have same lowest vote count.

        Tiebreak procedure:
        1. Two tied → head-to-head comparison.
        2. Three or more tied → count first-choice votes restricted to only
           the tied candidates. If one has fewest, eliminate. If multiple
           tied for fewest (but not all), narrow and repeat. If all equal,
           fall back to random.

        Returns (candidate_to_eliminate, tiebreak_details).
        """
        tiebreak_info = {
            "type": "elimination",
            "tied_candidates": list(tied),
            "steps": [],
        }

        while len(tied) > 1:
            if len(tied) == 2:
                # Head-to-head between the two
                h2h = self._head_to_head(tied[0], tied[1], scoresheet)
                step = {
                    "method": "head_to_head",
                    "head_to_head": h2h,
                }
                if h2h["winner"] is not None:
                    loser = tied[1] if h2h["winner"] == tied[0] else tied[0]
                    step["resolved"] = True
                    step["eliminated"] = loser
                    tiebreak_info["steps"].append(step)
                    return loser, tiebreak_info
                else:
                    step["resolved"] = False
                    tiebreak_info["steps"].append(step)
                    break  # h2h tied → fall through to random

            # 3+ tied: count first-choice votes restricted to tied candidates
            votes = self._count_votes(scoresheet, set(tied))

            min_votes = min(votes.values())
            fewest = [c for c in tied if votes[c] == min_votes]

            step = {
                "method": "restricted_vote",
                "votes": dict(votes),
            }

            if len(fewest) == len(tied):
                # All have equal votes — can't narrow further
                step["resolved"] = False
                step["all_equal"] = True
                tiebreak_info["steps"].append(step)
                break  # fall through to random

            if len(fewest) == 1:
                step["resolved"] = True
                step["eliminated"] = fewest[0]
                tiebreak_info["steps"].append(step)
                return fewest[0], tiebreak_info

            # Multiple tied for fewest, but not all — narrow and continue
            step["resolved"] = False
            step["remaining_tied"] = list(fewest)
            tiebreak_info["steps"].append(step)
            tied = fewest

        # Fallback: choose at random
        eliminated = random.choice(tied)
        step = {
            "method": "random",
            "remaining_tied": list(tied),
            "eliminated": eliminated,
        }
        tiebreak_info["steps"].append(step)
        return eliminated, tiebreak_info
