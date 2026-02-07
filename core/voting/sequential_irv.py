"""Sequential Instant Runoff Voting (IRV) system."""

from core.models import Scoresheet, VotingResult
from core.voting import register_voting_system
from core.voting.base import VotingSystem


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

    Tiebreakers (for both elimination and winner):
    1. Head-to-head (2 tied) or IRV among tied (3+)
    2. Fewest votes at subsequent rank levels (elimination) / Highest Borda (winner)
    3. Lowest Borda score (elimination) / Head-to-head wins (winner)
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
            first_place_votes = {c: 0 for c in active}

            for judge in scoresheet.judges:
                ranking = scoresheet.get_judge_ranking(judge)
                # Find this judge's top choice among active candidates
                for comp in ranking:
                    if comp in active:
                        first_place_votes[comp] += 1
                        break

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
                # Everyone tied - apply tiebreaker to find winner
                winner, tiebreak_info = self._winner_tiebreak(
                    list(active), scoresheet, tiebreak_depth
                )
                round_info["all_tied"] = True
                round_info["winner"] = winner
                round_info["method"] = "all_tied_tiebreak"
                round_info["tiebreak"] = tiebreak_info
                round_details.append(round_info)
                return winner, round_details

            # Break elimination tie if needed
            if len(to_eliminate) > 1:
                eliminated, tiebreak_info = self._elimination_tiebreak(
                    to_eliminate, scoresheet, active, tiebreak_depth
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
        self, tied: list[str], scoresheet: Scoresheet, active: set[str],
        depth: int = 0,
    ) -> tuple[str, dict]:
        """Determine who to eliminate when multiple have same lowest vote count.

        Returns (candidate_to_eliminate, tiebreak_details).
        """
        tiebreak_info = {
            "type": "elimination",
            "tied_candidates": list(tied),
            "steps": [],
        }

        # Tiebreaker 1: Head-to-head / IRV among tied (only at depth 0)
        if depth == 0:
            if len(tied) == 2:
                # Head-to-head between the two
                h2h = self._head_to_head(tied[0], tied[1], scoresheet)
                step = {
                    "method": "head_to_head",
                    "head_to_head": h2h,
                }
                if h2h["winner"] is not None:
                    # The loser of h2h is eliminated
                    loser = tied[1] if h2h["winner"] == tied[0] else tied[0]
                    step["resolved"] = True
                    step["eliminated"] = loser
                    tiebreak_info["steps"].append(step)
                    return loser, tiebreak_info
                else:
                    step["resolved"] = False
                    tiebreak_info["steps"].append(step)
            else:
                # 3+ tied: run sub-IRV among tied
                sub_winner, sub_rounds = self._run_irv(
                    set(tied), scoresheet, tiebreak_depth=depth + 1
                )
                step = {
                    "method": "irv",
                    "irv_rounds": sub_rounds,
                    "irv_winner": sub_winner,
                }

                # Find the first eliminated candidate in sub-IRV rounds
                first_eliminated = None
                for rd in sub_rounds:
                    if rd.get("eliminated"):
                        first_eliminated = rd["eliminated"]
                        break

                if first_eliminated is not None:
                    step["resolved"] = True
                    step["eliminated"] = first_eliminated
                    tiebreak_info["steps"].append(step)
                    return first_eliminated, tiebreak_info

                # No elimination round. Check single zero-vote exclusion.
                for rd in sub_rounds:
                    excluded = rd.get("excluded_zero_vote", [])
                    if len(excluded) == 1:
                        first_eliminated = excluded[0]
                        break

                if first_eliminated is not None:
                    step["resolved"] = True
                    step["eliminated"] = first_eliminated
                    tiebreak_info["steps"].append(step)
                    return first_eliminated, tiebreak_info

                # Sub-IRV didn't produce a clear weakest candidate.
                # Remove the winner (strongest) from tied list.
                if isinstance(sub_winner, str):
                    tied = [c for c in tied if c != sub_winner]
                    if len(tied) == 1:
                        step["resolved"] = True
                        step["eliminated"] = tied[0]
                        tiebreak_info["steps"].append(step)
                        return tied[0], tiebreak_info

                step["resolved"] = False
                tiebreak_info["steps"].append(step)

        # Tiebreaker 2: Fewest votes at each subsequent rank level
        for rank in range(2, len(active) + 1):
            rank_counts = {c: 0 for c in tied}

            for judge in scoresheet.judges:
                ranking = scoresheet.get_judge_ranking(judge)
                # Find this judge's nth choice among active candidates
                count = 0
                for comp in ranking:
                    if comp in active:
                        count += 1
                        if count == rank and comp in tied:
                            rank_counts[comp] += 1
                            break

            min_count = min(rank_counts.values())
            fewest = [c for c in tied if rank_counts[c] == min_count]

            step = {
                "method": "rank_counts",
                "rank": rank,
                "counts": dict(rank_counts),
            }

            if len(fewest) == 1:
                step["resolved"] = True
                step["eliminated"] = fewest[0]
                tiebreak_info["steps"].append(step)
                return fewest[0], tiebreak_info
            else:
                step["resolved"] = False
                step["remaining_tied"] = list(fewest)
                tiebreak_info["steps"].append(step)

            tied = fewest

        # Tiebreaker 3: Lowest Borda score
        n = scoresheet.num_competitors
        borda = {
            c: sum(n - scoresheet.get_placement(j, c) for j in scoresheet.judges)
            for c in tied
        }
        min_borda = min(borda.values())
        fewest = [c for c in tied if borda[c] == min_borda]

        step = {
            "method": "borda",
            "scores": dict(borda),
        }

        if len(fewest) == 1:
            step["resolved"] = True
            step["eliminated"] = fewest[0]
            tiebreak_info["steps"].append(step)
            return fewest[0], tiebreak_info
        else:
            step["resolved"] = False
            step["remaining_tied"] = list(fewest)
            tiebreak_info["steps"].append(step)

        # Still tied - return first one (could randomize)
        step = {
            "method": "unresolved",
            "remaining_tied": list(fewest),
            "eliminated": fewest[0],
        }
        tiebreak_info["steps"].append(step)
        return fewest[0], tiebreak_info

    def _winner_tiebreak(
        self, tied: list[str], scoresheet: Scoresheet,
        depth: int = 0,
    ) -> tuple[str | list[str], dict]:
        """Break tie when determining winner (all candidates have equal votes).

        Returns (winner_or_tied_list, tiebreak_details).
        """
        tiebreak_info = {
            "type": "winner",
            "tied_candidates": list(tied),
            "steps": [],
        }

        # Tiebreaker 1: Head-to-head / IRV among tied (only at depth 0)
        if depth == 0:
            if len(tied) == 2:
                h2h = self._head_to_head(tied[0], tied[1], scoresheet)
                step = {
                    "method": "head_to_head",
                    "head_to_head": h2h,
                }
                if h2h["winner"] is not None:
                    step["resolved"] = True
                    step["winner"] = h2h["winner"]
                    tiebreak_info["steps"].append(step)
                    return h2h["winner"], tiebreak_info
                else:
                    step["resolved"] = False
                    tiebreak_info["steps"].append(step)
            else:
                # 3+ tied: run sub-IRV
                sub_winner, sub_rounds = self._run_irv(
                    set(tied), scoresheet, tiebreak_depth=depth + 1
                )
                step = {
                    "method": "irv",
                    "irv_rounds": sub_rounds,
                    "irv_winner": sub_winner,
                }
                if isinstance(sub_winner, str):
                    step["resolved"] = True
                    step["winner"] = sub_winner
                    tiebreak_info["steps"].append(step)
                    return sub_winner, tiebreak_info
                else:
                    # Sub-IRV returned tied list - narrow tied list
                    step["resolved"] = False
                    tiebreak_info["steps"].append(step)
                    tied = list(sub_winner)

        # Tiebreaker 2: Borda scoring
        n = scoresheet.num_competitors
        borda = {
            c: sum(n - scoresheet.get_placement(j, c) for j in scoresheet.judges)
            for c in tied
        }
        max_borda = max(borda.values())
        best = [c for c in tied if borda[c] == max_borda]

        step = {
            "method": "borda",
            "scores": dict(borda),
        }

        if len(best) == 1:
            step["resolved"] = True
            step["winner"] = best[0]
            tiebreak_info["steps"].append(step)
            return best[0], tiebreak_info
        else:
            step["resolved"] = False
            step["remaining_tied"] = list(best)
            tiebreak_info["steps"].append(step)

        # Tiebreaker 3: Head-to-head wins among Borda-tied
        wins = {c: 0 for c in best}
        matchups = []
        for i, a in enumerate(best):
            for b in best[i + 1:]:
                h2h = self._head_to_head(a, b, scoresheet)
                matchups.append(h2h)
                if h2h["winner"] == a:
                    wins[a] += 1
                elif h2h["winner"] == b:
                    wins[b] += 1

        max_wins = max(wins.values())
        best = [c for c in best if wins[c] == max_wins]

        step = {
            "method": "head_to_head_wins",
            "matchups": matchups,
            "wins": dict(wins),
        }

        if len(best) == 1:
            step["resolved"] = True
            step["winner"] = best[0]
            tiebreak_info["steps"].append(step)
            return best[0], tiebreak_info
        else:
            step["resolved"] = False
            step["remaining_tied"] = list(best)
            tiebreak_info["steps"].append(step)

        # Unresolvable tie
        step = {
            "method": "unresolved",
            "remaining_tied": list(best),
        }
        tiebreak_info["steps"].append(step)
        return best, tiebreak_info
