"""Color themes. Override any key per theme with `colors:` in profile.yaml."""
from __future__ import annotations

THEMES = {
    "dark": dict(bg="#161b22", fg="#c9d1d9", key="#ffa657", value="#a5d6ff",
                 add="#3fb950", dele="#f85149", cc="#616e7f"),
    "light": dict(bg="#f6f8fa", fg="#24292f", key="#953800", value="#0a3069",
                  add="#1a7f37", dele="#cf222e", cc="#c2cfde"),
}


def resolve(overrides: dict | None = None) -> dict:
    """Return THEMES with the user's per-theme overrides applied."""
    overrides = overrides or {}
    out = {}
    for name, base in THEMES.items():
        custom = overrides.get(name) or {}
        out[name] = {**base, **{k: str(v) for k, v in custom.items() if k in base}}
    return out
