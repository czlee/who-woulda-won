"""Seed the KV store by submitting all gallery URLs to the live /api/analyze endpoint.

Run this after deploying a new set of gallery URLs to ensure OG images are
pre-populated before users view the gallery.

Usage:
    poetry run python scripts/seed_kv.py [--base-url https://www.whowouldawon.dance]
"""

import argparse
import re
import sys
import time
from pathlib import Path

import requests

GALLERY_DATA_JS = Path(__file__).parent.parent / "public" / "gallery-data.js"


def load_gallery_entries():
    """Extract (url, division) pairs from public/gallery-data.js.

    division is the parserDivision value if present, else None. Deduplicates
    on (url, division) so each unique combination is seeded exactly once.
    """
    text = GALLERY_DATA_JS.read_text()
    seen = set()
    entries = []
    for item in re.findall(r'\{[^}]+\}', text):
        url_match = re.search(r"url:\s*'([^']+)'", item)
        if not url_match:
            continue
        url = url_match.group(1)
        div_match = re.search(r"parserDivision:\s*'([^']+)'", item)
        division = div_match.group(1) if div_match else None
        key = (url, division)
        if key not in seen:
            seen.add(key)
            entries.append(key)
    if not entries:
        print(f"ERROR: No entries found in {GALLERY_DATA_JS}", file=sys.stderr)
        sys.exit(1)
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--base-url', default='https://www.whowouldawon.dance',
                        help='Base URL of the deployed app (default: https://www.whowouldawon.dance)')
    parser.add_argument('--delay', type=float, default=3.38,
                        help='Seconds to wait between requests (default: 3.38)')
    args = parser.parse_args()

    gallery_entries = load_gallery_entries()
    endpoint = f"{args.base_url.rstrip('/')}/api/analyze"
    print(f"Seeding KV via {endpoint}")
    print(f"Processing {len(gallery_entries)} entries with {args.delay}s delay between requests\n")

    errors = []
    for i, (url, division) in enumerate(gallery_entries, 1):
        label = f"{url} [{division}]" if division else url
        print(f"[{i:2d}/{len(gallery_entries)}] {label} ... ", end='', flush=True)
        payload = {'url': url}
        if division:
            payload['division'] = division
        try:
            response = requests.post(endpoint, json=payload, timeout=30)
            if response.ok:
                data = response.json()
                name = data.get('competition_name', '(no name)')
                print(f"OK — {name}")
            else:
                msg = f"HTTP {response.status_code}"
                try:
                    msg += f": {response.json().get('error', response.text[:80])}"
                except Exception:
                    msg += f": {response.text[:80]}"
                print(f"FAILED — {msg}")
                errors.append((label, msg))
        except Exception as e:
            msg = str(e)
            print(f"FAILED — {msg}")
            errors.append((label, msg))

        if i < len(gallery_entries):
            time.sleep(args.delay)

    print(f"\nDone. {len(gallery_entries) - len(errors)}/{len(gallery_entries)} succeeded.")
    if errors:
        print("\nFailed entries:")
        for label, msg in errors:
            print(f"  {label}\n    {msg}")
        sys.exit(1)


if __name__ == '__main__':
    main()
