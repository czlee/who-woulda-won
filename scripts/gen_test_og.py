"""Generate a test OG image for visual comparison during development.

Run with:
    poetry run python scripts/gen_test_og.py

The output is saved to scripts/test_og_output.png. Compare it visually against
public/og-image-default.png (the reference design screenshot).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from api.og_image import render_og_image  # noqa: E402

og_rows = [
    {"name": "Adam Archer & Anna Adler",  "ranks": [1, 5, 5, 3]},
    {"name": "Boris Beck & Bella Braun",  "ranks": [2, 1, 1, 4]},
    {"name": "Carlos Cruz & Clara Chen",  "ranks": [3, 4, 2, 2]},
    {"name": "David Deng & Diana Duval",  "ranks": [4, 2, 3, 1]},
]
competition_name = None  # produces generic subtitle

img = render_og_image(competition_name, og_rows)
out = Path(__file__).parent / "test_og_output.png"
img.save(out)
print(f"Saved to {out}")
