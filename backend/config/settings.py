"""Global runtime switches for the prediction engine.

``MARKET_BLIND`` is the product-defining flag. When True (the default), predictions
must NOT use any betting line as an input: every sport's predictor takes its pure
model / Poisson path and picks are generated from the model alone. The
market-anchored path is kept fully intact for the (opt-in) ROI-settlement work and
is reached only by setting ``MARKET_BLIND=0``.

Flags are read at call-time (not import-time) so tests and CI can flip them with
``monkeypatch.setenv`` without reimporting modules. Resolution mirrors
``sports.nba.live_odds._get_key``: process env first, then the repo/backend
``.env`` so a bare CLI run and the Docker stack agree.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

_TRUE = {"1", "true", "yes", "on", "t", "y"}
_FALSE = {"0", "false", "no", "off", "f", "n"}


def _read_env(name: str) -> Optional[str]:
    """``name`` from the process env, else the repo/backend ``.env``."""
    val = os.environ.get(name)
    if val is not None:
        return val
    # backend/config/settings.py -> parents[2] = repo root, parents[1] = backend
    for up in (2, 1):
        env = Path(__file__).resolve().parents[up] / ".env"
        if env.exists():
            for line in env.read_text().splitlines():
                s = line.strip()
                if s.startswith(f"{name}="):
                    return s.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _flag(name: str, default: bool) -> bool:
    raw = _read_env(name)
    if raw is None or raw == "":
        return default
    low = raw.strip().lower()
    if low in _TRUE:
        return True
    if low in _FALSE:
        return False
    return default


def market_blind() -> bool:
    """True => predictions ignore the betting line entirely (the brand default)."""
    return _flag("MARKET_BLIND", default=True)
