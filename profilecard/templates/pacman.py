"""Add a running contribution counter to a Pac-Man contribution-graph SVG.

The SVG itself comes from abozanona/pacman-contribution-graph (see the workflow).
Every contribution square has an <animate attributeName="fill"> that switches it
to the empty colour when Pac-Man eats it. This module:
  1. reads the time each square (c-<week>-<day>) is eaten from the keyTimes,
  2. fetches per-day counts via GraphQL contributionCalendar (the same data the
     generator uses) and maps them onto squares with the generator's date maths
     (53 weeks ending this week),
  3. adds "<label>: N" under the grid. When a square is eaten the number rolls up
     odometer-style, flashes and swells slightly, and a small "+N" floats away.
     Pure SMIL (no JS), in sync with Pac-Man's dur and repeatCount,
  4. holds HOLD_MS at the end of each loop (keyTimes rescaled, last value held)
     so the final total stays visible before the loop restarts.
"""
from __future__ import annotations

import datetime as dt
import math
import re
import sys
from html import escape
from pathlib import Path

from .. import github
from ..config import Config
from ..themes import resolve

NAME = "pacman"
GRID_WIDTH = 53
EXTRA_H = 26                       # room under the grid for the counter
FLASH = {"dark": "#ffd33d", "light": "#bf8700"}
FONT = "ConsolasFallback,Consolas,Menlo,monospace"
MARK = "pacman-counter"
HOLD_MS = 3000
TICK = 0.05                        # seconds per rolling step (20 fps)
EASE = 0.3                         # share of the remainder added per step
FLOAT_S = 0.7                      # how long "+N" floats before fading


def out_path(cfg: Config, theme: str) -> Path:
    return cfg.output_dir / NAME / f"{theme}.svg"


