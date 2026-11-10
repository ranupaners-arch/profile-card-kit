"""ASCII portrait for the left column of the neofetch card."""
from __future__ import annotations

import math

from .config import ConfigError

COLS, ROWS = 50, 37          # grid for 12px font / 14px line height
MAX_COLS = 52                # wider than this runs into the info column
SHADOW_SLACK = 0.15          # extra hue tolerance per unit of lightness below the sampled wall
HUE_TOLERANCE = 8.0          # minimum distance (Lab a/b) from the wall's hue that still counts as wall
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


def to_square(img, size: int = 400):
    """Fit any photo onto a size x size canvas without stretching it.

    The photo is scaled so its longer side is `size` and centred; the empty strips are
    filled by repeating the photo's edge pixels (a plain backdrop stays plain).
    """
    import cv2

    h, w = img.shape[:2]
    scale = size / max(h, w)
    img = cv2.resize(img, (max(1, round(w * scale)), max(1, round(h * scale))), interpolation=cv2.INTER_AREA)
    h, w = img.shape[:2]
    top, left = (size - h) // 2, (size - w) // 2
    return cv2.copyMakeBorder(img, top, size - h - top, left, size - w - left, cv2.BORDER_REPLICATE)


def find_face(gray):
    """Largest frontal face as (x, y, w, h) on the 400x400 canvas, or None."""
    import cv2

    if not hasattr(cv2, "CascadeClassifier"):    # removed in OpenCV 5: fall back to the head-width guess
        return None
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    if cascade.empty():
        return None
    faces = cascade.detectMultiScale(cv2.equalizeHist(gray), scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    return max(faces, key=lambda f: f[2] * f[3]) if len(faces) else None


def backdrop_mask(img):
    """1 where the pixel is backdrop: the same hue as the wall and connected to the image edge.

    A wall is rarely one colour: shadows change its lightness a lot but its hue little.
    So the backdrop is modelled as hue (Lab a, b) that follows lightness along a line, fitted
    on the top strip and the upper left/right edges (the lower edges are usually the person).
    A pixel is backdrop when its hue sits on that line and its lightness is within the range
    seen on the wall. Skin, clothes and hair differ in hue or are darker than any wall.
    """
    import cv2
    import numpy as np

    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    b, h = 12, lab.shape[0]
    samp = np.concatenate([lab[:b].reshape(-1, 3), lab[:h // 2, :b].reshape(-1, 3),
                           lab[:h // 2, -b:].reshape(-1, 3)])
    L = samp[:, 0]

    def fit(x, y):
        var = x.var()
        slope = float(np.cov(x, y, bias=True)[0, 1] / var) if var > 1.0 else 0.0
        return slope, float(y.mean() - slope * x.mean())

    keep = np.ones(len(samp), bool)
    for _ in range(3):                                   # refit without outliers (hair, a shoulder)
        (sa, ia), (sb, ib) = fit(L[keep], samp[keep, 1]), fit(L[keep], samp[keep, 2])
        res = np.hypot(samp[:, 1] - (sa * L + ia), samp[:, 2] - (sb * L + ib))
        keep = res < max(3.0, 2.5 * float(np.median(res[keep])))
    # Shadows can be much darker than the strips we sampled, but never as dark as hair or a
    # dark jacket: accept down to half the wall's median lightness, up to just above its brightest.
    lo, hi = 0.5 * float(np.median(L[keep])), float(np.percentile(L[keep], 99)) + 20
    # A saturated backdrop (a blue cloth) shifts hue more as its lightness changes than a pale
    # wall does, so the tolerance grows with the wall's own saturation.
    saturation = float(np.hypot(np.median(samp[keep, 1]) - 128, np.median(samp[keep, 2]) - 128))
    tolerance = max(HUE_TOLERANCE, 0.4 * saturation)

    full_L = lab[..., 0]
    dev = np.hypot(lab[..., 1] - (sa * full_L + ia), lab[..., 2] - (sb * full_L + ib))
    # The hue line is fitted on the lit part of the wall; deep shadow drifts away from it, so
    # allow a little more slack the further a pixel is below the sampled lightness.
    slack = SHADOW_SLACK * np.clip(float(np.percentile(L[keep], 5)) - full_L, 0, None)
    near = ((dev < tolerance + slack) & (full_L >= lo) & (full_L <= hi)).astype(np.uint8)
    near = cv2.morphologyEx(near, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, labels, _, _ = cv2.connectedComponentsWithStats(near)
    edge = set(np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))) - {0}
    return np.isin(labels, list(edge)).astype(np.uint8)


def auto_subject(img, cols: int, rows: int):
    """Find the subject in a portrait with a fairly plain backdrop.

    Backdrop: see backdrop_mask(). It is removed only where it connects to the image edge,
    so a white shirt enclosed by a jacket stays. The largest remaining blob is the subject.
    Crop: centred on the detected face when OpenCV finds one, otherwise sized from the
    width of the subject's top third. Both are at the card's portrait aspect ratio.
    Returns (foreground mask, (x0, y0, x1, y1)) on the 400x400 canvas.
    """
    import cv2
    import numpy as np

    bg = backdrop_mask(img)

    n, labels, stats, _ = cv2.connectedComponentsWithStats(1 - bg)
    if n < 2:
        return np.ones((400, 400), np.uint8), (0, 0, 400, 400)
    fg = (labels == 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    ys, xs = np.where(fg > 0)
    y0, y1 = ys.min(), ys.max()

    aspect = 0.696 * (cols / rows) / (COLS / ROWS)       # width / height of the crop
    face = find_face(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    if face is not None:
        fx, fy, fw, fh = (float(v) for v in face)
        w = min(400.0, fw * 2.3)
        top = max(0.0, fy - fh * 0.55)                    # leave room for hair
        centre = fx + fw / 2
    else:
        # Size the crop from the head (the top third of the subject), not the shoulders.
        band = fg[y0:y0 + max(8, int((y1 - y0) * 0.33))]
        bx = np.where(band.any(axis=0))[0]
        w = min(400.0, (bx.max() - bx.min()) * 1.45)
        top = max(0.0, y0 - 6.0)
        centre = (bx.min() + bx.max()) / 2
    h = w / aspect
    if top + h > 400:
        h = 400 - top
        w = h * aspect
    left = min(max(centre - w / 2, 0.0), 400 - w)
    return fg, (int(left), int(top), int(left + w), int(top + h))


def from_image(src: str, crop: tuple[int, int, int, int] | None = None,
               cols: int = COLS, rows: int = ROWS, mask_hue: tuple[int, int] | None = None,
               invert: bool = False, auto: bool = False) -> str:
    """Convert a portrait photo to ASCII.

    auto      detect the plain backdrop from the image border, remove it and crop to the
              subject. The easiest start; use crop/mask_hue to fine-tune.
    crop      (x0, y0, x1, y1) in pixels of the photo fitted onto a 400x400 canvas; default: whole canvas.
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
    img = to_square(img)
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
