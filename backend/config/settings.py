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


# --- Publishing / autonomy (M4) — every default is the safe, DARK posture. ---
_AUTONOMY_MODES = ("approve_all", "batch", "auto")


def autonomy_mode() -> str:
    """The 🟡 loosening dial (OPS_RUNBOOK §6). ``approve_all`` (default) => every
    Yellow item waits for the owner; ``batch`` => one daily batch to clear; ``auto``
    => gated items auto-post. The single tighten-back switch is AUTONOMY_MODE=approve_all."""
    raw = (_read_env("AUTONOMY_MODE") or "").strip().lower()
    return raw if raw in _AUTONOMY_MODES else "approve_all"


def publishing_killed() -> bool:
    """Global kill switch (OPS_RUNBOOK §11): when True, NO Publisher posts anything."""
    return _flag("CHALK_KILL_SWITCH", default=False)


def dry_run_default() -> bool:
    """When True (the dark default until launch), publishers LOG intent and never call
    a real platform API. Flip CHALK_DRY_RUN=0 only once creds + go-live are ready."""
    return _flag("CHALK_DRY_RUN", default=True)
