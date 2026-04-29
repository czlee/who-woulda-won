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


def load_gallery_urls():
    """Extract URLs from public/gallery-data.js by parsing url: '...' entries."""
    text = GALLERY_DATA_JS.read_text()
    urls = re.findall(r"url:\s*'([^']+)'", text)
    if not urls:
        print(f"ERROR: No URLs found in {GALLERY_DATA_JS}", file=sys.stderr)
        sys.exit(1)
    return urls


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--base-url', default='https://www.whowouldawon.dance',
                        help='Base URL of the deployed app (default: https://www.whowouldawon.dance)')
    parser.add_argument('--delay', type=float, default=7.5,
                        help='Seconds to wait between requests (default: 7.5)')
    args = parser.parse_args()

    gallery_urls = load_gallery_urls()
    endpoint = f"{args.base_url.rstrip('/')}/api/analyze"
    print(f"Seeding KV via {endpoint}")
    print(f"Processing {len(gallery_urls)} URLs with {args.delay}s delay between requests\n")

    errors = []
    for i, url in enumerate(gallery_urls, 1):
        print(f"[{i:2d}/{len(gallery_urls)}] {url} ... ", end='', flush=True)
        try:
            response = requests.post(endpoint, json={'url': url}, timeout=30)
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
                errors.append((url, msg))
        except Exception as e:
            msg = str(e)
            print(f"FAILED — {msg}")
            errors.append((url, msg))

        if i < len(gallery_urls):
            time.sleep(args.delay)

    print(f"\nDone. {len(gallery_urls) - len(errors)}/{len(gallery_urls)} succeeded.")
    if errors:
        print("\nFailed URLs:")
        for url, msg in errors:
            print(f"  {url}\n    {msg}")
        sys.exit(1)


if __name__ == '__main__':
    main()
