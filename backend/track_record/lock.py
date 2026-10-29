"""Immutable, timestamped, hashed daily prediction lock.

Writing a lock BEFORE tip-off (and refusing to overwrite it) is what makes the
public record honest, with no hindsight edits. The content hash makes tampering
detectable.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.paths import DATA_DIR

LOCKED_DIR = DATA_DIR / "predictions" / "locked"


def lock_path(sport: str, game_date: str) -> Path:
    return LOCKED_DIR / sport / f"{game_date}.json"


def _body(sport, game_date, game_predictions, prop_predictions, model_version) -> Dict[str, Any]:
    return {
        "sport": sport,
        "game_date": game_date,
        "model_version": model_version,
        "game_predictions": [gp.to_dict() for gp in game_predictions],
        "prop_predictions": [pp.to_dict() for pp in (prop_predictions or [])],
    }


def _hash(body: Dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def lock_predictions(
    sport: str,
    game_date: str,
    game_predictions: List[Any],
    prop_predictions: Optional[List[Any]] = None,
    model_version: str = "",
    *,
    locked_at: Optional[str] = None,
    force: bool = False,
) -> Path:
    p = lock_path(sport, game_date)
    if p.exists() and not force:
        raise FileExistsError(
            f"predictions for {sport} {game_date} are already locked at {p}; "
            "locks are immutable (use force=True only to correct a same-day error)"
        )
    body = _body(sport, game_date, game_predictions, prop_predictions, model_version)
    doc = {**body, "locked_at": locked_at or datetime.now(timezone.utc).isoformat(),
           "content_hash": _hash(body)}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=2, default=str))
    return p


def load_lock(sport: str, game_date: str) -> Dict[str, Any]:
    return json.loads(lock_path(sport, game_date).read_text())


def verify_lock(sport: str, game_date: str) -> bool:
    """True iff the on-disk lock's content hash still matches its body."""
    doc = dict(load_lock(sport, game_date))
    claimed = doc.pop("content_hash", None)
    doc.pop("locked_at", None)
    return claimed == _hash(doc)