def cell_counts(svg: str, calendar: dict[dt.date, int]) -> dict[tuple[int, int], int]:
    """Map dates to squares exactly like buildGrid() in the generator."""
    m = re.search(r"<generatedOn>([^<]+)</generatedOn>", svg)
    today = dt.datetime.fromisoformat(m.group(1).replace("Z", "+00:00")).date() if m else dt.date.today()
    latest = max((d for d, c in calendar.items() if c > 0), default=today)
    end = max(today, latest)
    weekday = (end.weekday() + 1) % 7                    # Sunday = 0 (getUTCDay)
    start = end - dt.timedelta(days=(GRID_WIDTH - 1) * 7 + weekday)
    cells = {}
    for d, c in calendar.items():
        if start <= d <= end and c > 0:
            cells[((d - start).days // 7, (d.weekday() + 1) % 7)] = c
    return cells


def eat_times(svg: str) -> tuple[dict[tuple[int, int], float], str, str]:
    """Time (0..1) each square turns empty, plus dur and repeatCount."""
    times, dur, rep = {}, None, "indefinite"
    pat = re.compile(r'<rect id="c-(\d+)-(\d+)"[^>]*fill="([^"]+)">\s*<animate attributeName="fill" '
                     r'dur="([^"]+)" repeatCount="([^"]+)"[^>]*?values="([^"]+)"\s*keyTimes="([^"]+)"')
    for m in pat.finditer(svg):
        x, y, empty, dur, rep, values, keys = m.groups()
        vals, kts = values.split(";"), [float(k) for k in keys.split(";")]
        for v, k in zip(vals[1:], kts[1:]):
            if v == empty:
                times[(int(x), int(y))] = k
                break
    if dur is None:
        found = re.search(r'id="pacman"[\s\S]*?dur="([^"]+)"', svg)
        if not found:
            raise ValueError("not a pacman-contribution-graph SVG (no animated squares found)")
        dur = found.group(1)
    return times, dur, rep


def ms(d: str) -> float:
    return float(d[:-2]) if d.endswith("ms") else float(d.rstrip("s")) * 1000


def roll_frames(events: list[tuple[float, int]], length: float) -> list[tuple[float, int]]:
    """Simulate a number chasing the true total (odometer style).

    Each TICK the number rises by ceil(remainder * EASE): small jumps finish at
    once, big ones roll for ~0.5-1 s and slow down exactly at the total. If the
    next square is eaten while still rolling, the target rises too, so the number
    never jumps and always ends exactly on the total.
    """
    frames, shown, i, target, t = [(0.0, 0)], 0, 0, 0, 0.0
    while t < length:
        while i < len(events) and events[i][0] <= t + 1e-9:
            target = events[i][1]
            i += 1
        if shown < target:
            shown += max(1, math.ceil((target - shown) * EASE))
            frames.append((t, shown))
        t = round(t + TICK, 6)
    return frames


def pulse_track(starts: list[float], length: float, rise: float, fall: float,
                peak: str, base: str) -> tuple[str, str]:
    """Linear keyTimes/values: rise to `peak`, then back to `base`, per event."""
    pts = [(0.0, base)]
    for j, t in enumerate(starts):
        nxt = starts[j + 1] if j + 1 < len(starts) else length
        if t <= pts[-1][0]:
            continue
        pts.append((t, base))
        a = min(t + rise, nxt - 1e-3)
        pts.append((a, peak))
        b = min(a + fall, nxt - 2e-3)
        if b > a:
            pts.append((b, base))
    if pts[-1][0] < length:
        pts.append((length, pts[-1][1]))
    kt = ";".join(f"{x / length:.5f}" for x, _ in pts)
    return kt, ";".join(v for _, v in pts)


def counter_svg(events: list[tuple[float, int]], length_ms: float, rep: str,
                c: dict, y: float, label: str) -> tuple[str, int]:
    """events: (second eaten, running total) on a timeline of length_ms."""
    L = length_ms / 1000
    dur = f"{length_ms:.0f}ms"
    vx = (len(label) + 2) * 8.4                           # 14px monospace ~0.6em
    total = events[-1][1] if events else 0
    px = vx + len(f"{total:,}") * 8.4 + 10                # position of "+N"
    head = f'dur="{dur}" repeatCount="{rep}"'
    parts = [f'<g id="{MARK}" font-family="{FONT}" font-size="14px">',
             f'<text x="0" y="{y}" fill="{c["key"]}">{escape(label)}<tspan fill="{c["cc"]}">:</tspan></text>']

    # Rolling number: one <text> per value, shown discretely in its time window.
    starts = [t for t, _ in events]
    kt, vals = pulse_track(starts, L, 0.06, 0.35, c["flash"], c["value"])
    skt, svals = pulse_track(starts, L, 0.06, 0.30, "1.22", "1")
    parts.append(f'<g transform="translate({vx:.1f},{y})"><g fill="{c["value"]}">'
                 f'<animate attributeName="fill" {head} calcMode="linear" keyTimes="{kt}" values="{vals}"/>'
                 f'<animateTransform attributeName="transform" type="scale" {head} calcMode="linear" '
                 f'keyTimes="{skt}" values="{svals}"/>')
    frames = roll_frames(events, L)
    for j, (t, v) in enumerate(frames):
        nxt = frames[j + 1][0] if j + 1 < len(frames) else None
        if j == 0:
            anim = f'values="visible;hidden" keyTimes="0;{nxt / L:.5f}"' if nxt is not None else ""
        elif nxt is None:
            anim = f'values="hidden;visible" keyTimes="0;{t / L:.5f}"'
        else:
            anim = f'values="hidden;visible;hidden" keyTimes="0;{t / L:.5f};{nxt / L:.5f}"'
        a = f'<animate attributeName="visibility" {head} calcMode="discrete" {anim}/>' if anim else ""
        parts.append(f'<text visibility="{"visible" if j == 0 else "hidden"}">{v:,}{a}</text>')
    parts.append("</g></g>")

    # Small "+N" that floats up and fades next to the number.
    prev = 0
    for j, (t, v) in enumerate(events):
        n, prev = v - prev, v
        nxt = events[j + 1][0] if j + 1 < len(events) else L
        # Only one "+N" at a time: the old one vanishes when the next square is eaten.
        a, b = t / L, max(min(t + FLOAT_S, nxt, L), t + 0.02) / L
        parts.append(
            f'<text x="{px:.1f}" y="{y}" font-size="12px" fill="{c["flash"]}" opacity="0">+{n:,}'
            f'<animate attributeName="opacity" {head} calcMode="linear" '
            f'keyTimes="0;{a:.5f};{a + 0.00001:.5f};{b:.5f};1" values="0;0;1;0;0"/>'
            f'<animateTransform attributeName="transform" type="translate" {head} calcMode="linear" '
            f'keyTimes="0;{a:.5f};{b:.5f};1" values="0,0;0,0;0,-12;0,-12"/></text>')
    parts.append("</g>")
    return "".join(parts), len(frames)


def add_hold(svg: str, dur: str) -> str:
    """Extend every animation with this `dur` by HOLD_MS, holding the last frame."""
    d = ms(dur)
    scale = d / (d + HOLD_MS)

    def fix(m: re.Match) -> str:
        tag = m.group(0)
        if f'dur="{dur}"' not in tag or "keyTimes" not in tag:
            return tag
        kt = re.search(r'keyTimes="([^"]+)"', tag)
        vs = re.search(r'values="([^"]+)"', tag)
        keys = [float(k) * scale for k in kt.group(1).split(";")]
        vals = vs.group(1).split(";")
        keys.append(1.0)
        vals.append(vals[-1])
        tag = tag.replace(kt.group(0), 'keyTimes="' + ";".join(f"{k:.5f}" for k in keys) + '"')
        tag = tag.replace(vs.group(0), 'values="' + ";".join(vals) + '"')
        return tag.replace(f'dur="{dur}"', f'dur="{d + HOLD_MS:.0f}ms"')

    return re.sub(r"<animate(?:Transform)?\b[^>]*>", fix, svg)


def palette(cfg: Config, theme: str) -> dict:
    base = resolve(cfg.colors)[theme]
    c = {k: base[k] for k in ("key", "value", "cc")}
    c["flash"] = str((cfg.colors.get(theme) or {}).get("flash") or FLASH[theme])
    return c


def process(path: Path, theme: str, calendar: dict[dt.date, int], cfg: Config) -> int:
    svg = path.read_text(encoding="utf-8")
    if MARK in svg:
        sys.exit(f"{path}: counter already present (run on the freshly generated SVG).")
    times, dur, rep = eat_times(svg)
    counts = cell_counts(svg, calendar)
    missing = [k for k in counts if k not in times]
    if missing:
        print(f"WARNING {path}: {len(missing)} squares with contributions were never eaten: {missing[:5]}")
    byt: dict[float, int] = {}
    for k, t in times.items():
        if counts.get(k, 0) > 0:
            byt[t] = byt.get(t, 0) + counts[k]
    events, total = [], 0
    for t in sorted(byt):
        total += byt[t]
        events.append((t, total))

    m = re.search(r'<svg width="(\d+)" height="(\d+)"', svg)
    if not m:
        raise ValueError(f"{path}: unexpected <svg> header")
    w, h = int(m.group(1)), int(m.group(2))
    svg = svg.replace(m.group(0), f'<svg width="{w}" height="{h + EXTRA_H}"', 1)
    svg = add_hold(svg, dur)
    D = ms(dur)
    sec = [(t * D / 1000, v) for t, v in events]
    block, nframes = counter_svg(sec, D + HOLD_MS, rep, palette(cfg, theme), h + 12, cfg.pacman_label)
    svg = svg.replace("</svg>", block + "</svg>")
    path.write_text(svg, encoding="utf-8")
    print(f"{path}: {len(events)} events, {nframes} number frames, total {total:,} (calendar {sum(counts.values()):,})")
    return total


def add_counter(cfg: Config, files: list[tuple[Path, str]] | None = None) -> None:
    """Add the counter to output/pacman/{dark,light}.svg (or the given path:theme pairs)."""
    files = files or [(out_path(cfg, t), t) for t in resolve(cfg.colors)]
    calendar = github.contribution_calendar(cfg.username)
    for path, theme in files:
        process(path, theme, calendar, cfg)
