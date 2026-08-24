"""Experiment-log card generator (ARCHITECTURE §5g) — the signature content type.

Turns an ExperimentResult (a ledger row from experiments/) into the locked
Editorial-Terminal experiment-log card (templates/experiment_log.html): the
`tested X -> what it did -> what's next` engine, with an honest before/after chart.

Metric selection is Option C — the card features the metric that best tells each
experiment's honest story, via a FIXED uniform rule (`pick_display_metric`) so it is
never post-hoc cherry-picking. A DROPPED experiment renders without the red
"achievement" styling; duds are content (Constitution #1).

This builds the HTML; rasterization to PNG is done by the caller / html_render
(CONTENT_SPEC §6). CLI writes HTML for a ledger id so a headless browser can shoot it.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

TEMPLATES = Path(__file__).resolve().parent / "templates"
CHART_H = 150  # px — matches the template .bars height

# metric -> (card label, unit, higher_is_better, y-axis half-pad, formatter)
_METRICS = {
    "su_acc":         ("SU ACCURACY", "pp",  True,  0.020, lambda v: f"{v * 100:.1f}%"),
    "winner_logloss": ("LOG-LOSS",    "",    False, 0.010, lambda v: f"{v:.4f}"),
    "margin_mae":     ("MARGIN MAE",  "pts", False, 0.400, lambda v: f"{v:.2f}"),
    "total_mae":      ("TOTAL MAE",   "pts", False, 0.400, lambda v: f"{v:.2f}"),
    # Soccer is 3-way (home/draw/away): a draw is a real outcome, so the metrics differ.
    "three_way_logloss": ("3-WAY LOG-LOSS", "",   False, 0.010, lambda v: f"{v:.4f}"),
    "three_way_acc":     ("3-WAY ACCURACY", "pp", True,  0.020, lambda v: f"{v * 100:.1f}%"),
}

_DESC = {
    "su_acc": "Straight-up winner accuracy, walk-forward.",
    "winner_logloss": "Winner log-loss — lower means better-calibrated.",
    "margin_mae": "Average points off the final margin — lower is better.",
    "total_mae": "Average points off the game total — lower is better.",
    "three_way_logloss": "Home/draw/away log-loss — lower means better-calibrated.",
    "three_way_acc": "Home/draw/away hit rate, walk-forward.",
}


def pick_display_metric(result: Dict[str, Any]) -> str:
    """Option C: feature the most audience-legible metric that actually moved.

    A FIXED rule applied uniformly (never chosen after seeing which looks best):
    prefer SU accuracy if it moved >= 0.25pp, else margin MAE (>= 0.02 pts), else
    total MAE (>= 0.02 pts); if nothing moved much, show accuracy honestly (held/flat)
    rather than reaching for jargon (log-loss)."""
    cm, hm = result["champion_metrics"], result["challenger_metrics"]
    if "three_way_logloss" in cm:   # soccer (3-way): accuracy if it moved, else log-loss
        dacc = abs((hm.get("three_way_acc", 0) - cm.get("three_way_acc", 0)) * 100)
        return "three_way_acc" if dacc >= 0.25 else "three_way_logloss"
    dsu = abs((hm.get("su_acc", 0) - cm.get("su_acc", 0)) * 100)
    dmae = abs(hm.get("margin_mae", 0) - cm.get("margin_mae", 0))
    dtot = abs(hm.get("total_mae", 0) - cm.get("total_mae", 0))
    if dsu >= 0.25:
        return "su_acc"
    if dmae >= 0.02:
        return "margin_mae"
    if dtot >= 0.02:
        return "total_mae"
    return "su_acc"


def _seasons(window: Optional[str]) -> Optional[int]:
    try:
        a, b = str(window).replace("–", "-").split("-")[:2]
        return int(b) - int(a) + 1
    except Exception:
        return None


def _fill(tpl: str, tokens: Dict[str, Any]) -> str:
    for k, v in tokens.items():
        tpl = tpl.replace(f"%%{k}%%", str(v))
    return tpl


def build_experiment_log_html(result: Dict[str, Any], *, metric: str = "auto",
                              next_exp: Optional[Dict[str, Any]] = None,
                              verdict_note: Optional[str] = None,
                              handle: str = "@playthechalk") -> str:
    """Fill the experiment-log template from a ledger row (ExperimentResult).
    ``metric='auto'`` uses the Option-C selector."""
    if metric == "auto":
        metric = pick_display_metric(result)
    label, unit, higher_better, pad, fmt = _METRICS[metric]
    before = float(result["champion_metrics"][metric])
    after = float(result["challenger_metrics"][metric])
    lo, hi = min(before, after), max(before, after)
    # Honest y-axis: wide enough that a small delta looks small (never truncated to 0).
    ymin, ymax = lo - pad, hi + pad * 0.35
    span = (ymax - ymin) or 1.0
    def bar_h(v: float) -> int:
        return max(6, round((v - ymin) / span * CHART_H))

    if metric == "su_acc":
        d = (after - before) * 100
        delta_big = f"{d:+.2f}" if abs(d) < 0.1 else f"{d:+.1f}"   # 2 decimals for sub-0.1pp
    else:
        delta_big = f"{after - before:+.2f}"

    kept = result.get("decision") == "keep"
    seasons = _seasons(result.get("eval_window"))
    desc = _DESC[metric] + (f" {seasons} seasons." if seasons else "")
    if verdict_note is None:
        verdict_note = ("Marginal — but it earns its place." if kept
                        else "No lift on the primary metric — dropped, honestly.")
    metric_label = label + ("" if higher_better else " ↓")   # "lower is better" cue

    ne = next_exp or {}
    tpl = (TEMPLATES / "experiment_log.html").read_text(encoding="utf-8")
    tokens = {
        "STATE": "kept" if kept else "dropped",
        "ID": result["id"], "TITLE": result["name"],
        "TESTED": result.get("hypothesis", ""),
        "WINDOW": f"{seasons} SEASONS" if seasons else (result.get("eval_window") or ""),
        "METRIC_LABEL": metric_label, "YRANGE": f"{fmt(ymin)}–{fmt(ymax)}",
        "BAR_DELTA": delta_big, "BEFORE_V": fmt(before), "AFTER_V": fmt(after),
        "BEFORE_H": bar_h(before), "AFTER_H": bar_h(after),
        "DELTA_BIG": delta_big, "DELTA_UNIT": unit,
        "METRIC_DESC": desc, "VERDICT": "KEPT" if kept else "DROPPED",
        "VERDICT_NOTE": verdict_note,
        "NEXT_NAME": ne.get("name", "—"), "NEXT_ID": ne.get("id", ""),
        "NEXT_DESC": ne.get("hypothesis", ""),
        "HANDLE": handle,
    }
    return _fill(tpl, tokens)


def card_from_ledger(exp_id: str, *, metric: str = "auto", next_id: Optional[str] = None) -> str:
    from experiments import ledger, roadmap
    rows = [r for r in ledger.load_ledger() if r.get("id") == exp_id]
    if not rows:
        raise SystemExit(f"no ledger row for {exp_id}")
    result = rows[-1]
    ne = roadmap.get_experiment(roadmap.load_roadmap(), result["sport"], next_id) if next_id else None
    return build_experiment_log_html(result, metric=metric, next_exp=ne)


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Render an experiment-log card (HTML) from a ledger row.")
    ap.add_argument("--id", required=True)
    ap.add_argument("--metric", default="auto", choices=["auto", *_METRICS])
    ap.add_argument("--next", default=None, help="ledger/roadmap id for the NEXT block")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(card_from_ledger(a.id, metric=a.metric, next_id=a.next), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
