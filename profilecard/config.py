"""Load and validate profile.yaml."""
from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Item values equal to this token are filled in at build time from `birthday`.
UPTIME_TOKEN = "{uptime}"

LINK_TYPES = ("website", "x", "email")
DEFAULT_LABELS = {"website": "WEBSITE", "x": "X / TWITTER", "email": "EMAIL"}


class ConfigError(ValueError):
    """The config file is missing, unreadable or has an invalid field."""


class _Loader(yaml.SafeLoader):
    """SafeLoader that leaves yes/no/on/off, 1.10 and 0123 as the text the user typed.

    Plain YAML turns `Pets: no` into False and `Version: 1.10` into 1.1. Every value in
    this file is text for the card, so only dates (and null) are still interpreted.
    """


_Loader.yaml_implicit_resolvers = {
    ch: [(tag, rx) for tag, rx in resolvers
         if tag not in ("tag:yaml.org,2002:bool", "tag:yaml.org,2002:int", "tag:yaml.org,2002:float")]
    for ch, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


@dataclass
class Link:
    type: str
    url: str
    label: str


@dataclass
class Config:
    root: Path
    username: str
    name: str
    birthday: dt.date | None
    info: list          # [(key, value)] ; None = blank line
    contact: list       # [(key, value)] ; None = blank line
    links: list[Link]
    ascii_path: Path | None
    colors: dict
    output_dir: Path
    cache_dir: Path
    pacman_label: str = "Contributions"
    pacman: bool = True
    extra: dict = field(default_factory=dict)


def _items(raw, where: str) -> list:
    """Turn a YAML list of `{key: value}` maps (or blanks) into [(key, value)]."""
    out: list = []
    for entry in raw or []:
        if entry is None or entry == "":
            out.append(None)  # blank line
        elif isinstance(entry, dict) and len(entry) == 1:
            ((k, v),) = entry.items()
            out.append((str(k), "" if v is None else str(v)))
        else:
            raise ConfigError(
                f"{where}: each entry must be a single `Key: value` pair or an empty line, got {entry!r}"
            )
    return out


def _bool(value, default: bool, where: str) -> bool:
    if value in (None, ""):
        return default
    text = str(value).strip().lower()
    if text in ("true", "yes", "on"):
        return True
    if text in ("false", "no", "off"):
        return False
    raise ConfigError(f"{where}: expected true or false, got {value!r}")


def _date(value, where: str) -> dt.date | None:
    if value in (None, ""):
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError as e:
        raise ConfigError(f"{where}: expected a date like 2000-01-31, got {value!r}") from e


def _links(raw) -> list[Link]:
    links = []
    for i, entry in enumerate(raw or []):
        if not isinstance(entry, dict) or "type" not in entry or "url" not in entry:
            raise ConfigError(f"links[{i}]: needs `type` and `url`")
        kind = str(entry["type"]).lower()
        if kind not in LINK_TYPES:
            raise ConfigError(f"links[{i}]: unknown type {kind!r}; choose from {', '.join(LINK_TYPES)}")
        url = str(entry["url"])
        if kind == "email" and not url.startswith("mailto:"):
            url = "mailto:" + url
        links.append(Link(kind, url, str(entry.get("label") or DEFAULT_LABELS[kind]).upper()))
    return links


def load(path: str | os.PathLike = "profile.yaml") -> Config:
    path = Path(path).resolve()
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=_Loader)  # noqa: S506 - restricted SafeLoader subclass or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"{path.name} is not valid YAML: {e}") from e
    if not isinstance(data, dict):
        raise ConfigError(f"{path.name}: top level must be a mapping")

    root = path.parent
    # Precedence: USER_NAME env > profile.yaml > repository owner (set by GitHub Actions).
    username = (os.environ.get("USER_NAME") or data.get("github_username")
                or os.environ.get("GITHUB_REPOSITORY_OWNER") or "")
    username = str(username).strip()
    if not username:
        raise ConfigError("github_username is not set (profile.yaml, USER_NAME or GITHUB_REPOSITORY_OWNER)")

    ascii_path = data.get("ascii")
    if ascii_path:
        ascii_path = (root / str(ascii_path)).resolve()
        if not ascii_path.is_file():
            raise ConfigError(f"ascii: file not found: {ascii_path}")

    return Config(
        root=root,
        username=username,
        name=str(data.get("name") or username).upper(),
        birthday=_date(data.get("birthday"), "birthday"),
        info=_items(data.get("info"), "info"),
        contact=_items(data.get("contact"), "contact"),
        links=_links(data.get("links")),
        ascii_path=ascii_path or None,
        colors=data.get("colors") or {},
        output_dir=(root / str(data.get("output_dir") or "output")).resolve(),
        cache_dir=(root / "cache").resolve(),
        pacman_label=str(data.get("pacman_label") or "Contributions"),
        pacman=_bool(data.get("pacman"), True, "pacman"),
    )
