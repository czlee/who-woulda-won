"""Vercel serverless function for generating OG social media preview images.

Uses a pre-rendered template image (assets/og-image-template.png) as the base,
and draws only the dynamic content (text, winner highlights, arrows) on top.
"""

import io
import sys
from pathlib import Path

from flask import Flask, Response, request
from PIL import Image, ImageDraw, ImageFont

# Add the project root to the path so we can import core modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from core import kv  # noqa: E402

app = Flask(__name__)

# Image dimensions
IMG_W, IMG_H = 1200, 630

# Template path
TEMPLATE_PATH = Path(__file__).parent.parent / "assets" / "og-image-template.png"

# Layout constants (measured from template)
# Column divider x-positions: [card_left, comp|rp, rp|borda, borda|schulze, schulze|irv, card_right]
COL_DIVIDERS = [60, 492, 653, 815, 977, 1139]

# Row divider y-positions: [table_top_border, header|row1, row1|row2, row2|row3, row3|row4]
ROW_DIVIDERS = [252, 358, 430, 501, 573]

# Subtitle text region in the header gradient card
SUBTITLE_Y = (138, 162)  # region to paint over for subtitle override

# Colours
WINNER_BG = (212, 237, 218)      # #d4edda
UP_COLOR = (40, 167, 69)         # #28a745
DOWN_COLOR = (220, 53, 69)       # #dc3545
BODY_TEXT = (51, 51, 51)         # #333
MUTED_TEXT = (200, 225, 245)     # approximates white ~80% on blue gradient

FONT_DIR = Path(__file__).parent.parent / "assets" / "fonts" / "DM_Sans"
ARROW_SIZE = 6  # triangle half-width; height = ARROW_SIZE * 1.2


def _load_fonts():
    regular_path = FONT_DIR / "DMSans-Regular.ttf"
    medium_path = FONT_DIR / "DMSans-Medium.ttf"
    semibold_path = FONT_DIR / "DMSans-SemiBold.ttf"
    return {
        "subtitle": ImageFont.truetype(str(medium_path), 24),
        "name": ImageFont.truetype(str(regular_path), 22),
        "rank": ImageFont.truetype(str(regular_path), 22),
        "rank_winner": ImageFont.truetype(str(semibold_path), 22),
    }


