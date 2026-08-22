"""Load + query the pre-registered experiment roadmap (experiments/roadmap.yaml).

The roadmap is the pre-committed plan and is treated as READ-ONLY at runtime — the
runner never rewrites it (keeping the pre-registration honest and the file's comments
intact). What actually ran, and whether it was kept/dropped, lives in the append-only
ledger; `next_unrun` uses the ledger's run-ids to advance the queue.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

ROADMAP_PATH = Path(__file__).resolve().parent / "roadmap.yaml"


def load_roadmap(path: Path = ROADMAP_PATH) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def experiments_for(rm: dict, sport: str) -> List[dict]:
    return rm.get("sports", {}).get(sport, {}).get("experiments", [])


def keep_rule_for(rm: dict, sport: str, exp: dict) -> Dict[str, Any]:
    """Global default keep-rule, overridden by any per-experiment keep_rule."""
    base = dict(rm.get("defaults", {}).get("keep_rule", {}))
    base.update(exp.get("keep_rule") or {})
    return base


def get_experiment(rm: dict, sport: str, exp_id: str) -> Optional[dict]:
    for e in experiments_for(rm, sport):
        if e.get("id") == exp_id:
            return e
    return None


def next_unrun(rm: dict, sport: str, run_ids: set) -> Optional[dict]:
    """First `queued` experiment not already in the ledger."""
    for e in experiments_for(rm, sport):
        if e.get("status") == "queued" and e.get("id") not in run_ids:
            return e
    return None
