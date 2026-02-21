"""Parser for eepro.com HTML pages."""

import re
from bs4 import BeautifulSoup

from core.models import Scoresheet
from core.parsers import register_parser
from core.parsers.base import ScoresheetParser


@register_parser
class EeproParser(ScoresheetParser):
    """Parser for eepro.com (Event Express Pro) competition results.

    eepro.com pages contain simple HTML tables, one per division.
    Each table has:
    - Header row with a single cell spanning the table width (division name)
    - Second row with column headers: Place, Competitor, [Judge Names], BIB, Marks Sorted
    - Data rows with placements

    Note: Pages may contain multiple divisions.

    Expected URL format:
        https://eepro.com/results/<slug>/<slug>.html
    """

    URL_PATTERN = re.compile(
        r"^https?://eepro\.com"
        r"/results/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+\.html$"
    )

    EXAMPLE_URL = "https://eepro.com/results/event-name/division-name.html"

    def can_parse(self, source: str) -> bool:
        """Check if this is a valid eepro.com results URL."""
        return bool(self.URL_PATTERN.match(source))

    def can_parse_content(self, content: bytes, filename: str) -> bool:
        """Check if this looks like an eepro.com HTML page.

        Tell-tale sign: The <title> tag contains "Event Express Pro".
        """
        try:
            html = content.decode("utf-8", errors="replace")
        except Exception:
            return False
        return "event express pro" in html.lower()

    def parse(self, source: str, content: bytes, division: str | None = None) -> Scoresheet:
        """Parse eepro.com HTML content into a Scoresheet.

        Args:
            source: URL or filename
            content: Raw HTML bytes
            division: Optional division name substring (case-insensitive).
                      If None and there is exactly one division, parses it.
                      If None and there are multiple divisions, raises an error
                      listing all available divisions.

        Returns:
            Scoresheet for the specified division.
        """
        html = content.decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "lxml")

        # Find all division tables. A division table has a first row
        # containing a single cell with a colspan (the division header).
        tables = soup.find_all("table")
        division_tables = []
        division_names = []

        for table in tables:
            first_row = table.find("tr")
            if not first_row:
                continue
            cells = first_row.find_all("td")
            if len(cells) == 1 and cells[0].get("colspan"):
                division_tables.append(table)
                name = cells[0].get_text(strip=True)
                if name.startswith("Division:"):
                    name = name[9:].strip()
                division_names.append(name)

        if not division_tables:
            raise ValueError("No division tables found in HTML")

        # Select the division
        if division is not None:
            # Find the first division whose name contains the search string
            division_lower = division.lower()
            match_index = None
            for i, name in enumerate(division_names):
                if division_lower in name.lower():
                    match_index = i
                    break

            if match_index is None:
                division_list = "\n".join(f"  - {name}" for name in division_names)
                raise ValueError(
                    f"No division matching \"{division}\" was found. "
                    f"Available divisions:\n{division_list}"
                )

            selected_index = match_index
        elif len(division_tables) == 1:
            selected_index = 0
        else:
            division_list = "\n".join(f"  - {name}" for name in division_names)
            raise ValueError(
                f"This page contains {len(division_tables)} divisions. "
                f"Please specify which division to analyse.\n\n"
                f"Available divisions:\n{division_list}"
            )

        # Get event name from page title or H2
        event_name = "Unknown Event"
        h2 = soup.find("h2")
        if h2:
            event_name = h2.get_text(strip=True)

        return self._parse_division_table(division_tables[selected_index], event_name)

    def _parse_division_table(self, table, event_name: str) -> Scoresheet:
        """Parse a single division table into a Scoresheet."""
        rows = table.find_all("tr")

        if len(rows) < 3:
            raise ValueError("Table has too few rows")

        # First row: division name
        division_row = rows[0]
        division_cell = division_row.find("td")
        division_name = division_cell.get_text(strip=True) if division_cell else "Unknown Division"

        # Clean up division name (remove "Division: " prefix)
        if division_name.startswith("Division:"):
            division_name = division_name[9:].strip()

        competition_name = f"{event_name} - {division_name}"

        # Second row: column headers
        header_row = rows[1]
        header_cells = header_row.find_all("td")

        # Expected: Place, Competitor, [Judges...], BIB, Marks Sorted
        # We need to identify which columns are judges
        headers = [cell.get_text(strip=True) for cell in header_cells]

        # Find judge columns (between Competitor and BIB)
        try:
            competitor_idx = next(i for i, h in enumerate(headers) if "competitor" in h.lower())
            bib_idx = next(i for i, h in enumerate(headers) if "bib" in h.lower())
        except StopIteration:
            raise ValueError(f"Could not find Competitor or BIB columns. Headers: {headers}")

        judge_indices = list(range(competitor_idx + 1, bib_idx))
        judges = [headers[i] for i in judge_indices]

        if not judges:
            raise ValueError("No judge columns found")

        # Parse data rows
        competitors = []
        rankings = {judge: {} for judge in judges}

        for row in rows[2:]:
            cells = row.find_all("td")
            if len(cells) < bib_idx:
                continue  # Skip malformed rows

            # Get competitor name
            competitor = cells[competitor_idx].get_text(strip=True)
            if not competitor:
                continue

            competitors.append(competitor)

            # Get judge placements
            for i, judge_idx in enumerate(judge_indices):
                if judge_idx < len(cells):
                    placement_text = cells[judge_idx].get_text(strip=True)
                    # Handle cases like "6-DQ" by extracting just the number
                    placement = self._extract_placement(placement_text)
                    rankings[judges[i]][competitor] = placement

        if not competitors:
            raise ValueError("No competitors found in table")

        return Scoresheet(
            competition_name=competition_name,
            competitors=competitors,
            judges=judges,
            rankings=rankings,
        )

    def _extract_placement(self, text: str) -> int:
        """Extract numeric placement from text, handling cases like '6-DQ'."""
        # Try to extract the first number
        match = re.match(r"(\d+)", text)
        if match:
            return int(match.group(1))
        return 0  # Default for unparseable placements

    def get_division_names(self, content: bytes) -> list[str]:
        """Get list of division names in the HTML content.

        Useful for letting users choose which division to parse.
        """
        html = content.decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "lxml")

        division_names = []
        for table in soup.find_all("table"):
            first_row = table.find("tr")
            if not first_row:
                continue
            cells = first_row.find_all("td")
            if len(cells) == 1 and cells[0].get("colspan"):
                name = cells[0].get_text(strip=True)
                if name.startswith("Division:"):
                    name = name[9:].strip()
                division_names.append(name)

        return division_names
