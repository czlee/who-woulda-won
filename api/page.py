"""Vercel serverless function serving index.html with injected og tags."""

import sys
from pathlib import Path
from urllib.parse import urlencode

from flask import Flask, request, Response

# Add the project root to the path so we can import core modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from core import kv  # noqa: E402

app = Flask(__name__)

INDEX_HTML = Path(__file__).parent.parent / "public" / "index.html"


@app.route("/")
def page():
    """Serve index.html, injecting og:title and og:url when competition name is known."""
    url = request.args.get("url", "")
    division = request.args.get("division") or None

    html = INDEX_HTML.read_text(encoding="utf-8")

    if url:
        competition_name = kv.get_competition_name(url, division)
        if competition_name:
            html = html.replace(
                'property="og:title" content="Who Woulda Won?"',
                f'property="og:title" content="{competition_name} | Who Woulda Won?"',
                1,
            )
            params = {"url": url}
            if division:
                params["division"] = division
            page_url = f"https://www.whowouldawon.dance/?{urlencode(params)}"
            html = html.replace(
                'property="og:url" content="https://www.whowouldawon.dance/"',
                f'property="og:url" content="{page_url}"',
                1,
            )

    return Response(html, content_type="text/html; charset=utf-8")
