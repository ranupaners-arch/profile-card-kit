"""Pixel-art link buttons: one SVG per button per theme.

README renders SVGs through <img>, so every button is its own image inside its
own <a>. Each image is 1/N of the card width and the gaps are drawn inside the
images, so the outer edges line up with the card.
"""
from __future__ import annotations

from html import escape
from pathlib import Path

from ..config import Config, Link
from ..themes import resolve
from .neofetch import WIDTH

NAME = "links"
PX = 3
MIN_GAP = 36
HEIGHT = 20 * PX
LABEL_FONT = 18
ADVANCE = 0.6
ICON_GAP = 12

MONITOR = """
##########
#........#
#.#......#
#..#.....#
#.#......#
#........#
##########
....##....
..######..
"""
MONITOR_CURSOR = """
..........
..........
..........
..........
....###...
"""
XLOGO = """
##......##
.##....##.
..##..##..
...####...
....##....
...####...
..##..##..
.##....##.
##......##
"""
ENVELOPE = """
##########
##......##
#.#....#.#
#..#..#..#
#...##...#
#........#
#........#
##########
"""


def sprite(art: str) -> str:
    """Bitmap '#' -> one <path> centred on (0,0); one pixel = PX."""
    rows = art.strip("\n").split("\n")
    h, w = len(rows), max(len(r) for r in rows)
    ox, oy = -w * PX / 2, -h * PX / 2
    d = []
    for y, row in enumerate(rows):
        x = 0
        while x < len(row):
            if row[x] == "#":
                s = x
                while x < len(row) and row[x] == "#":
                    x += 1
                d.append(f"M{ox + s*PX:g} {oy + y*PX:g}h{(x-s)*PX}v{PX}h{-(x-s)*PX}z")
            else:
                x += 1
    return "".join(d)


def website() -> str:
    base_rows = len(MONITOR.strip("\n").split("\n"))
    cur = sprite(MONITOR_CURSOR + "\n".join(["." * 10] * (base_rows - 5)))
    return (f'<path d="{sprite(MONITOR)}"/>'
            f'<path d="{cur}"><animate attributeName="opacity" values="1;0" '
            'keyTimes="0;0.5" dur="1.06s" calcMode="discrete" repeatCount="indefinite"/></path>')


def x() -> str:
    # Hops one pixel every 2 seconds.
    return ('<g><animateTransform attributeName="transform" type="translate" '
            f'values="0,0;0,-{PX};0,0" keyTimes="0;0.85;0.92" dur="2s" calcMode="discrete" '
            f'repeatCount="indefinite"/><path d="{sprite(XLOGO)}"/></g>')


def email() -> str:
    # Shakes like a notification.
    return ('<g><animateTransform attributeName="transform" type="translate" '
            f'values="0,0;-{PX},0;{PX},0;-{PX},0;{PX},0;0,0" keyTimes="0;0.7;0.74;0.78;0.82;0.86" '
            f'dur="2.4s" calcMode="discrete" repeatCount="indefinite"/><path d="{sprite(ENVELOPE)}"/></g>')


ICONS = {"website": website, "x": x, "email": email}


def mix(a: str, b: str, t: float) -> str:
    pa = [int(a[i:i+2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i+2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(p + (q - p) * t):02x}" for p, q in zip(pa, pb))


def stepped(x: float, y: float, w: float, h: float) -> str:
    """Rectangle with stair-stepped corners (pixel-art)."""
    return f"M{x+PX:g} {y:g}h{w-2*PX:g}v{PX}h{PX}v{h-2*PX:g}h{-PX}v{PX}h{-(w-2*PX):g}v{-PX}h{-PX}v{-(h-2*PX):g}h{PX}z"


def geometry(n: int) -> tuple[float, float, float]:
    """(slot width, button width, gap) for n buttons across the card."""
    slot = WIDTH / n
    button = max(20 * PX, int((WIDTH - (n - 1) * MIN_GAP) / n // PX) * PX)
    gap = (WIDTH - n * button) / (n - 1) if n > 1 else 0
    return slot, button, gap


def build(link: Link, slot: int, n: int, theme: str, colors: dict) -> str:
    c = colors[theme]
    slot_w, button_w, gap = geometry(n)
    # Button i starts at i*(button+gap) in the row; inside its own image it shifts
    # left by i*slot, so the first button is flush left and the last flush right.
    bx = slot * (button_w + gap) - slot * slot_w
    icon_w = 10 * PX
    label_w = len(link.label) * LABEL_FONT * ADVANCE
    left = bx + (button_w - icon_w - ICON_GAP - label_w) / 2
    mid = HEIGHT / 2 - 1.5
    outline = mix(c["bg"], c["fg"], 0.18)
    return f"""<?xml version='1.0' encoding='UTF-8'?>
<svg xmlns="http://www.w3.org/2000/svg" width="{slot_w:.3f}px" height="{HEIGHT}px"
     viewBox="0 0 {slot_w:.3f} {HEIGHT}" font-family="ConsolasFallback,Consolas,Menlo,monospace">
<style>
@font-face {{
  src: local('Consolas'), local('Consolas Bold');
  font-family: 'ConsolasFallback';
  font-display: swap;
  size-adjust: 109%;
}}
text {{white-space: pre;}}
.px {{shape-rendering: crispEdges;}}
</style>
<g class="px">
<path d="{stepped(bx, 0, button_w, HEIGHT)}" fill="{outline}"/>
<path d="{stepped(bx + PX, PX, button_w - 2*PX, HEIGHT - 2*PX)}" fill="{c['bg']}"/>
<rect x="{bx + 2*PX:g}" y="{HEIGHT - 2*PX}" width="{button_w - 4*PX}" height="{PX}" fill="{c['key']}"/>
<g fill="{c['key']}" transform="translate({left + icon_w/2:.2f},{mid:g})">{ICONS[link.type]()}</g>
</g>
<text x="{left + icon_w + ICON_GAP:.2f}" y="{mid + 0.35*LABEL_FONT:.2f}" font-size="{LABEL_FONT}px" fill="{c['fg']}">{escape(link.label)}</text>
</svg>
"""


def filename(i: int, link: Link, theme: str) -> str:
    return f"{i + 1}-{link.type}_{theme}.svg"


def render(cfg: Config, out_dir: Path | None = None) -> list[Path]:
    colors = resolve(cfg.colors)
    target = out_dir or cfg.output_dir / NAME
    paths = []
    if not cfg.links:
        return paths
    target.mkdir(parents=True, exist_ok=True)
    for theme in colors:
        for i, link in enumerate(cfg.links):
            path = target / filename(i, link, theme)
            path.write_text(build(link, i, len(cfg.links), theme, colors), encoding="utf-8")
            paths.append(path)
    return paths
