"""LLM copy drafting (ARCHITECTURE §5g, the 🟡 Yellow tier): captions/threads from
STRUCTURED records only (never free-form), applying the CONTENT_SPEC §1 voice + copy
laws. Every draft is then gated by publish/guardrails before it can post.

DARK by default: the Claude call fires only when a credential is present (or
CHALK_COPY_LLM=1). Otherwise a deterministic, copy-law-compliant TEMPLATE runs, the
same shape the LLM is asked to produce, so the pipeline works (and is testable)
without a key. On any LLM error we fall back to the template (never crash, never post
free-form). Model defaults to the latest Claude (claude-api skill), CHALK_COPY_MODEL-overridable.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

from config.settings import _flag  # noqa: PLC2701 - shared flag reader

logger = logging.getLogger(__name__)

# Per the claude-api skill: default to the latest Claude; override via CHALK_COPY_MODEL.
COPY_MODEL = os.environ.get("CHALK_COPY_MODEL", "claude-opus-5")

SYSTEM = (
    "You are CHALK, a market-blind sports-prediction research project. Draft ONE short "
    "social caption from the STRUCTURED DATA you are given. Never invent numbers or facts. "
    "Voice: rigorous, dry, self-aware, anti-hype, the one honest machine in a feed of touts.\n"
    "Copy laws (hard): say 'a research project', never 'entertainment'; NO tout language "
    "(lock/guaranteed/hammer/easy money/etc.); NO methodology taglines ('market-blind', "
    "'build in public'); NO self-deprecating market lines ('doesn't beat the market'); "
    "attribute predictions to 'the model'; for an experiment, the NEXT line must explain what "
    "the next stat actually is. End with the research-project disclaimer."
)


def _pick_disclaimer(kind: str) -> str:
    return "A research project. Not betting advice." if kind in {"score", "carousel", "reel"} \
        else "A research project."


def _template(kind: str, r: Dict[str, Any]) -> str:
    d = _pick_disclaimer(kind)
    if kind == "experiment_log":
        verdict = "kept" if r.get("decision") == "keep" else "dropped"
        return (f"Experiment log: {r['name']}. "
                f"Tested: {r.get('hypothesis','')} "
                f"Result: {r['metric_label']} {r['before']} → {r['after']} ({r['delta']}) "
                f"over {r.get('seasons','')} seasons, {verdict}. "
                f"Next: {r.get('next_name','')}, {r.get('next_desc','')} {d}")
    if kind == "score":
        return (f"The model's call: {r['winner']} to win, {r['score']}. "
                f"Model confidence {r['conf']}%. Graded tomorrow, win or lose. {d}")
    if kind == "results":
        return (f"How yesterday's calls landed: {r['today_w']}–{r['today_l']} "
                f"({r['season_w']}–{r['season_l']} on the season). "
                f"We grade every call, the misses too. {d}")
    if kind == "carousel":
        return (f"Today's calls across the slate: {r.get('n_games','')} games, "
                f"the model's picks. Swipe for each. {d}")
    return d


def _llm_enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY")) or _flag("CHALK_COPY_LLM", default=False)


def draft_caption(kind: str, record: Dict[str, Any]) -> str:
    """Draft a caption for ``kind`` from the structured ``record``. LLM when enabled,
    else the compliant template. Always returns a string; never raises."""
    if not _llm_enabled():
        return _template(kind, record)
    try:  # pragma: no cover - live LLM path (dark until a key is set)
        import anthropic
        import json as _json
        client = anthropic.Anthropic()
        user = (f"kind: {kind}\nstructured data (the ONLY facts/numbers you may state):\n"
                f"{_json.dumps(record, ensure_ascii=False)}\n\n"
                f"Draft the caption now. Include the disclaimer: {_pick_disclaimer(kind)!r}.")
        resp = client.messages.create(model=COPY_MODEL, max_tokens=700, system=SYSTEM,
                                      messages=[{"role": "user", "content": user}])
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
        return text or _template(kind, record)
    except Exception as e:  # never crash / never post free-form on failure
        logger.warning("copy LLM draft failed (%s), using template fallback", e)
        return _template(kind, record)
