"""Scan the OG image template and find pixel coordinates for layout constants.

Run with:
    poetry run python scripts/measure_template.py

Prints column divider x-positions, row divider y-positions, and other layout
boundaries by scanning for #ddd border pixels in the template image.
"""

import sys
from pathlib import Path

from PIL import Image

if len(sys.argv) > 1:
    TEMPLATE_PATH = Path(sys.argv[1])
else:
    TEMPLATE_PATH = Path(__file__).parent.parent / "assets" / "og-image-template.png"
BORDER_COLOR = (221, 221, 221)  # #ddd
TOLERANCE = 5


def _close(pixel, target, tol=TOLERANCE):
    """Check if an RGB pixel is close to the target color."""
    return all(abs(a - b) <= tol for a, b in zip(pixel[:3], target))


def find_vertical_dividers(img, scan_y):
    """Scan horizontally at scan_y to find vertical divider x-positions."""
    dividers = []
    in_border = False
    for x in range(img.width):
        px = img.getpixel((x, scan_y))[:3]
        if _close(px, BORDER_COLOR):
            if not in_border:
                dividers.append(x)
                in_border = True
        else:
            in_border = False
    return dividers


def find_horizontal_dividers(img, scan_x):
    """Scan vertically at scan_x to find horizontal divider y-positions."""
    dividers = []
    in_border = False
    for y in range(img.height):
        px = img.getpixel((x, y))[:3] if False else img.getpixel((scan_x, y))[:3]
        if _close(px, BORDER_COLOR):
            if not in_border:
                dividers.append(y)
                in_border = True
        else:
            in_border = False
    return dividers


def find_blue_header_row(img, scan_x):
    """Find the y-range of the blue table header row.

    The blue header has RGB roughly (52, 152, 219). Scan vertically to find
    the contiguous blue region below the gradient header card.
    """
    BLUE = (52, 152, 219)
    tol = 15
    start = None
    end = None
    for y in range(img.height):
        px = img.getpixel((scan_x, y))[:3]
        if all(abs(a - b) <= tol for a, b in zip(px, BLUE)):
            if start is None:
                start = y
            end = y
        elif start is not None:
            break
    return start, end


def find_white_card(img, scan_x, below_y=180):
    """Find the y-range of the white card wrapper below the header."""
    WHITE = (255, 255, 255)
    tol = 3
    start = None
    end = None
    for y in range(below_y, img.height):
        px = img.getpixel((scan_x, y))[:3]
        if all(abs(a - b) <= tol for a, b in zip(px, WHITE)):
            if start is None:
                start = y
            end = y
        elif start is not None and y - end > 5:
            # Allow small gaps for border lines
            break
    return start, end


def sample_subtitle_region(img):
    """Find the subtitle text region in the header gradient.

    The header card is the gradient area at the top. The subtitle is the
    second line of text. We look for a region where text would be.
    """
    # Sample gradient colors at a few points in the subtitle region
    # The header gradient spans roughly y=16 to y=186 based on typical layout
    # Subtitle is roughly in the lower third of the header
    mid_x = img.width // 2
    samples = []
    for y in range(120, 170):
        px = img.getpixel((mid_x, y))[:3]
        samples.append((y, px))
    return samples


def main():
    img = Image.open(TEMPLATE_PATH).convert("RGBA")
    print(f"Image size: {img.width}x{img.height}")
    print()

    # Scan for vertical dividers at a data row y (about halfway through first data row)
    # First, find the blue header to know where data rows start
    mid_x = img.width // 2
    blue_start, blue_end = find_blue_header_row(img, mid_x)
    print(f"Blue header row: y={blue_start} to y={blue_end}")

    # Scan for vertical dividers at a point in the first data row
    data_row_y = blue_end + 30 if blue_end else 280
    vert_dividers = find_vertical_dividers(img, data_row_y)
    print(f"Vertical dividers at y={data_row_y}: {vert_dividers}")

    # Scan for horizontal dividers at a point in the middle of a system column
    if len(vert_dividers) >= 2:
        scan_x_for_rows = (vert_dividers[-2] + vert_dividers[-1]) // 2
    else:
        scan_x_for_rows = mid_x
    horiz_dividers = find_horizontal_dividers(img, scan_x_for_rows)
    print(f"Horizontal dividers at x={scan_x_for_rows}: {horiz_dividers}")

    # White card boundaries
    white_start, white_end = find_white_card(img, mid_x)
    print(f"White card: y={white_start} to y={white_end}")

    # Subtitle region sampling
    print()
    print("Subtitle region gradient samples:")
    samples = sample_subtitle_region(img)
    for y, px in samples[::5]:  # every 5th sample
        print(f"  y={y}: RGB{px}")

    # Print summary as Python constants
    print()
    print("=" * 60)
    print("Suggested Python constants:")
    print("=" * 60)
    if vert_dividers:
        print(f"# Card left edge (first vert divider): x={vert_dividers[0]}")
        print(f"# Card right edge (last vert divider): x={vert_dividers[-1]}")
        if len(vert_dividers) >= 6:
            # Expect: left-edge, col1|col2, col2|col3, col3|col4, col4|col5, right-edge
            print(f"COL_DIVIDERS = {vert_dividers}")
        else:
            print(f"VERT_DIVIDERS = {vert_dividers}")

    if horiz_dividers:
        print(f"ROW_DIVIDERS = {horiz_dividers}")

    if blue_start and blue_end:
        print(f"BLUE_HEADER_Y = ({blue_start}, {blue_end})")

    if white_start and white_end:
        print(f"WHITE_CARD_Y = ({white_start}, {white_end})")


if __name__ == "__main__":
    main()
