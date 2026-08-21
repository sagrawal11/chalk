"""Canonical player slug — the stable key for per-player artifacts (residual
models, caches).

One definition shared by the trainers and the predictor so keys never diverge.
This fixes PLANNING.md 9.1: training grouped residuals by the display
``PLAYER_NAME`` while the predictor looked up a ``.title()``-cased variant, so
"LeBron James" (dict key) never matched "Lebron James" (lookup) and the entire
residual tier silently collapsed to global-only for such players.
"""
from __future__ import annotations

import re


def player_slug(name: str) -> str:
    """Lowercase, underscore-joined, punctuation-stripped slug.

    "LeBron James" -> "lebron_james"; "De'Aaron Fox" -> "deaaron_fox";
    "P.J. Tucker" -> "pj_tucker"; "Devin_Booker" -> "devin_booker".
    """
    if name is None:
        return ""
    s = str(name).strip().lower().replace(" ", "_")
    s = re.sub(r"[^a-z0-9_]", "", s)   # drop apostrophes/periods/accents-stripped
    s = re.sub(r"_+", "_", s).strip("_")
    return s
