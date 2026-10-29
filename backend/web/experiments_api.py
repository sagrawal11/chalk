"""Public progression feed (ARCHITECTURE §5l): the "changelog".

Serves the experiment ledger + per-sport champion history so the frontend can render
the model's climb over time (every experiment, wins and duds). Read-only over the
committed artifacts (artifacts/experiments_ledger.jsonl + artifacts/<sport>/champion.json).
Registered on the main Flask app as a blueprint.
"""
from __future__ import annotations

from flask import Blueprint, jsonify

from experiments import ledger
from experiments.champion import FEATURE_BUILDERS, load_champion

bp = Blueprint("experiments_api", __name__)


@bp.route("/api/experiments")
def api_experiments():
    rows = ledger.load_ledger()
    sports = sorted({r.get("sport") for r in rows if r.get("sport")})
    champions = {}
    for s in sorted(set(sports) | set(FEATURE_BUILDERS)):
        try:
            c = load_champion(s)
            champions[s] = {
                "model_version": c.model_version, "rung": c.rung,
                "active_feature_builders": c.active_feature_builders,
                "cumulative_metrics": c.cumulative_metrics,
                "eval_window": c.eval_window, "holdout_season": c.holdout_season,
            }
        except Exception:
            pass  # no champion yet for that sport
    return jsonify({
        "experiments": rows,                                  # one row per experiment (kept + dud)
        "champions": champions,                               # current champion per sport
        "counts": {s: ledger.counts(s) for s in sports},      # run / kept / dropped (multiple-comparisons exposure)
    })
