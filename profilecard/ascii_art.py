"""ASCII portrait for the left column of the neofetch card."""
from __future__ import annotations

import math

COLS, ROWS = 50, 37          # grid for 12px font / 14px line height
RAMP = " .:-=+*#%@"          # light -> dense


def placeholder() -> list[str]:
    """A neutral head-and-shoulders silhouette, used when no `ascii:` file is set."""
    rows = []
    for y in range(ROWS):
        row = []
        for x in range(COLS):
            dx = (x - COLS / 2 + 0.5) / (COLS / 2)
            head = ((dx / 0.38) ** 2 + ((y - 12) / 9.5) ** 2) <= 1
            neck = abs(dx) < 0.13 and 18 <= y <= 24
            shoulders = ((dx / 0.95) ** 2 + ((y - 38) / 15) ** 2) <= 1 and y >= 24
            if head or neck or shoulders:
                d = math.hypot(dx * 1.6, (y - 14) / 14)
                row.append(RAMP[min(len(RAMP) - 1, max(2, int(3 + d * 5)))])
            else:
                row.append(" ")
        rows.append("".join(row).rstrip())
    return rows


def load(path) -> list[str]:
    if path is None:
        return placeholder()
    text = path.read_text(encoding="utf-8").rstrip("\n")
    return text.split("\n") if text else placeholder()


def from_image(src: str, crop: tuple[int, int, int, int] | None = None,
               cols: int = COLS, rows: int = ROWS, mask_hue: tuple[int, int] | None = None,
               invert: bool = False) -> str:
    """Convert a portrait photo to ASCII.

    crop      (x0, y0, x1, y1) in pixels of the image resized to 400x400; default: whole image.
    mask_hue  (low, high) OpenCV hue range (0-179) of a plain backdrop to blank out, e.g. (95, 135) for blue.
    invert    swap dark/light, for pictures with a bright subject on a dark background.

    Needs `pip install -r requirements-ascii.txt` (OpenCV + NumPy).
    """
    try:
        import cv2
        import numpy as np
    except ImportError as e:
        raise SystemExit("The ascii command needs OpenCV: pip install -r requirements-ascii.txt") from e

    img = cv2.imread(src)
    if img is None:
        raise SystemExit(f"cannot read image: {src}")
    img = cv2.resize(img, (400, 400), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    eq = cv2.createCLAHE(clipLimit=5.0, tileGridSize=(6, 6)).apply(gray)
    eq = cv2.addWeighted(eq, 2.2, cv2.GaussianBlur(eq, (0, 0), 3), -1.2, 0)
    soft = cv2.GaussianBlur(gray, (0, 0), 1.5)
    edge = np.hypot(cv2.Sobel(soft, cv2.CV_32F, 1, 0), cv2.Sobel(soft, cv2.CV_32F, 0, 1))
    edge = np.clip(edge / max(np.percentile(edge, 97), 1e-6), 0, 1)

    x0, y0, x1, y1 = crop or (0, 0, 400, 400)
    size = (cols, rows)
    tone = eq[y0:y1, x0:x1] / 255.0
    dark = cv2.resize(tone if invert else 1 - tone, size, interpolation=cv2.INTER_AREA)
    edge = cv2.resize(edge[y0:y1, x0:x1], size, interpolation=cv2.INTER_AREA)
    val = np.clip(np.maximum(dark ** 1.15, edge * 0.9), 0, 1)

    if mask_hue:
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        bg = ((hsv[..., 0] > mask_hue[0]) & (hsv[..., 0] < mask_hue[1]) & (hsv[..., 1] > 90)).astype(np.uint8)
        bg = cv2.morphologyEx(bg, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        n, lab, stats, _ = cv2.connectedComponentsWithStats(1 - bg)
        fg = (lab == 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])).astype(np.uint8) if n > 1 else 1 - bg
        fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
        mask = cv2.resize(fg[y0:y1, x0:x1].astype(float), size, interpolation=cv2.INTER_AREA)
    else:
        mask = np.ones((rows, cols))

    n = len(RAMP) - 1
    return "\n".join(
        "".join(RAMP[max(1, round(val[y, x] * n))] if mask[y, x] > 0.5 else " " for x in range(cols)).rstrip()
        for y in range(rows)
    )
