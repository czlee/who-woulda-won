"""Vercel serverless function for generating OG social media preview images."""

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

# Layout
PADDING = 36
HEADER_Y = 16
HEADER_H = 160
TABLE_Y = 192
TABLE_H = IMG_H - TABLE_Y - 16

# Table geometry
TABLE_X = PADDING
TABLE_W = IMG_W - 2 * PADDING  # 1128
COL_COMPETITOR = 420
COL_SYSTEM = (TABLE_W - COL_COMPETITOR) // 4  # 177
TABLE_HEADER_H = 60
DATA_ROW_H = (TABLE_H - TABLE_HEADER_H) // 4  # fits 4 rows

# Colours
BG_COLOR = "#f5f5f5"
HEADER_GRAD_L = (52, 152, 219)   # #3498DB
HEADER_GRAD_R = (36, 113, 163)   # #2471A3
TABLE_HEADER_BG = (52, 152, 219)
TABLE_BORDER = (221, 221, 221)
EVEN_ROW_BG = (249, 249, 249)
ODD_ROW_BG = (255, 255, 255)
WINNER_BG = (212, 237, 218)      # #d4edda
UP_COLOR = (40, 167, 69)         # #28a745
DOWN_COLOR = (220, 53, 69)       # #dc3545
BODY_TEXT = (51, 51, 51)         # #333
HEADER_TEXT = (255, 255, 255)
MUTED_TEXT = (255, 255, 255, 204)  # white 80% opacity

FONT_DIR = Path(__file__).parent.parent / "assets" / "fonts" / "DM_Sans"
SYSTEM_LABELS = ["Rel.\nPlacement", "Borda\nCount", "Schulze\nMethod", "Seq.\nIRV"]


def _load_fonts():
    regular_path = FONT_DIR / "DMSans-Regular.ttf"
    semibold_path = FONT_DIR / "DMSans-SemiBold.ttf"
    return {
        "title": ImageFont.truetype(str(semibold_path), 44),
        "subtitle": ImageFont.truetype(str(regular_path), 26),
        "table_header": ImageFont.truetype(str(semibold_path), 22),
        "table_header_small": ImageFont.truetype(str(semibold_path), 18),
        "name": ImageFont.truetype(str(regular_path), 26),
        "rank": ImageFont.truetype(str(semibold_path), 26),
        "rank_small": ImageFont.truetype(str(regular_path), 20),
    }


def _draw_gradient_rect(draw, x1, y1, x2, y2, c1, c2):
    w = x2 - x1
    for i in range(w):
        t = i / w
        color = tuple(int(a + t * (b - a)) for a, b in zip(c1, c2))
        draw.line([(x1 + i, y1), (x1 + i, y2)], fill=color)


def _truncate(draw, text, font, max_width):
    if draw.textlength(text, font=font) <= max_width:
        return text
    while text and draw.textlength(text + "…", font=font) > max_width:
        text = text[:-1]
    return text + "…"


def _first_name(name: str) -> str:
    """'Alice Smith & Bob Jones' → 'Alice & Bob'"""
    return " & ".join(part.split()[0] for part in name.split(" & ") if part.split())


