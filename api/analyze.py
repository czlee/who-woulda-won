"""Vercel serverless function for analyzing scoresheets."""

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx

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


def handler(request):
    """Handle incoming requests to analyze scoresheets.

    Accepts:
    - POST with JSON body: {"url": "https://..."}
    - POST with multipart form: file upload with 'file' field and optional 'filename' field

    Returns JSON with voting system comparison results.
    """
    # Handle CORS preflight
    if request.method == "OPTIONS":
        return create_response(
            "",
            status=204,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            },
        )

    if request.method != "POST":
        return create_response(
            {"error": "Method not allowed. Use POST."},
            status=405,
        )

    try:
        content_type = request.headers.get("content-type", "")

        if "application/json" in content_type:
            # JSON body with URL
            body = request.body.decode("utf-8")
            data = json.loads(body)
            url = data.get("url")

            if not url:
                return create_response(
                    {"error": "Missing 'url' in request body"},
                    status=400,
                )

            # Fetch the URL
            source, content = fetch_url(url)

        elif "multipart/form-data" in content_type:
            # File upload
            # Note: Vercel's request object handles multipart parsing
            file_data = request.files.get("file")
            if not file_data:
                return create_response(
                    {"error": "Missing 'file' in form data"},
                    status=400,
                )

            filename = request.form.get("filename", file_data.filename or "upload")
            source = filename
            content = file_data.read()

        else:
            return create_response(
                {"error": f"Unsupported content type: {content_type}"},
                status=400,
            )

        # Analyze the scoresheet
        result = analyze_scoresheet(source, content)

        return create_response(result.to_dict())

    except AnalysisError as e:
        return create_response(
            {"error": str(e)},
            status=400,
        )
    except json.JSONDecodeError as e:
        return create_response(
            {"error": f"Invalid JSON: {e}"},
            status=400,
        )
    except Exception as e:
        return create_response(
            {"error": f"Internal error: {e}"},
            status=500,
        )


def fetch_url(url: str) -> tuple[str, bytes]:
    """Fetch content from a URL.

    Returns (source_identifier, content_bytes).
    """
    # Validate URL
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


def create_response(body, status: int = 200, headers: dict = None):
    """Create a response object for Vercel."""
    response_headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
    }
    if headers:
        response_headers.update(headers)

    if isinstance(body, dict):
        body = json.dumps(body)

    # Return in format expected by Vercel Python runtime
    return {
        "statusCode": status,
        "headers": response_headers,
        "body": body,
    }
