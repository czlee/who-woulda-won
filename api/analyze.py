"""Vercel serverless function for analyzing scoresheets."""

import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx
from flask import Flask, request, jsonify

# Add the project root to the path so we can import core modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import parsers to register them
from core.parsers import scoring_dance  # noqa: F401
from core.parsers import eepro  # noqa: F401
from core.parsers import danceconvention  # noqa: F401

# Import voting systems to register them
from core.voting import borda  # noqa: F401
from core.voting import relative_placement  # noqa: F401
from core.voting import schulze  # noqa: F401
from core.voting import sequential_irv  # noqa: F401

from core.analyze import analyze_scoresheet, AnalysisError

app = Flask(__name__)


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """Analyze a scoresheet using multiple voting systems.

    Accepts:
    - JSON body: {"url": "https://..."}
    - Multipart form: file upload with 'file' field and optional 'filename' field

    Returns JSON with voting system comparison results.
    """
    try:
        content_type = request.content_type or ""

        if "application/json" in content_type:
            data = request.get_json()
            url = data.get("url") if data else None

            if not url:
                return jsonify({"error": "Missing 'url' in request body"}), 400

            source, content = fetch_url(url)

        elif "multipart/form-data" in content_type:
            file_data = request.files.get("file")
            if not file_data:
                return jsonify({"error": "Missing 'file' in form data"}), 400

            filename = request.form.get("filename", file_data.filename or "upload")
            source = filename
            content = file_data.read()

        else:
            return jsonify({"error": f"Unsupported content type: {content_type}"}), 400

        result = analyze_scoresheet(source, content)
        return jsonify(result.to_dict())

    except AnalysisError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Internal error: {e}"}), 500


def fetch_url(url: str) -> tuple[str, bytes]:
    """Fetch content from a URL.

    Returns (source_identifier, content_bytes).
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise AnalysisError(f"Invalid URL scheme: {parsed.scheme}")

    try:
        with httpx.Client(follow_redirects=True, timeout=30.0) as client:
            response = client.get(url)
            response.raise_for_status()
            return url, response.content
    except httpx.HTTPStatusError as e:
        raise AnalysisError(f"HTTP error fetching URL: {e.response.status_code}")
    except httpx.RequestError as e:
        raise AnalysisError(f"Error fetching URL: {e}")
