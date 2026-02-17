"""Parser for scoring.dance HTML pages."""

import json
import re
from bs4 import BeautifulSoup

from core.models import Scoresheet
from core.parsers import register_parser
from core.parsers.base import PrelimsError, ScoresheetParser


@register_parser
class ScoringDanceParser(ScoresheetParser):
    """Parser for scoring.dance competition results.

    scoring.dance pages contain embedded JSON-LD with structured data,
    making parsing straightforward. We look for the DanceEvent JSON-LD
    block that contains judges_placements.

    Expected URL format:
        https://scoring.dance/events/<number>/results/<number>.html
        https://scoring.dance/<lang>/events/<number>/results/<number>.html

    where <lang> is a language code like "en", "enUS", "frFR", "zhCN",
    or "en-US" (2-letter language, optionally followed by 2-letter country
    code with or without a hyphen).
    """

    URL_PATTERN = re.compile(
        r"^https?://scoring\.dance"
        r"(/[a-z]{2}(-?[A-Z]{2})?)?"  # optional language(+country), e.g. /en, /enUS, /en-US
        r"/events/\d+"
        r"/results/\d+\.html$"
    )

    EXAMPLE_URL = "https://scoring.dance/events/123/results/456.html"

    def can_parse(self, source: str) -> bool:
        """Check if this is a valid scoring.dance results URL."""
        return bool(self.URL_PATTERN.match(source))

    def can_parse_content(self, content: bytes, filename: str) -> bool:
        """Check if this looks like a scoring.dance HTML page.

        Tell-tale sign: JSON-LD script block with @type DanceEvent
        and judges_placements data.
        """
        try:
            html = content.decode("utf-8", errors="replace")
        except Exception:
            return False
        return (
            "application/ld+json" in html
            and '"DanceEvent"' in html
        )

    def parse(self, source: str, content: bytes) -> Scoresheet:
        """Parse scoring.dance HTML content into a Scoresheet."""
        html = content.decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "lxml")

        # Find JSON-LD scripts
        json_ld_scripts = soup.find_all("script", {"type": "application/ld+json"})

        event_data = None
        has_dance_event = False
        for script in json_ld_scripts:
            try:
                data = json.loads(script.string)
                if data.get("@type") == "DanceEvent":
                    has_dance_event = True
                    results = data.get("result", [])
                    if results and "judges_placements" in results[0]:
                        event_data = data
                        break
            except (json.JSONDecodeError, TypeError):
                continue

        if event_data is None:
            if has_dance_event:
                raise PrelimsError(
                    "This looks like a prelims scoresheet from scoring.dance."
                )
            raise ValueError(
                "Could not find DanceEvent JSON-LD with judges_placements in HTML"
            )

        return self._parse_json_ld(event_data)

    def _parse_json_ld(self, data: dict) -> Scoresheet:
        """Parse the DanceEvent JSON-LD into a Scoresheet."""
        # Extract competition name
        event_name = data.get("name", "Unknown Event")
        round_info = data.get("round", {})
        round_name = round_info.get("name", "") if isinstance(round_info, dict) else ""
        competition_name = f"{event_name} - {round_name}" if round_name else event_name

        results = data.get("result", [])
        if not results:
            raise ValueError("No results found in JSON-LD data")

        # Extract judges from the first result's judges_placements
        first_result = results[0]
        judges_placements = first_result.get("judges_placements", [])
        judges = [jp.get("name", f"Judge {i+1}") for i, jp in enumerate(judges_placements)]

        # Extract competitors and build rankings
        competitors = []
        rankings = {judge: {} for judge in judges}

        for result in results:
            dancer = result.get("dancer", {})

            # Build competitor name from leader and follower
            leader = dancer.get("leader", {})
            follower = dancer.get("follower", {})
            leader_name = leader.get("fullname", "Unknown Leader")
            follower_name = follower.get("fullname", "Unknown Follower")
            competitor = f"{leader_name} & {follower_name}"
            competitors.append(competitor)

            # Extract placements from each judge
            result_placements = result.get("judges_placements", [])
            for i, jp in enumerate(result_placements):
                if i < len(judges):
                    judge = judges[i]
                    placement_str = jp.get("placement", "0")
                    try:
                        placement = int(placement_str)
                    except ValueError:
                        placement = 0
                    rankings[judge][competitor] = placement

        # Validate that we have complete data
        if not competitors:
            raise ValueError("No competitors found in results")
        if not judges:
            raise ValueError("No judges found in results")

        return Scoresheet(
            competition_name=competition_name,
            competitors=competitors,
            judges=judges,
            rankings=rankings,
        )
