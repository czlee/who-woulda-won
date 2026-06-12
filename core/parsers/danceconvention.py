"""Parser for danceconvention.net PDF scoresheets."""

import re
from io import BytesIO

import pdfplumber

from core.models import Scoresheet
from core.parsers import register_parser
from core.parsers.base import PrelimsError, ScoresheetParser, _common_word_prefix, _get_division_core


@register_parser
class DanceConventionParser(ScoresheetParser):
    """Parser for danceconvention.net PDF scoresheets.

    These PDFs have:
    - Title and event name at the top
    - Judge key showing initials -> full names
    - Table with columns: #, Name, [Judge initials], [cumulative counts], Result, Remarks
    - Names show leader and follower on separate lines within the same cell

    Expected URL format:
        https://danceconvention.net/eventdirector/<lang>/roundscores/<number>.pdf
    """

    URL_PATTERN = re.compile(
        r"^https?://danceconvention\.net"
        r"/eventdirector/[a-z]{2}/roundscores/\d+\.pdf$"
    )

    EXAMPLE_URL = "https://danceconvention.net/eventdirector/en/roundscores/123.pdf"

    def can_parse(self, source: str) -> bool:
        """Check if this is a valid danceconvention.net scoresheet URL."""
        return bool(self.URL_PATTERN.match(source))

    def can_parse_content(self, content: bytes, filename: str) -> bool:
        """Check if this looks like a danceconvention.net PDF scoresheet.

        Tell-tale signs:
        - File is a PDF (starts with %PDF magic bytes)
        - Contains a judge key (uppercase initials followed by names)
        - Contains a results table with a # column
        """
        if not content.startswith(b"%PDF"):
            return False

        try:
            pdf_file = BytesIO(content)
            with pdfplumber.open(pdf_file) as pdf:
                if not pdf.pages:
                    return False

                # Check first page text for judge key pattern
                text = pdf.pages[0].extract_text() or ""
                has_judge_key = bool(self._extract_judge_key(text))

                # Check tables for a # column header
                tables = pdf.pages[0].extract_tables()
                has_results_table = False
                for table in (tables or []):
                    if table and table[0] and self._is_results_header(table[0]):
                        has_results_table = True
                        break

                return has_judge_key and has_results_table
        except Exception:
            return False

    def parse(self, source: str, content: bytes, division: str | None = None) -> Scoresheet:
        """Parse danceconvention.net PDF content into a Scoresheet."""
        pdf_file = BytesIO(content)

        with pdfplumber.open(pdf_file) as pdf:
            if not pdf.pages:
                raise ValueError("PDF has no pages")

            sections, nonfinals_tables = self._split_into_sections(pdf.pages)

        if not sections:
            if nonfinals_tables:
                self._check_if_prelims(nonfinals_tables)  # raises PrelimsError if appropriate
            raise ValueError("No tables found in PDF")

        if len(sections) == 1:
            competition_name, all_text, all_tables = sections[0]
        elif division is None:
            division_list = "\n".join(f"  - {s[0]}" for s in sections)
            raise ValueError(
                f"This PDF contains {len(sections)} competitions. "
                f"Please specify which competition to analyse.\n\n"
                f"Available competitions:\n{division_list}"
            )
        else:
            competition_name, all_text, all_tables = self._select_section(sections, division)

        judge_key = self._extract_judge_key(all_text)
        return self._parse_results_table(all_tables, competition_name, judge_key)

    def _get_page_section_name(self, text: str) -> str | None:
        """Detect whether a page starts a new competition section.

        Continuation pages begin their extracted text with the table column
        header row ("# Name ...") or a data row (leading digit). All other
        pages are treated as the start of a new competition section.
        Returns the competition name, or None for continuation pages.
        """
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if not lines or lines[0].startswith("#") or lines[0][:1].isdigit():
            return None
        return self._extract_competition_name(text)

    def _split_into_sections(
        self, pages
    ) -> tuple[list[tuple[str, str, list]], list]:
        """Split PDF pages into competition sections.

        Returns:
          - sections: list of (competition_name, all_text, finals_tables),
            one per competition found (only sections that have finals tables)
          - nonfinals_results_tables: all results tables lacking cumulative
            columns, for use in prelims detection when no finals are found
        """
        sections: list[list] = []  # each entry: [name, text, finals_tables]
        current: list | None = None
        nonfinals_results_tables: list = []

        for page in pages:
            text = page.extract_text() or ""
            page_tables = page.extract_tables() or []

            results_tables = [
                t for t in page_tables
                if t and len(t) >= 2 and self._is_results_header(t[0])
            ]
            finals_tables = [
                t for t in results_tables if self._has_cumulative_columns(t[0])
            ]
            nonfinals_results_tables.extend(
                t for t in results_tables if not self._has_cumulative_columns(t[0])
            )

            section_name = self._get_page_section_name(text)

            if section_name is not None and (
                current is None or section_name != current[0]
            ):
                current = [section_name, text, []]
                sections.append(current)
            elif current is not None:
                current[1] += "\n" + text
            else:
                # First page has no recognisable header — still start a section
                name = self._extract_competition_name(text)
                current = [name, text, []]
                sections.append(current)

            current[2].extend(finals_tables)

        sections_with_finals = [(s[0], s[1], s[2]) for s in sections if s[2]]
        return sections_with_finals, nonfinals_results_tables

    def _select_section(
        self, sections: list[tuple[str, str, list]], division: str
    ) -> tuple[str, str, list]:
        """Select a competition section by fuzzy-matching the division string.

        Four-tier match against the core (common prefix and round suffix stripped),
        case-insensitive:
          1. Exact core match
          2. Core starts with search term
          3. Search term is substring of core
          4. Search term is substring of full name (for queries that include the prefix)
        If multiple sections match at the same tier, raises a ValueError.
        """
        division_lower = division.lower()
        names = [s[0] for s in sections]
        prefix = _common_word_prefix(names)
        candidates: list[tuple[int, int]] = []  # (tier, index)

        for i, (name, _, _) in enumerate(sections):
            core = _get_division_core(name, prefix)
            name_lower = name.lower()
            if core == division_lower:
                tier = 1
            elif core.startswith(division_lower):
                tier = 2
            elif division_lower in core:
                tier = 3
            elif division_lower in name_lower:
                tier = 4
            else:
                continue
            candidates.append((tier, i))

        if not candidates:
            division_list = "\n".join(f"  - {s[0]}" for s in sections)
            raise ValueError(
                f"No competition matching \"{division}\" was found. "
                f"Available competitions:\n{division_list}"
            )

        best_tier = min(t for t, _ in candidates)
        best_candidates = [i for t, i in candidates if t == best_tier]

        if len(best_candidates) > 1:
            matched_list = "\n".join(f"  - {sections[i][0]}" for i in best_candidates)
            raise ValueError(
                f"Multiple competitions match \"{division}\". Please be more specific.\n\n"
                f"Matching competitions:\n{matched_list}"
            )

        return sections[best_candidates[0]]

    def _extract_competition_name(self, text: str) -> str:
        """Extract competition name from PDF text."""
        lines = text.strip().split("\n")

        # Usually first two non-empty lines are title and event name
        title_parts = []
        for line in lines[:5]:
            line = line.strip()
            if line and not line.startswith("Score legend"):
                title_parts.append(line)
            if len(title_parts) >= 2:
                break

        if title_parts:
            return " - ".join(title_parts)
        return "Unknown Competition"

    @staticmethod
    def _is_results_header(header: list) -> bool:
        """Check if a table header row looks like a results table.

        Checks that "#" appears in one of the first two columns, which is
        a language-independent marker for the competitor number column.
        """
        for cell in header[:2]:
            if cell and str(cell).strip() == "#":
                return True
        return False

    @staticmethod
    def _has_cumulative_columns(header: list) -> bool:
        """Check if the header contains cumulative tally columns (1-1, 1-2, etc.).

        Main results tables have these columns; tiebreak tables do not.
        """
        return any(
            cell and str(cell).strip().startswith("1-")
            for cell in header
        )

    def _check_if_prelims(self, tables: list) -> None:
        """Check tables without cumulative columns for prelims characteristics.

        Called when no finals (1-N column) tables are found. Raises PrelimsError
        if the judge values look like callback scores (0/10/alternates).
        """
        header = tables[0][0]
        col_indices = self._find_column_indices(header)
        judge_start = col_indices["judge_start"]
        judge_end = col_indices["judge_end"]

        all_judge_values = []
        for table in tables:
            for row in table[1:]:
                for col_idx in range(judge_start, judge_end):
                    if col_idx < len(row) and row[col_idx]:
                        all_judge_values.append(str(row[col_idx]).strip())

        if all_judge_values and self._looks_like_callbacks(all_judge_values):
            raise PrelimsError(
                "This looks like a prelims scoresheet from danceconvention.net."
            )

    @staticmethod
    def _is_judge_initials(s: str) -> bool:
        """Check if a string looks like judge initials (2-4 alphanumeric chars).

        Initials can be mixed case (e.g. "IPz") and any script (e.g. "КП").
        """
        return 2 <= len(s) <= 4 and s.isalnum()

    def _extract_judge_key(self, text: str) -> dict[str, str]:
        """Extract judge initials -> full name mapping from text.

        Looks for lines like "AG Alexis Garrish" or "КП Павел Катунин":
        2-4 uppercase initials followed by at least two alphabetic name words.
        Uses Unicode-aware checks so this works for any script.
        """
        judge_key = {}

        for line in text.split("\n"):
            words = line.strip().split()
            if len(words) < 3:
                continue
            initials = words[0]
            if not self._is_judge_initials(initials):
                continue
            # All remaining words should be alphabetic (any script), which
            # excludes lines with numbers or punctuation.
            name_parts = words[1:]
            if all(w.isalpha() for w in name_parts):
                judge_key[initials] = " ".join(name_parts)

        return judge_key

    def _parse_results_table(
        self,
        tables: list[list[list[str]]],
        competition_name: str,
        judge_key: dict[str, str],
    ) -> Scoresheet:
        """Parse the main results table."""
        # Find all tables with results (identified by a # column in the header).
        # Multi-page PDFs have a continuation table on each page with the same
        # header row, so we merge data rows from all of them.
        all_results_tables = []
        for table in tables:
            if not table or len(table) < 2:
                continue
            header = table[0]
            if header and self._is_results_header(header):
                all_results_tables.append(table)

        if not all_results_tables:
            raise ValueError("Could not find results table in PDF")

        # Finals scoresheets have cumulative tally columns (1-1, 1-2, ...).
        # Tiebreak tables on page 2 do not, so if any table has cumulative
        # columns, restrict to those to exclude tiebreak tables.
        # Prelims scoresheets also lack cumulative columns: pass them off to
        # a dedicated checker that raises PrelimsError if appropriate.
        results_tables = [
            t for t in all_results_tables if self._has_cumulative_columns(t[0])
        ]
        if not results_tables:
            self._check_if_prelims(all_results_tables)
            raise ValueError("Could not find finals results table in PDF")

        # Use the header from the first table for column detection
        header = results_tables[0][0]

        # Find column indices
        col_indices = self._find_column_indices(header)
        name_idx = col_indices["name"]
        judge_start = col_indices["judge_start"]
        judge_end = col_indices["judge_end"]

        # Extract judge initials from header (position determines which
        # columns are judges, so we just need non-empty cells)
        judge_initials = []
        for i in range(judge_start, judge_end):
            if i < len(header) and header[i]:
                judge_initials.append(str(header[i]).strip())

        if not judge_initials:
            raise ValueError("Could not find judge columns in table header")

        # Use full names if available, otherwise use initials
        judges = [judge_key.get(init, init) for init in judge_initials]

        # Collect data rows from all finals tables
        number_idx = col_indices["number"]
        parsed_rows = []  # (bib_number, competitor_name, [(col_idx, initials, value_str)])

        for results_table in results_tables:
            for row in results_table[1:]:
                if not row or len(row) <= name_idx:
                    continue

                name_cell = row[name_idx] if name_idx < len(row) else None
                if not name_cell:
                    continue

                competitor = self._clean_competitor_name(str(name_cell))
                if not competitor:
                    continue

                number_cell = row[number_idx] if number_idx < len(row) else None
                bib = str(number_cell).strip() if number_cell else ""

                row_judge_values = []
                for i, initials in enumerate(judge_initials):
                    col_idx = judge_start + i
                    if col_idx < len(row) and row[col_idx]:
                        value_str = str(row[col_idx]).strip()
                        row_judge_values.append((col_idx, initials, value_str))

                parsed_rows.append((bib, competitor, row_judge_values))

        # Disambiguate duplicate names by appending bib number
        name_counts: dict[str, int] = {}
        for _, comp, _ in parsed_rows:
            name_counts[comp] = name_counts.get(comp, 0) + 1
        if any(v > 1 for v in name_counts.values()):
            parsed_rows = [
                (n, f"{c} [#{n}]" if name_counts[c] > 1 else c, jv)
                for n, c, jv in parsed_rows
            ]

        # Build competitors list and rankings dict
        competitors = []
        rankings = {judge: {} for judge in judges}

        for _bib, competitor, row_judge_values in parsed_rows:
            competitors.append(competitor)
            for _col_idx, initials, value_str in row_judge_values:
                try:
                    placement = int(value_str)
                    judge_name = judge_key.get(initials, initials)
                    rankings[judge_name][competitor] = placement
                except ValueError:
                    pass  # Skip non-numeric placements

        if not competitors:
            raise ValueError("No competitors found in table")

        # Validate that we have complete rankings
        for judge in judges:
            if len(rankings[judge]) != len(competitors):
                # Fill in missing with 0 (will be flagged as incomplete)
                for comp in competitors:
                    if comp not in rankings[judge]:
                        rankings[judge][comp] = 0

        return Scoresheet(
            competition_name=competition_name,
            competitors=competitors,
            judges=judges,
            rankings=rankings,
        )

    def _find_column_indices(self, header: list) -> dict[str, int]:
        """Find the indices of key columns in the header.

        Uses structural detection rather than language-specific header names:
        - The "#" column is identified by its literal text
        - The name column is the one immediately after "#"
        - Judge columns follow the name column and end before the "1-N"
          cumulative tally columns
        """
        indices = {
            "number": 0,
            "name": 1,
            "judge_start": 2,
            "judge_end": len(header),
        }

        for i, cell in enumerate(header):
            if not cell:
                continue
            cell_str = str(cell).strip()

            if cell_str == "#":
                indices["number"] = i
                indices["name"] = i + 1
                indices["judge_start"] = i + 2
            elif cell_str.startswith("1-") or cell_str == "Sum":
                # Found cumulative/summary columns, judges end before this
                indices["judge_end"] = min(indices["judge_end"], i)

        return indices

    @staticmethod
    def _looks_like_callbacks(values: list[str]) -> bool:
        """Check if judge cell values look like callback scores rather than rankings.

        Callback scores are typically 0 (no), 10 (yes), or alternates like 4.5.
        Rankings are integers from 1 to N where N is the number of competitors.
        """
        callback_values = {"0", "10"}
        for v in values:
            if v in callback_values:
                continue
            try:
                f = float(v)
                if 4.0 <= f <= 5.0 and f != int(f):
                    continue  # alternate score like 4.5
            except ValueError:
                pass
            return False  # found a value that doesn't look like a callback
        return True

    def _clean_competitor_name(self, name: str) -> str:
        """Clean up competitor name, combining leader/follower if on separate lines."""
        # Replace newlines with " & " to combine leader/follower
        name = name.replace("\n", " & ")
        # Clean up extra whitespace
        name = " ".join(name.split())
        return name