def _ordinal(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    return f"{n}" + {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def _draw_rounded_rect(draw, x1, y1, x2, y2, radius, fill):
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill)


def _draw_text_centered(draw, text, font, x, y, w, h, fill):
    """Draw text centered in a box defined by (x, y, x+w, y+h)."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = x + (w - tw) // 2
    ty = y + (h - th) // 2
    draw.text((tx, ty), text, font=font, fill=fill)


def _col_x(col_index):
    """Return the left x coordinate of a table column (0 = competitor, 1-4 = systems)."""
    if col_index == 0:
        return TABLE_X
    return TABLE_X + COL_COMPETITOR + (col_index - 1) * COL_SYSTEM


def _col_w(col_index):
    return COL_COMPETITOR if col_index == 0 else COL_SYSTEM


def render_og_image(competition_name: str | None, og_rows: list | None) -> Image.Image:
    img = Image.new("RGB", (IMG_W, IMG_H), BG_COLOR)
    draw = ImageDraw.Draw(img)
    fonts = _load_fonts()

    # --- Header card ---
    _draw_gradient_rect(draw, PADDING, HEADER_Y, IMG_W - PADDING, HEADER_Y + HEADER_H,
                        HEADER_GRAD_L, HEADER_GRAD_R)
    # Rounded corners via rounded_rectangle overlay
    draw.rounded_rectangle([PADDING, HEADER_Y, IMG_W - PADDING, HEADER_Y + HEADER_H],
                            radius=8, outline=None, fill=None)
    # Re-draw as rounded
    img2 = Image.new("RGB", (IMG_W, IMG_H), BG_COLOR)
    draw2 = ImageDraw.Draw(img2)
    _draw_gradient_rect(draw2, PADDING, HEADER_Y, IMG_W - PADDING, HEADER_Y + HEADER_H,
                        HEADER_GRAD_L, HEADER_GRAD_R)
    mask = Image.new("L", (IMG_W, IMG_H), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([PADDING, HEADER_Y, IMG_W - PADDING, HEADER_Y + HEADER_H],
                                 radius=8, fill=255)
    img.paste(img2, mask=mask)
    draw = ImageDraw.Draw(img)

    title_text = "Who Woulda Won?"
    subtitle_text = competition_name if competition_name else "Compare voting systems on dance competition scoresheets"

    # Title
    title_bbox = draw.textbbox((0, 0), title_text, font=fonts["title"])
    title_h = title_bbox[3] - title_bbox[1]
    subtitle_bbox = draw.textbbox((0, 0), subtitle_text, font=fonts["subtitle"])
    subtitle_h = subtitle_bbox[3] - subtitle_bbox[1]
    gap = 10
    total_text_h = title_h + gap + subtitle_h
    text_y = HEADER_Y + (HEADER_H - total_text_h) // 2

    draw.text((PADDING + 24, text_y), title_text, font=fonts["title"], fill=HEADER_TEXT)

    subtitle_max_w = IMG_W - 2 * PADDING - 48
    subtitle_text = _truncate(draw, subtitle_text, fonts["subtitle"], subtitle_max_w)
    draw.text((PADDING + 24, text_y + title_h + gap), subtitle_text,
              font=fonts["subtitle"], fill=(255, 255, 255, 204))

    if og_rows is None:
        return img

    # --- Table card ---
    rows = og_rows[:4]
    actual_row_h = (TABLE_H - TABLE_HEADER_H) // max(len(rows), 1)

    # White rounded card background
    draw.rounded_rectangle([TABLE_X, TABLE_Y, TABLE_X + TABLE_W, TABLE_Y + TABLE_H],
                            radius=8, fill=(255, 255, 255))

    # Table header row background
    draw.rounded_rectangle([TABLE_X, TABLE_Y, TABLE_X + TABLE_W, TABLE_Y + TABLE_HEADER_H],
                            radius=8, fill=TABLE_HEADER_BG)
    # Cover bottom-rounded corners of header so data rows attach flush
    draw.rectangle([TABLE_X, TABLE_Y + TABLE_HEADER_H - 8,
                    TABLE_X + TABLE_W, TABLE_Y + TABLE_HEADER_H],
                   fill=TABLE_HEADER_BG)

    # Header cell text
    # Competitor column header
    _draw_text_centered(draw, "Competitor", fonts["table_header"],
                        _col_x(0), TABLE_Y, _col_w(0), TABLE_HEADER_H, HEADER_TEXT)

    # System column headers (may be two lines)
    for i, label in enumerate(SYSTEM_LABELS):
        cx = _col_x(i + 1)
        cw = _col_w(i + 1)
        lines = label.split("\n")
        if len(lines) == 2:
            f = fonts["table_header_small"]
            lh = draw.textbbox((0, 0), lines[0], font=f)[3]
            gap_between = 2
            total = lh * 2 + gap_between
            start_y = TABLE_Y + (TABLE_HEADER_H - total) // 2
            for j, line in enumerate(lines):
                bbox = draw.textbbox((0, 0), line, font=f)
                tw = bbox[2] - bbox[0]
                draw.text((cx + (cw - tw) // 2, start_y + j * (lh + gap_between)),
                          line, font=f, fill=HEADER_TEXT)
        else:
            _draw_text_centered(draw, label, fonts["table_header"],
                                cx, TABLE_Y, cw, TABLE_HEADER_H, HEADER_TEXT)

    # Vertical column dividers in header
    for i in range(1, 5):
        dx = _col_x(i)
        draw.line([(dx, TABLE_Y), (dx, TABLE_Y + TABLE_HEADER_H)], fill=(255, 255, 255, 80))

    # Data rows
    rp_rank_lookup = {row["name"]: row["ranks"][0] for row in rows if row["ranks"][0] is not None}

    for row_i, row in enumerate(rows):
        ry = TABLE_Y + TABLE_HEADER_H + row_i * actual_row_h
        row_bg = EVEN_ROW_BG if row_i % 2 == 1 else ODD_ROW_BG

        # Row background
        is_last = row_i == len(rows) - 1
        if is_last:
            draw.rounded_rectangle([TABLE_X, ry, TABLE_X + TABLE_W, TABLE_Y + TABLE_H],
                                    radius=8, fill=row_bg)
            draw.rectangle([TABLE_X, ry, TABLE_X + TABLE_W, ry + 8], fill=row_bg)
        else:
            draw.rectangle([TABLE_X, ry, TABLE_X + TABLE_W, ry + actual_row_h], fill=row_bg)

        # Horizontal divider above row
        draw.line([(TABLE_X, ry), (TABLE_X + TABLE_W, ry)], fill=TABLE_BORDER)

        # Competitor name (first names only)
        name_text = _truncate(draw, _first_name(row["name"]), fonts["name"],
                               COL_COMPETITOR - 24)
        name_bbox = draw.textbbox((0, 0), name_text, font=fonts["name"])
        name_h = name_bbox[3] - name_bbox[1]
        name_y = ry + (actual_row_h - name_h) // 2
        draw.text((_col_x(0) + 16, name_y), name_text, font=fonts["name"], fill=BODY_TEXT)

        # System rank cells
        for sys_i, rank in enumerate(row["ranks"]):
            cx = _col_x(sys_i + 1)
            cw = _col_w(sys_i + 1)

            # Winner cell highlight
            cell_bg = row_bg
            if rank == 1:
                cell_bg = WINNER_BG
                draw.rectangle([cx, ry, cx + cw, ry + actual_row_h], fill=cell_bg)

            # Vertical divider
            draw.line([(cx, ry), (cx, ry + actual_row_h)], fill=TABLE_BORDER)

            if rank is None:
                continue

            ordinal_text = _ordinal(rank)

            # Determine arrow based on comparison to RP rank (col 0)
            rp_rank = row["ranks"][0]
            arrow = ""
            arrow_color = BODY_TEXT
            if sys_i > 0 and rp_rank is not None:
                if rank < rp_rank:
                    arrow = "▲"
                    arrow_color = UP_COLOR
                elif rank > rp_rank:
                    arrow = "▼"
                    arrow_color = DOWN_COLOR

            rank_font = fonts["rank"]
            arrow_font = fonts["rank_small"]

            ord_bbox = draw.textbbox((0, 0), ordinal_text, font=rank_font)
            ord_w = ord_bbox[2] - ord_bbox[0]
            ord_h = ord_bbox[3] - ord_bbox[1]

            if arrow:
                arr_bbox = draw.textbbox((0, 0), arrow, font=arrow_font)
                arr_w = arr_bbox[2] - arr_bbox[0]
                total_w = ord_w + 3 + arr_w
                start_x = cx + (cw - total_w) // 2
                text_y = ry + (actual_row_h - ord_h) // 2
                draw.text((start_x, text_y), ordinal_text, font=rank_font, fill=BODY_TEXT)
                arr_h = arr_bbox[3] - arr_bbox[1]
                arr_y = ry + (actual_row_h - arr_h) // 2 + (ord_h - arr_h) // 2
                draw.text((start_x + ord_w + 3, arr_y), arrow, font=arrow_font, fill=arrow_color)
            else:
                _draw_text_centered(draw, ordinal_text, rank_font,
                                    cx, ry, cw, actual_row_h, BODY_TEXT)

    # Outer border of table
    draw.rounded_rectangle([TABLE_X, TABLE_Y, TABLE_X + TABLE_W, TABLE_Y + TABLE_H],
                            radius=8, outline=TABLE_BORDER, fill=None)

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
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
