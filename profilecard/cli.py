"""Command line: python -m profilecard <command>."""
from __future__ import annotations

import argparse
import os
import sys
from html import escape
from pathlib import Path

from . import ascii_art
from .config import Config, ConfigError, load
from .templates import links, neofetch, pacman


def rel(cfg: Config, path: Path) -> str:
    return "./" + os.path.relpath(path, cfg.root).replace(os.sep, "/")


def picture(cfg: Config, dark: Path, light: Path, alt: str, width: str | None = None) -> str:
    w = f' width="{width}"' if width else ""
    return (f'<picture><source media="(prefers-color-scheme: dark)" srcset="{rel(cfg, dark)}">'
            f'<img alt="{escape(alt)}"{w} src="{rel(cfg, light)}"></picture>')


def write_snippet(cfg: Config) -> Path:
    """Write output/snippet.md: paste it into your README."""
    card = picture(cfg, neofetch.out_path(cfg, "dark"), neofetch.out_path(cfg, "light"), cfg.name.title())
    site = next((lk for lk in cfg.links if lk.type == "website"), None)
    blocks = [f'<a href="{escape(site.url)}">{card}</a>' if site else card]
    if cfg.links:
        n = len(cfg.links)
        row = "".join(
            f'<a href="{escape(lk.url)}">'
            + picture(cfg, cfg.output_dir / links.NAME / links.filename(i, lk, "dark"),
                      cfg.output_dir / links.NAME / links.filename(i, lk, "light"),
                      lk.label.title(), f"{100 / n:.1f}%")
            + "</a>"
            for i, lk in enumerate(cfg.links))
        blocks.append(f'<p align="left">{row}</p>')
    blocks.append(picture(cfg, pacman.out_path(cfg, "dark"), pacman.out_path(cfg, "light"),
                          "Pac-Man eating the contribution graph"))
    path = cfg.output_dir / "snippet.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    return path


def cmd_build(cfg: Config, args) -> None:
    written = neofetch.render(cfg) + links.render(cfg)
    written.append(write_snippet(cfg))
    for p in written:
        print(f"wrote {os.path.relpath(p, cfg.root)}")


def cmd_stats(cfg: Config, args) -> None:
    neofetch.update_stats(cfg)


def cmd_update(cfg: Config, args) -> None:
    cmd_build(cfg, args)
    cmd_stats(cfg, args)


def cmd_pacman(cfg: Config, args) -> None:
    files = None
    if args.files:
        files = []
        for spec in args.files:
            path, _, theme = spec.rpartition(":")
            if theme not in ("dark", "light") or not path:
                raise SystemExit(f"bad argument {spec!r}: use path:dark or path:light")
            files.append((Path(path), theme))
    pacman.add_counter(cfg, files)


def cmd_ascii(cfg: Config | None, args) -> None:
    crop = tuple(int(v) for v in args.crop.split(",")) if args.crop else None
    if crop is not None and len(crop) != 4:
        raise SystemExit("--crop needs four numbers: x0,y0,x1,y1 (on a 400x400 image)")
    hue = tuple(int(v) for v in args.mask_hue.split(",")) if args.mask_hue else None
    if hue is not None and len(hue) != 2:
        raise SystemExit("--mask-hue needs two numbers: low,high (OpenCV hue, 0-179)")
    print(ascii_art.from_image(args.image, crop=crop, mask_hue=hue, invert=args.invert))


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="profilecard", description=__doc__)
    p.add_argument("-c", "--config", default="profile.yaml", help="path to profile.yaml (default: ./profile.yaml)")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("build", help="render the card, link buttons and README snippet (no network)").set_defaults(fn=cmd_build)
    sub.add_parser("stats", help="fetch GitHub stats into the card (needs GITHUB_TOKEN or ACCESS_TOKEN)").set_defaults(fn=cmd_stats)
    sub.add_parser("update", help="build, then stats").set_defaults(fn=cmd_update)

    pc = sub.add_parser("pacman", help="add the contribution counter to the generated Pac-Man SVGs")
    pc.add_argument("files", nargs="*", metavar="PATH:THEME", help="default: output/pacman/{dark,light}.svg")
    pc.set_defaults(fn=cmd_pacman)

    a = sub.add_parser("ascii", help="turn a portrait photo into ASCII art (needs requirements-ascii.txt)")
    a.add_argument("image")
    a.add_argument("--crop", help="x0,y0,x1,y1 on a 400x400 version of the image")
    a.add_argument("--mask-hue", help="low,high OpenCV hue of a plain backdrop to remove, e.g. 95,135")
    a.add_argument("--invert", action="store_true", help="for a bright subject on a dark background")
    a.set_defaults(fn=cmd_ascii, no_config=True)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        cfg = None if getattr(args, "no_config", False) else load(args.config)
        args.fn(cfg, args)
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2
    return 0
