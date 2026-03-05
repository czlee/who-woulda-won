"""Thin wrapper around Upstash Redis for storing competition metadata."""

import json
import os
import re
from datetime import datetime, timezone


def normalize_url(url: str, division: str | None = None) -> str:
    """Normalize a scoresheet URL to a stable KV key.

    Strips cosmetic language path segments from known parsers, lowercases the
    full URL, and appends :{division} if division is non-empty.
    """
    # scoring.dance: strip optional /{lang} before /events/
    # e.g. /enCA/events/123/... -> /events/123/...
    url = re.sub(r"(scoring\.dance)/[a-zA-Z]{2,6}/events/", r"\1/events/", url)

    # danceconvention.net: strip mandatory /{lang}/ between eventdirector/ and roundscores/
    # e.g. /eventdirector/fr/roundscores/... -> /eventdirector/roundscores/...
    url = re.sub(r"(danceconvention\.net/eventdirector)/[a-z]{2}/(roundscores/)", r"\1/\2", url)

    key = url.lower()
    if division:
        key = f"{key}:{division.lower()}"
    return f"meta:{key}"


def _get_client():
    """Return an Upstash Redis client, or None if env vars are not set."""
    url = os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    if not url or not token:
        return None
    from upstash_redis import Redis
    return Redis(url=url, token=token)


def get_competition_name(url: str, division: str | None = None) -> str | None:
    """Return the stored competition name for the given URL, or None."""
    try:
        client = _get_client()
        if client is None:
            return None
        key = normalize_url(url, division)
        data = client.hget(key, "competition_name")
        return data
    except Exception:
        return None


def set_meta(url: str, division: str | None, competition_name: str,
             og_rows: list | None = None) -> None:
    """Store competition name and (on first write) first_analyzed_at for a URL."""
    try:
        client = _get_client()
        if client is None:
            return
        key = normalize_url(url, division)
        # Preserve first_analyzed_at if the key already exists
        existing = client.hget(key, "first_analyzed_at")
        fields: dict = {"competition_name": competition_name}
        if not existing:
            fields["first_analyzed_at"] = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
        if og_rows is not None:
            fields["og_rows"] = json.dumps(og_rows)
        client.hset(key, values=fields)
    except Exception:
        pass


def get_og_rows(url: str, division: str | None = None) -> list | None:
    """Return stored og_rows for the given URL, or None."""
    try:
        client = _get_client()
        if client is None:
            return None
        key = normalize_url(url, division)
        data = client.hget(key, "og_rows")
        return json.loads(data) if data else None
    except Exception:
        return None
