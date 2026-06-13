#!/usr/bin/env python3
"""Discover recent competition finals and analyze them with Who Woulda Won."""

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.analyze import AnalysisError, AnalysisResult, analyze_scoresheet
from core.parsers import danceconvention, eepro, scoring_dance  # noqa: F401 — trigger registration
from core.voting import borda, relative_placement, schulze, sequential_irv  # noqa: F401
from core.parsers.eepro import EeproParser
from core.parsers.base import shorten_division_name
from core.summarize import summarize

LEVEL_ORDER = ["drama", "shakeup", "close_call", "consistent"]

LEVEL_COLORS = {
    "drama":      "\033[31m",   # red
    "shakeup":    "\033[33m",   # yellow (closest to orange)
    "close_call": "\033[93m",   # bright yellow (closest to amber)
    "consistent": "\033[32m",   # green
}
ANSI_RESET = "\033[0m"


def colorize(text: str, level: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"{LEVEL_COLORS.get(level, '')}{text}{ANSI_RESET}"


def bold(text: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[1m{text}{ANSI_RESET}"


def green(text: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[32m{text}{ANSI_RESET}"


def red(text: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[31m{text}{ANSI_RESET}"


def bg_dark_green(text: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[42m{text}{ANSI_RESET}"


def heading(text: str) -> None:
    line = "─" * 60
    print(f"\n{line}\n  {text}\n{line}")

ROUND_KEYWORDS = re.compile(
    r"^(?:Final|Finals|Semifinal|Semifinals|Semi|Semis|"
    r"Quarterfinal|Quarterfinals|Quarter|Quarters|"
    r"Prelim|Prelims|Preliminary|Preliminaries)$",
    re.IGNORECASE,
)


@dataclass
class DiscoveredFinal:
    site: str
    event_name: str
    event_date: date
    event_end_date: date
    division: str
    url: str
    parser_division: str | None = None


@dataclass
class AnalyzedFinal:
    final: DiscoveredFinal
    level: str
    label: str
    sentence: str
    competition_name: str
    analysis: AnalysisResult


def _overlaps(ev_start: date, ev_end: date, w_start: date, w_end: date) -> bool:
    return ev_start <= w_end and ev_end >= w_start


def get_default_start_date() -> date:
    gallery_path = Path(__file__).parent.parent / "public" / "gallery-data.js"
    try:
        dates = re.findall(r"date:\s*'(\d{4}-\d{2}-\d{2})'", gallery_path.read_text())
        if dates:
            max_date = date.fromisoformat(max(dates))
            # Gallery dates are the Saturday of the event weekend, so advance
            # to Monday to skip the rest of that weekend.
            days_forward = 3 if max_date.weekday() == 5 else 1
            return max_date + timedelta(days=days_forward)
    except Exception:
        pass
    return date.today() - timedelta(days=7)


# ---------------------------------------------------------------------------
# scoring.dance
# ---------------------------------------------------------------------------

def discover_scoring_dance(
    client: httpx.Client, w_start: date, w_end: date
) -> list[DiscoveredFinal]:
    finals = []
    print("  Fetching scoring.dance/enCA/recent...", end=" ", flush=True)
    try:
        html = client.get("https://scoring.dance/enCA/recent").text
    except Exception as e:
        print(f"FAILED: {e}")
        return finals

    soup = BeautifulSoup(html, "lxml")
    print()

    # Matches "05/29 - 06/01/2026" (range) or "04/05/2026" (single date)
    date_range_re = re.compile(r"(\d{2}/\d{2})\s*[-–]\s*(\d{2}/\d{2})/(\d{4})")
    date_single_re = re.compile(r"(\d{2}/\d{2}/\d{4})")
    event_ids: dict[str, tuple[date, date]] = {}
    seen_ids: set[str] = set()

    for a in soup.find_all("a", href=re.compile(r"/events/\d+")):
        href = a.get("href", "")
        m = re.search(r"/events/(\d+)", href)
        if not m or m.group(1) in seen_ids:
            continue
        event_id = m.group(1)
        seen_ids.add(event_id)

        node = a
        found = False
        for _ in range(5):
            if node is None:
                break
            text = node.get_text(" ", strip=True)
            dm = date_range_re.search(text)
            if dm:
                yr = int(dm.group(3))
                try:
                    ev_start = datetime.strptime(f"{dm.group(1)}/{yr}", "%m/%d/%Y").date()
                    ev_end = datetime.strptime(f"{dm.group(2)}/{yr}", "%m/%d/%Y").date()
                    event_ids[event_id] = (ev_start, ev_end)
                    found = True
                except ValueError:
                    pass
                break
            ds = date_single_re.search(text)
            if ds:
                try:
                    ev_start = ev_end = datetime.strptime(ds.group(1), "%m/%d/%Y").date()
                    event_ids[event_id] = (ev_start, ev_end)
                    found = True
                except ValueError:
                    pass
                break
            node = node.parent
        if not found:
            raw = node.get_text(" ", strip=True)[:80] if node is not None else "(no text found)"
            print(f"  WARNING: could not parse date for scoring.dance event {event_id}: {raw!r} (skipping)")
        elif ev_end < w_start:
            break  # events are reverse-chronological; nothing earlier will be in window

    in_window = [(eid, es, ee) for eid, (es, ee) in event_ids.items()
                 if _overlaps(es, ee, w_start, w_end)]

    if not in_window:
        print(f"  No events in window (checked {len(event_ids)} events on page)")
        return finals

    for event_id, ev_start, ev_end in in_window:
        print(f"  scoring.dance event {event_id} ({ev_start} – {ev_end})", end=" ", flush=True)
        try:
            r = client.get(f"https://scoring.dance/enCA/events/{event_id}/results/")
            r.raise_for_status()
        except Exception as e:
            print(f"FAILED: {e}")
            continue

        rsoup = BeautifulSoup(r.text, "lxml")
        h1 = rsoup.find("h1")
        event_name = re.sub(r"\s+results?$", "", h1.get_text(strip=True), flags=re.IGNORECASE) if h1 else f"Event {event_id}"
        count = 0
        for a in rsoup.find_all("a", href=re.compile(r"/events/\d+/results/\d+\.html")):
            name = a.get_text(strip=True)
            nl = name.lower()
            if "final" not in nl:
                continue
            if any(x in nl for x in ("prelim", "semi", "quarter")):
                continue
            href = a.get("href", "")
            url = f"https://scoring.dance{href}" if href.startswith("/") else href
            division = re.sub(r"\s+finals?$", "", name, flags=re.IGNORECASE).strip()
            finals.append(DiscoveredFinal(
                site="scoring.dance",
                event_name=event_name,
                event_date=ev_start,
                event_end_date=ev_end,
                division=division,
                url=url,
            ))
            count += 1
        print(f"→ {event_name}, {count} finals")

    return finals


# ---------------------------------------------------------------------------
# eepro.com
# ---------------------------------------------------------------------------

def discover_eepro(
    client: httpx.Client, w_start: date, w_end: date
) -> list[DiscoveredFinal]:
    finals = []
    eepro_parser = EeproParser()

    for year in sorted({w_start.year, w_end.year}):
        listing_url = f"https://eepro.com/results/{year}/"
        print(f"  Fetching eepro.com/results/{year}/...", end=" ", flush=True)
        try:
            html = client.get(listing_url).text
        except Exception as e:
            print(f"FAILED: {e}")
            continue

        soup = BeautifulSoup(html, "lxml")
        print()
        seen_urls: set[str] = set()

        # Each event is a <li> whose direct text contains the date range
        # and whose nested <ul> contains result type links.
        for li in soup.find_all("li"):
            li_text = li.get_text(" ", strip=True)

            dm = re.search(r"([A-Za-z]+)\s+(\d+)[-–](\d+),?\s*(\d{4})", li_text)
            if dm:
                try:
                    ev_start = datetime.strptime(
                        f"{dm.group(1)} {dm.group(2)} {dm.group(4)}", "%B %d %Y"
                    ).date()
                    ev_end = datetime.strptime(
                        f"{dm.group(1)} {dm.group(3)} {dm.group(4)}", "%B %d %Y"
                    ).date()
                except ValueError:
                    continue
            else:
                dm2 = re.search(r"([A-Za-z]+)\s+(\d+),?\s*(\d{4})", li_text)
                if not dm2:
                    continue
                try:
                    ev_start = ev_end = datetime.strptime(
                        f"{dm2.group(1)} {dm2.group(2)} {dm2.group(3)}", "%B %d %Y"
                    ).date()
                except ValueError:
                    continue

            if not _overlaps(ev_start, ev_end, w_start, w_end):
                continue

            # Extract event name: text before the first date pattern in li_text
            event_name_raw = re.split(r"[A-Za-z]+ \d+[-–]", li_text)[0].strip(" -–")
            event_label = f"eepro.com: {event_name_raw} ({ev_start} – {ev_end})" if event_name_raw else f"eepro.com ({ev_start} – {ev_end})"
            printed_event = False

            for a in li.find_all("a", href=True):
                href = a.get("href", "")
                m = re.search(
                    r"(?:\.\./|/results/)([a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+?)(?:\.html)?$",
                    href,
                )
                if not m:
                    continue
                event_slug = m.group(1)
                result_type = m.group(2).lower()
                if not result_type.endswith("finals") or "prelims" in result_type:
                    continue

                result_url = f"https://eepro.com/results/{event_slug}/{m.group(2)}.html"
                if result_url in seen_urls:
                    continue
                seen_urls.add(result_url)

                try:
                    resp = client.get(result_url)
                    if resp.status_code == 404:
                        continue
                    resp.raise_for_status()
                    content = resp.content
                except Exception:
                    continue

                division_names = eepro_parser.get_division_names(content)
                rsoup = BeautifulSoup(content.decode("utf-8", errors="replace"), "lxml")
                h2 = rsoup.find("h2")
                event_name = h2.get_text(strip=True) if h2 else event_slug

                if not printed_event:
                    print(f"  {event_label}")
                    printed_event = True

                if not division_names:
                    finals.append(DiscoveredFinal(
                        site="eepro.com",
                        event_name=event_name,
                        event_date=ev_start,
                        event_end_date=ev_end,
                        division="",
                        url=result_url,
                    ))
                else:
                    for div_name in division_names:
                        short_name = shorten_division_name(div_name, division_names)
                        finals.append(DiscoveredFinal(
                            site="eepro.com",
                            event_name=event_name,
                            event_date=ev_start,
                            event_end_date=ev_end,
                            division=short_name,
                            url=result_url,
                            parser_division=short_name,
                        ))

    return finals


# ---------------------------------------------------------------------------
# danceconvention.net
# ---------------------------------------------------------------------------

def _decode_nuxt(text: str) -> str:
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), text)


def _parse_mdy(s: str) -> date | None:
    try:
        parts = s.strip().split("/")
        if len(parts) == 3:
            m, d, y = int(parts[0]), int(parts[1]), int(parts[2])
            return date(2000 + y if y < 100 else y, m, d)
    except (ValueError, IndexError):
        pass
    return None


def discover_danceconvention(
    client: httpx.Client, w_start: date, w_end: date
) -> list[DiscoveredFinal]:
    finals = []

    for year in sorted({w_start.year, w_end.year}):
        archive_url = f"https://danceconvention.net/eventdirector/en/eventsarchive/{year}"
        print(f"  Fetching danceconvention.net archive ({year})...", end=" ", flush=True)
        try:
            resp = client.get(archive_url)
            resp.raise_for_status()
        except Exception as e:
            print(f"FAILED: {e}")
            continue

        blob = _decode_nuxt(resp.text)
        ep_re = re.compile(r"/eventdirector/en/eventpage/(\d+)-([^\"]+)")

        events: dict[str, tuple[str, str, date, date]] = {}
        for m in ep_re.finditer(blob):
            event_id, slug = m.group(1), m.group(2)
            if event_id in events:
                continue

            # Look backwards for event name and dates
            ctx = blob[max(0, m.start() - 600) : m.start()]

            # Narrow to text after the most recent occurrence of this event_id
            id_pos = ctx.rfind(f",{event_id},")
            if id_pos == -1:
                id_pos = 0
            relevant = ctx[id_pos:]

            ev_start = ev_end = None
            raw_date_str = None
            dr = re.search(r'"(\d{1,2}/\d{1,2}/\d{2,4})-(\d{1,2}/\d{1,2}/\d{2,4})"', relevant)
            if dr:
                raw_date_str = dr.group(0)
                ev_start = _parse_mdy(dr.group(1))
                ev_end = _parse_mdy(dr.group(2))
            else:
                sd = re.search(r'"(\d{1,2}/\d{1,2}/\d{2,4})"', relevant)
                if sd:
                    raw_date_str = sd.group(0)
                    ev_start = ev_end = _parse_mdy(sd.group(1))

            if ev_start is None:
                date_info = f" (found date string: {raw_date_str})" if raw_date_str else " (no date string found)"
                print(f"  WARNING: could not parse date for danceconvention.net event {event_id} (slug: {slug}){date_info}, skipping", file=sys.stderr)
                continue

            name_m = re.search(rf",{event_id},\"([^\"]+)\"", ctx)
            event_name = name_m.group(1) if name_m else f"Event {event_id}"
            events[event_id] = (event_name, slug, ev_start, ev_end)

        qualifying = [
            (eid, name, slug, es, ee)
            for eid, (name, slug, es, ee) in events.items()
            if _overlaps(es, ee, w_start, w_end)
        ]
        print(f"found {len(events)} events, {len(qualifying)} in window")

        for event_id, event_name, slug, ev_start, ev_end in qualifying:
            results_url = (
                f"https://danceconvention.net/eventdirector/en/"
                f"eventpage/{event_id}-{slug}/results"
            )
            print(f"  danceconvention.net: {event_name} ({ev_start} – {ev_end})...", end=" ", flush=True)
            try:
                resp = client.get(results_url)
                resp.raise_for_status()
            except Exception as e:
                print(f"FAILED: {e}")
                continue

            rblob = _decode_nuxt(resp.text)

            # Division entries have TWO numbers before the roundscores URL:
            # {div_id},"Division Name",{pdf_id},"/eventdirector/en/roundscores/{pdf_id}.pdf"
            div_re = re.compile(
                r'\d+,"([^"]+)",(\d+),"/eventdirector/en/roundscores/\d+\.pdf"'
            )
            count = 0
            for m in div_re.finditer(rblob):
                division_name, pdf_id = m.group(1), m.group(2)
                if ROUND_KEYWORDS.match(division_name.strip()):
                    continue
                finals.append(DiscoveredFinal(
                    site="danceconvention.net",
                    event_name=event_name,
                    event_date=ev_start,
                    event_end_date=ev_end,
                    division=division_name,
                    url=f"https://danceconvention.net/eventdirector/en/roundscores/{pdf_id}.pdf",
                ))
                count += 1
            print(f"{count} finals")

    return finals


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyze_finals(
    finals: list[DiscoveredFinal], client: httpx.Client
) -> list[AnalyzedFinal]:
    analyzed = []
    for i, final in enumerate(finals, 1):
        div = final.division or "(single division)"
        print(f"  [{i}/{len(finals)}] {final.event_name} — {div}", end=" ", flush=True)
        try:
            content = client.get(final.url).content
            result = analyze_scoresheet(final.url, content, division=final.parser_division)
            s = summarize(result)
            analyzed.append(AnalyzedFinal(
                final=final,
                level=s["level"],
                label=s["label"],
                sentence=s["sentence"],
                competition_name=result.scoresheet.competition_name,
                analysis=result,
            ))
            print(f"→ {colorize(s['label'], s['level'])}")
        except AnalysisError as e:
            print(f"→ skip ({e})")
        except Exception as e:
            print(f"→ error: {e}")
    return analyzed


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _gallery_date(ev_start: date, ev_end: date) -> date:
    """Return the Saturday of the event weekend, or ev_end for non-weekend events."""
    for i in range((ev_end - ev_start).days + 1):
        d = ev_start + timedelta(days=i)
        if d.weekday() == 5:  # Saturday
            return d
    return ev_end


def print_report(analyzed: list[AnalyzedFinal]) -> None:
    by_level: dict[str, list[AnalyzedFinal]] = {lvl: [] for lvl in LEVEL_ORDER}
    for a in analyzed:
        by_level.get(a.level, by_level["consistent"]).append(a)

    for level in LEVEL_ORDER:
        entries = by_level[level]
        if not entries:
            continue
        heading(bold(colorize(entries[0].label, level)))
        for a in entries:
            div = a.final.division or "(single division)"
            dates = f"{a.final.event_date} – {a.final.event_end_date}"
            line = f"{a.final.event_name} — {div}  [{a.final.site}, {dates}]"
            print(f"  {colorize(line, level)}")


SYSTEM_ABBREVS = {
    "Borda Count": "Bor",
    "Relative Placement": "RP",
    "Schulze Method": "Sch",
    "Sequential IRV": "IRV",
}


def print_comparison_table(analysis: AnalysisResult) -> None:
    # Put RP first, matching the app's default column order
    rp_idx_orig = next((i for i, r in enumerate(analysis.results) if r.system_name == "Relative Placement"), None)
    if rp_idx_orig is not None:
        rp = analysis.results[rp_idx_orig]
        others = [r for i, r in enumerate(analysis.results) if i != rp_idx_orig]
        systems = [rp] + others
    else:
        systems = analysis.results
    rp_idx = 0 if rp_idx_orig is not None else None

    abbrevs = [SYSTEM_ABBREVS.get(r.system_name, r.system_name[:3]) for r in systems]

    rp = systems[rp_idx] if rp_idx is not None else systems[0] if systems else None
    competitors = sorted(
        analysis.scoresheet.competitors,
        key=lambda c: (rp.get_place(c) or 999) if rp else 0,
    )
    first_names = [
        " & ".join(part.split()[0] for part in re.split(r'\s+(?:&|and)\s+', c, flags=re.IGNORECASE) if part)
        for c in competitors
    ]

    name_w = max(len(n) for n in first_names)
    col_ws = [max(len(a), 3) for a in abbrevs]

    def hline(l, m, r):
        return "  " + l + m.join("─" * (w + 2) for w in [name_w] + col_ws) + r

    def data_row(first_name, competitor):
        rp_place = systems[rp_idx].get_place(competitor) if rp_idx is not None else None
        cells = [f" {first_name:<{name_w}} "]
        for i, (r, w) in enumerate(zip(systems, col_ws)):
            p = r.get_place(competitor)
            padded = f"{p:>{w}}" if p is not None else f"{'?':>{w}}"
            if p == 1:
                padded = bg_dark_green(padded)
            elif i != rp_idx and p is not None and rp_place is not None:
                if p < rp_place:
                    padded = green(padded)
                elif p > rp_place:
                    padded = red(padded)
            cells.append(f" {padded} ")
        return "  │" + "│".join(cells) + "│"

    def header_row():
        cells = [f" {'Name':<{name_w}} "] + [f" {a:>{w}} " for a, w in zip(abbrevs, col_ws)]
        return "  │" + "│".join(cells) + "│"

    print(hline("┌", "┬", "┐"))
    print(header_row())
    print(hline("├", "┼", "┤"))
    for first_name, competitor in zip(first_names, competitors):
        print(data_row(first_name, competitor))
    print(hline("└", "┴", "┘"))
    print()


def prompt_and_output_gallery(analyzed: list[AnalyzedFinal]) -> None:
    candidates = [a for a in analyzed if a.level in ("close_call", "shakeup", "drama")]
    if not candidates:
        print("\nNo Close Call, Shakeup, or Drama results to review.")
        return

    confirmed = []
    heading(bold("GALLERY REVIEW — Close Call, Shakeup & Drama"))

    for a in candidates:
        div = a.final.division or "(single division)"
        ww_url = f"https://www.whowouldawon.dance/?url={quote(a.final.url, safe='')}"
        if a.final.parser_division:
            ww_url += f"&division={quote(a.final.parser_division, safe='')}"
        print(f"\n  {bold(colorize(f'{a.label}  —  {a.final.event_name} — {div}', a.level))}")
        print(f"  {a.sentence}")
        print(f"  {ww_url}")
        print()
        print_comparison_table(a.analysis)
        try:
            ans = input("  Add to gallery? (y/n/q): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if ans == "q":
            break
        if ans == "y":
            confirmed.append(a)

    if not confirmed:
        print("\nNothing confirmed.")
        return

    # Build the JS lines to insert
    new_lines = []
    for a in confirmed:
        f = a.final
        gdate = _gallery_date(f.event_date, f.event_end_date).isoformat()
        parts = [
            f"date: '{gdate}'",
            f"url: '{f.url}'",
            f"event: '{f.event_name}'",
            f"division: '{f.division}'",
        ]
        if f.parser_division:
            parts.append(f"parserDivision: '{f.parser_division}'")
        new_lines.append("    { " + ", ".join(parts) + " },")

    heading(bold("INSERTING INTO gallery-data.js"))
    print()
    for line in new_lines:
        print(line)

    print()
    try:
        ans = input("  Write these entries to gallery-data.js? (y/n): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.")
        return
    if ans != "y":
        print("Skipped.")
        return

    gallery_path = Path(__file__).parent.parent / "public" / "gallery-data.js"
    content = gallery_path.read_text()
    insert_marker = "const GALLERY_ITEMS = [\n"
    idx = content.find(insert_marker)
    if idx == -1:
        print("ERROR: Could not find insertion point in gallery-data.js")
        return
    insert_pos = idx + len(insert_marker)
    insertion = "\n".join(new_lines) + "\n"
    gallery_path.write_text(content[:insert_pos] + insertion + content[insert_pos:])
    print(f"  Done — inserted {len(new_lines)} line(s) at the top of GALLERY_ITEMS.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Discover recent competition finals and analyze them."
    )
    ap.add_argument(
        "--start",
        type=date.fromisoformat,
        default=None,
        help="Start date YYYY-MM-DD (default: most recent date in gallery-data.js)",
    )
    ap.add_argument(
        "--end",
        type=date.fromisoformat,
        default=date.today(),
        help="End date YYYY-MM-DD (default: today)",
    )
    ap.add_argument(
        "--site",
        choices=["scoring.dance", "eepro", "danceconvention"],
        action="append",
        dest="sites",
        help="Only check this site (repeatable; default: all)",
    )
    args = ap.parse_args()

    w_start = args.start or get_default_start_date()
    w_end = args.end
    sites = set(args.sites or ["scoring.dance", "eepro", "danceconvention"])

    print(f"Date window: {w_start} to {w_end}\n")

    all_finals: list[DiscoveredFinal] = []

    with httpx.Client(timeout=30, follow_redirects=True) as client:
        if "scoring.dance" in sites:
            print("scoring.dance:")
            all_finals.extend(discover_scoring_dance(client, w_start, w_end))
        if "eepro" in sites:
            print("eepro.com:")
            all_finals.extend(discover_eepro(client, w_start, w_end))
        if "danceconvention" in sites:
            print("danceconvention.net:")
            all_finals.extend(discover_danceconvention(client, w_start, w_end))

        if not all_finals:
            print("\nNo finals discovered. Try --start / --end to adjust the window.")
            return

        print(f"\nDiscovered {len(all_finals)} finals. Analyzing...\n")
        analyzed = analyze_finals(all_finals, client)

    print_report(analyzed)
    prompt_and_output_gallery(analyzed)


if __name__ == "__main__":
    main()
