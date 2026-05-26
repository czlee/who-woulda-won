"""Dump all entries from the KV store to a JSON file.

Requires KV_REST_API_URL and KV_REST_API_TOKEN (or their UPSTASH_REDIS_REST_*
equivalents) to be set in the environment.

Usage:
    poetry run python scripts/dump_kv.py results.json
"""

import argparse
import json
import os
import sys


def get_client():
    url = os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    if not url or not token:
        print("ERROR: KV_REST_API_URL and KV_REST_API_TOKEN must be set.", file=sys.stderr)
        sys.exit(1)
    from upstash_redis import Redis
    return Redis(url=url, token=token)


def scan_all_keys(client, pattern="meta:*"):
    """Scan all keys matching pattern using SCAN cursor iteration."""
    keys = []
    cursor = 0
    while True:
        cursor, batch = client.scan(cursor, match=pattern, count=100)
        keys.extend(batch)
        if cursor == 0:
            break
    return keys


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("output", metavar="FILE", help="Write JSON output to FILE")
    parser.add_argument("--pattern", default="meta:*",
                        help="Redis key pattern to scan (default: meta:*)")
    args = parser.parse_args()

    client = get_client()

    print("Scanning keys...", file=sys.stderr)
    keys = scan_all_keys(client, args.pattern)
    total = len(keys)
    print(f"Found {total} keys.", file=sys.stderr)

    entries = []
    for i, key in enumerate(sorted(keys), 1):
        print(f"\r[{i}/{total}] {key}", end="", flush=True, file=sys.stderr)
        raw = client.hgetall(key)
        entry = {"key": key}
        for field, value in raw.items():
            if field == "og_rows":
                try:
                    entry[field] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    entry[field] = value
            else:
                entry[field] = value
        entries.append(entry)
    print(file=sys.stderr)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(entries)} entries to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