def _draw_up_triangle(draw, cx, cy, size, fill):
    """Draw a filled upward-pointing triangle centered at (cx, cy)."""
    h = int(size * 1.2)
    draw.polygon([(cx, cy - h), (cx - size, cy + h // 2), (cx + size, cy + h // 2)], fill=fill)


def _draw_down_triangle(draw, cx, cy, size, fill):
    """Draw a filled downward-pointing triangle centered at (cx, cy)."""
    h = int(size * 1.2)
    draw.polygon([(cx, cy + h), (cx - size, cy - h // 2), (cx + size, cy - h // 2)], fill=fill)


def _truncate(draw, text, font, max_width):
    if draw.textlength(text, font=font) <= max_width:
        return text
    while text and draw.textlength(text + "…", font=font) > max_width:
        text = text[:-1]
    return text + "…"


def _extract_first_names(name: str) -> str:
    """Extract first names from a competitor name.

    For couples (separated by " & " or " and "), extracts the first name of each.
    For singles, extracts the first name only.

    Examples:
        "Luke Primrose & Kate Markman" -> "Luke & Kate"
        "Tama Mitchell and Solana Carpenter" -> "Tama & Solana"
        "Grace Clarricoats" -> "Grace"
    """
    import re
    # Split by " & " or " and " (case-insensitive)
    parts = re.split(r'\s+(?:&|and)\s+', name, flags=re.IGNORECASE)

    first_names = [part.split()[0] for part in parts if part]
    return " & ".join(first_names)


def _ordinal(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    return f"{n}" + {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def _col_x(col_index):
    """Return the left x coordinate of a table column (0 = competitor, 1-4 = systems)."""
    return COL_DIVIDERS[col_index]


def _col_w(col_index):
    """Return the width of a table column."""
    return COL_DIVIDERS[col_index + 1] - COL_DIVIDERS[col_index]


def _row_y(row_index):
    """Return the top y coordinate of a data row (0-indexed)."""
    return ROW_DIVIDERS[row_index + 1]  # +1 because index 0 is the table top border


def _row_h(row_index):
    """Return the height of a data row.

    For the last row (cut off at the bottom of the image), use the same height
    as the previous row so that text is spaced consistently from the top divider.
    """
    if row_index + 2 < len(ROW_DIVIDERS):
        return ROW_DIVIDERS[row_index + 2] - ROW_DIVIDERS[row_index + 1]
    # Last row: use the same height as the previous row
    return ROW_DIVIDERS[row_index + 1] - ROW_DIVIDERS[row_index]


def render_og_image(competition_name: str | None, og_rows: list | None) -> Image.Image:
    img = Image.open(TEMPLATE_PATH).convert("RGB").copy()
    draw = ImageDraw.Draw(img)
    fonts = _load_fonts()

    # --- Subtitle override ---
    if competition_name:
        # Paint over the default subtitle text by sampling gradient colors from
        # just above the text region and filling down
        sub_y1, sub_y2 = SUBTITLE_Y
        sample_y = sub_y1 - 3  # sample gradient color from just above text
        pixels = img.load()
        for x in range(80, IMG_W - 80):
            fill_color = pixels[x, sample_y]
            for y in range(sub_y1, sub_y2):
                pixels[x, y] = fill_color

        # Draw the custom subtitle: "Compare voting systems for {competition_name}"
        subtitle_max_w = IMG_W - 200
        prefix = "Compare voting systems for "
        full_subtitle = prefix + competition_name
        subtitle_text = _truncate(draw, full_subtitle, fonts["subtitle"], subtitle_max_w)
        draw.text((IMG_W // 2, (sub_y1 + sub_y2) // 2), subtitle_text,
                  font=fonts["subtitle"], fill=MUTED_TEXT, anchor="mm")

    if og_rows is None:
        return img

    # --- Data rows ---
    rows = og_rows[:4]
    cell_pad = 20  # measured from template: text starts ~20px from cell border

    for row_i, row in enumerate(rows):
        ry = _row_y(row_i)
        rh = _row_h(row_i)
        mid_y = ry + rh // 2  # vertical center of row

        # Winner cell backgrounds
        for sys_i, rank in enumerate(row["ranks"]):
            if rank == 1:
                cx = _col_x(sys_i + 1)
                cw = _col_w(sys_i + 1)
                # Draw winner background, staying inside the cell borders
                draw.rectangle([cx + 1, ry + 1, cx + cw - 1, ry + rh - 1], fill=WINNER_BG)

        # Competitor name (first names only, left-aligned, vertically centered)
        name_font = fonts["name"]
        name_max_w = _col_w(0) - 2 * cell_pad
        first_names = _extract_first_names(row["name"]) if row["name"] else ""
        name_text = _truncate(draw, first_names, name_font, name_max_w)
        draw.text((_col_x(0) + cell_pad, mid_y), name_text,
                  font=name_font, fill=BODY_TEXT, anchor="lm")

        # System rank cells
        rp_rank = row["ranks"][0]

        for sys_i, rank in enumerate(row["ranks"]):
            if rank is None:
                continue

            cx = _col_x(sys_i + 1)
            cw = _col_w(sys_i + 1)
            rank_font = fonts["rank_winner"] if rank == 1 else fonts["rank"]

            ordinal_text = _ordinal(rank)

            # Determine arrow direction based on comparison to RP rank (col 0)
            arrow_dir = 0  # -1 = up (better), +1 = down (worse)
            arrow_color = BODY_TEXT
            if sys_i > 0 and rp_rank is not None:
                if rank < rp_rank:
                    arrow_dir = -1
                    arrow_color = UP_COLOR
                elif rank > rp_rank:
                    arrow_dir = 1
                    arrow_color = DOWN_COLOR

            cell_cx = cx + cw // 2  # horizontal center of cell

            if arrow_dir == 0:
                # No arrow: center text in cell
                draw.text((cell_cx, mid_y), ordinal_text,
                          font=rank_font, fill=BODY_TEXT, anchor="mm")
            else:
                # With arrow: center the text+arrow combo horizontally
                ord_w = draw.textlength(ordinal_text, font=rank_font)
                gap_arrow = 5
                arr_w = ARROW_SIZE * 2
                total_w = ord_w + gap_arrow + arr_w

                start_x = cx + (cw - total_w) // 2
                draw.text((start_x, mid_y), ordinal_text,
                          font=rank_font, fill=BODY_TEXT, anchor="lm")

                arr_cx = start_x + ord_w + gap_arrow + ARROW_SIZE
                if arrow_dir == -1:
                    _draw_up_triangle(draw, arr_cx, mid_y, ARROW_SIZE, arrow_color)
                else:
                    _draw_down_triangle(draw, arr_cx, mid_y, ARROW_SIZE, arrow_color)

    return img


@app.route("/api/og_image")
def og_image():
    url = request.args.get("url", "")
    division = request.args.get("division") or None
    competition_name = kv.get_competition_name(url, division) if url else None
    og_rows = kv.get_og_rows(url, division) if url else None
    img = render_og_image(competition_name, og_rows)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return Response(
        buf.read(),
        content_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )
