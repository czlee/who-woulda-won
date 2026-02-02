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

    Tiebreakers for elimination:
    1. Fewest votes at subsequent rank levels
    2. Lowest Borda score
    3. Random (or return as tied)
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
        self, candidates: set[str], scoresheet: Scoresheet
    ) -> tuple[str | list[str], list[dict]]:
        """Run IRV to find a single winner among candidates.

        Returns (winner, list of round details).
        Winner may be a list if there's an unresolvable tie.
        """
        active = set(candidates)
        m = scoresheet.num_judges
        majority_threshold = m // 2 + 1
        round_details = []

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

            round_info = {
                "round": round_num,
                "active_candidates": list(active),
                "votes": dict(first_place_votes),
                "majority_needed": majority_threshold,
            }

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
                winner = self._winner_tiebreak(list(active), scoresheet)
                round_info["all_tied"] = True
                round_info["winner"] = winner
                round_info["method"] = "all_tied_tiebreak"
                round_details.append(round_info)
                return winner, round_details

            # Break elimination tie if needed
            if len(to_eliminate) > 1:
                eliminated = self._elimination_tiebreak(
                    to_eliminate, scoresheet, active
                )
            else:
                eliminated = to_eliminate[0]

            round_info["eliminated"] = eliminated
            round_info["method"] = "elimination"
            round_details.append(round_info)

            active.remove(eliminated)

        # One candidate remaining
        winner = list(active)[0]
        return winner, round_details

    def _elimination_tiebreak(
        self, tied: list[str], scoresheet: Scoresheet, active: set[str]
    ) -> str:
        """Determine who to eliminate when multiple have same lowest vote count.

        Returns the candidate to eliminate.
        """
        # Tiebreaker 1: Fewest votes at each subsequent rank level
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

            if len(fewest) == 1:
                return fewest[0]

            tied = fewest

        # Tiebreaker 2: Lowest Borda score
        n = scoresheet.num_competitors
        borda = {
            c: sum(n - scoresheet.get_placement(j, c) for j in scoresheet.judges)
            for c in tied
        }
        min_borda = min(borda.values())
        fewest = [c for c in tied if borda[c] == min_borda]

        if len(fewest) == 1:
            return fewest[0]

        # Still tied - return first one (could randomize)
        return fewest[0]

    def _winner_tiebreak(
        self, tied: list[str], scoresheet: Scoresheet
    ) -> str | list[str]:
        """Break tie when determining winner (all candidates have equal votes).

        Returns winner or list of tied candidates if unresolvable.
        """
        # Use Borda as primary tiebreaker
        n = scoresheet.num_competitors
        borda = {
            c: sum(n - scoresheet.get_placement(j, c) for j in scoresheet.judges)
            for c in tied
        }
        max_borda = max(borda.values())
        best = [c for c in tied if borda[c] == max_borda]

        if len(best) == 1:
            return best[0]

        # Head-to-head among tied
        wins = {c: 0 for c in best}
        for i, a in enumerate(best):
            for b in best[i + 1:]:
                a_pref = sum(
                    1 for j in scoresheet.judges
                    if scoresheet.get_placement(j, a) < scoresheet.get_placement(j, b)
                )
                if a_pref > scoresheet.num_judges / 2:
                    wins[a] += 1
                elif a_pref < scoresheet.num_judges / 2:
                    wins[b] += 1

        max_wins = max(wins.values())
        best = [c for c in best if wins[c] == max_wins]

        if len(best) == 1:
            return best[0]

        # Unresolvable tie
        return best
