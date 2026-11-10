"""ASCII portrait for the left column of the neofetch card."""
from __future__ import annotations

import math

from .config import ConfigError

COLS, ROWS = 50, 37          # grid for 12px font / 14px line height
MAX_COLS = 52                # wider than this runs into the info column
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
    if not text:
        return placeholder()
    lines = text.split("\n")
    widest = max(len(line) for line in lines)
    if widest > MAX_COLS:
        raise ConfigError(f"{path.name} is {widest} columns wide; the card fits at most {MAX_COLS}. "
                          f"Re-run `python -m profilecard ascii` (default width is {COLS}).")
    return lines


def auto_subject(img, cols: int, rows: int):
    """Find the subject in a portrait with a plain backdrop.

    The backdrop colour is the median of the image border. Everything close to it is
    removed, the largest remaining blob is the subject, and the crop is that blob's
    width, anchored at its top, at the card's portrait aspect ratio.
    Returns (foreground mask, (x0, y0, x1, y1)) on the 400x400 image.
    """
    import cv2
    import numpy as np

    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    b = 12
    border = np.concatenate([lab[:b].reshape(-1, 3), lab[-b:].reshape(-1, 3),
                             lab[:, :b].reshape(-1, 3), lab[:, -b:].reshape(-1, 3)])
    dist = np.linalg.norm(lab - np.median(border, axis=0), axis=2)
    bg = cv2.morphologyEx((dist < 28).astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(1 - bg)
    if n < 2:
        return np.ones((400, 400), np.uint8), (0, 0, 400, 400)
    fg = (labels == 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    ys, xs = np.where(fg > 0)
    y0, y1 = ys.min(), ys.max()
    # Size the crop from the head (the top third of the subject), not the shoulders.
    band = fg[y0:y0 + max(8, int((y1 - y0) * 0.33))]
    bx = np.where(band.any(axis=0))[0]
    aspect = 0.696 * (cols / rows) / (COLS / ROWS)       # width / height of the crop
    w = min(400.0, (bx.max() - bx.min()) * 1.45)
    top = max(0.0, y0 - 6.0)
    h = w / aspect
    if top + h > 400:
        h = 400 - top
        w = h * aspect
    left = min(max((bx.min() + bx.max()) / 2 - w / 2, 0.0), 400 - w)
    return fg, (int(left), int(top), int(left + w), int(top + h))


def from_image(src: str, crop: tuple[int, int, int, int] | None = None,
               cols: int = COLS, rows: int = ROWS, mask_hue: tuple[int, int] | None = None,
               invert: bool = False, auto: bool = False) -> str:
    """Convert a portrait photo to ASCII.

    auto      detect the plain backdrop from the image border, remove it and crop to the
              subject. The easiest start; use crop/mask_hue to fine-tune.
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

    auto_fg = None
    if auto:
        auto_fg, auto_crop = auto_subject(img, cols, rows)
        crop = crop or auto_crop
    x0, y0, x1, y1 = crop or (0, 0, 400, 400)
    size = (cols, rows)
    tone = eq[y0:y1, x0:x1] / 255.0
    dark = cv2.resize(tone if invert else 1 - tone, size, interpolation=cv2.INTER_AREA)
    edge = cv2.resize(edge[y0:y1, x0:x1], size, interpolation=cv2.INTER_AREA)
    val = np.clip(np.maximum(dark ** 1.15, edge * 0.9), 0, 1)

    if auto_fg is not None and not mask_hue:
        mask = cv2.resize(auto_fg[y0:y1, x0:x1].astype(float), size, interpolation=cv2.INTER_AREA)
    elif mask_hue:
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
