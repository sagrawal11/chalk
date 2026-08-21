"""Brand tokens for rendered content.

Identity/voice tokens (name, handle, accent color, disclaimer, hashtags) are
configurable without touching code:
  1. edit ``content/brand.json`` (friendliest — just fill in your values), or
  2. set env vars ``BRAND_BRAND`` / ``BRAND_HANDLE`` / ``BRAND_ACCENT_HEX`` /
     ``BRAND_DISCLAIMER`` / ``BRAND_HASHTAGS`` (env wins, handy for CI).
The dark palette, fonts, and canvas sizes are fixed design defaults.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Tuple

# --- configurable identity/voice (defaults are placeholders — set your own) ---
_DEFAULTS = {
    "BRAND": "HOOPS ORACLE",
    "HANDLE": "@hoops.oracle",
    "ACCENT_HEX": "#F5C518",
    "DISCLAIMER": (
        "Model projections for entertainment only — not betting advice. 21+ (18+ where legal). "
        "If you or someone you know has a gambling problem, call 1-800-GAMBLER."
    ),
    "HASHTAGS": "#NBA #NBAPredictions #PlayerProps #NBAPicks #Hoops",
}


def _hex_to_rgb(h: str) -> Tuple[int, int, int]:
    h = str(h).lstrip("#")
    if len(h) != 6:
        return (245, 197, 24)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _load_cfg() -> dict:
    cfg = dict(_DEFAULTS)
    jpath = Path(__file__).parent / "brand.json"
    if jpath.exists():
        try:
            cfg.update({k: v for k, v in json.loads(jpath.read_text()).items() if k in cfg and v})
        except Exception:
            pass
    for k in cfg:  # env overrides win (BRAND_BRAND, BRAND_HANDLE, ...)
        env = os.environ.get(f"BRAND_{k}")
        if env:
            cfg[k] = env
    return cfg


_cfg = _load_cfg()
BRAND = _cfg["BRAND"]
HANDLE = _cfg["HANDLE"]
DISCLAIMER = _cfg["DISCLAIMER"]
HASHTAGS = _cfg["HASHTAGS"]
ACCENT = _hex_to_rgb(_cfg["ACCENT_HEX"])

# Sport-specific hashtags (brand tag is derived from BRAND and appended).
_SPORT_HASHTAGS = {
    "nba": "#NBA #NBAPredictions #NBAPicks",
    "nfl": "#NFL #NFLPredictions #NFLPicks",
    "mlb": "#MLB #MLBPredictions",
    "nhl": "#NHL #NHLPredictions",
    "soccer": "#Soccer #Football #SoccerPredictions",
}


def hashtags_for(sport: str) -> str:
    tags = _SPORT_HASHTAGS.get(str(sport).lower())
    if not tags:
        return HASHTAGS
    brand_tag = "#" + "".join(BRAND.split()).title() if BRAND else ""
    return f"{tags} {brand_tag}".strip()

# --- fixed design palette (dark, high-contrast for mobile feeds) ---
BG = (11, 18, 32)
PANEL = (17, 26, 46)
TEXT = (255, 255, 255)
MUTED = (138, 147, 166)
WIN = (61, 220, 132)
LOSE = (255, 90, 95)

# Canvas sizes (Instagram).
FEED = (1080, 1350)       # 4:5 portrait feed post
STORY = (1080, 1920)      # 9:16 story / reel cover

# Font candidates (first that loads wins; falls back to Pillow default).
FONT_REGULAR = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
FONT_BOLD = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]
