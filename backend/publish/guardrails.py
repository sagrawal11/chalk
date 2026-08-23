"""The 🟡 automated pre-publish guardrail checks (CONTENT_SPEC §5 / ARCHITECTURE §5h).

Eight checks gate every Yellow draft BEFORE it can post or enter the batch:
  1. tout denylist            (hard fail -> block)
  2. retired-phrasing/stamp   (flag -> hold for human)
  3. numbers reconcile        (hard fail -> block; no hallucinated stats)
  4. disclaimer present       (hard fail -> block)
  5. NEXT-explains-the-stat   (experiment posts only; flag -> hold)
  6. on-voice                 (LLM; skipped without a key -> hold-neutral)
  7. tragedy/serious-injury   (any hit -> ESCALATE 🔴, never auto-post)
  8. idempotency              (already-posted -> block)

Gate: any hard fail (1/3/4/8) => "block"; a tragedy hit (7) => "escalate"; any soft
flag (2/5/6) => "escalate" (hold for the human — Constitution #4 "when in doubt, hold").
Pure + deterministic (the LLM checks degrade to a neutral hold without a key), so the
whole gate is testable in the dark.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# 1. Tout denylist (CONTENT_SPEC §1.5). Word-boundaried so "locked before tip" is fine.
_TOUT = [r"\block\b", r"\blocks\b", r"guarantee", r"sure thing", r"easy money",
         r"\bhammer\b", r"free money", r"can'?t lose", r"cannot lose", r"\bbankroll\b",
         r"mortal lock", r"\bprint\b", "🔒", "💰", "🔥"]
# 2. Retired phrasings / stamps + self-deprecating market lines (copy laws #2, #4).
_RETIRED = [r"for entertainment", r"build in public", r"market[- ]blind",
            r"every test logged", r"measured on historical walk[- ]forward",
            r"beat(s|ing)? the market", r"can'?t beat", r"do(es)?n'?t beat",
            r"lose(s)? to the market", r"matches the market", r"\bno edge\b"]
# 7. Tragedy / serious-injury (Constitution #5). Conservative -> escalate, never block-silently.
_TRAGEDY = [r"\bdied\b", r"\bdeath\b", r"\bdead\b", r"\bkilled\b", r"passed away",
            r"\bfatal\b", r"tragedy", r"tragic", r"hospitali[sz]ed", r"in the hospital",
            r"collapsed", r"life[- ]threatening", r"paraly[sz]ed", r"stretchered",
            r"carted off", r"torn acl", r"acl tear", r"concussion", r"serious injury",
            r"season[- ]ending", r"career[- ]ending"]

_PICK_KINDS = {"score", "carousel", "reel"}   # need "not betting advice" (game/pick cards)


@dataclass
class Check:
    name: str
    status: str            # pass | flag | fail | escalate | skip
    detail: str = ""


@dataclass
class GuardrailReport:
    gate: str                       # pass | block | escalate
    checks: List[Check] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {"gate": self.gate, "checks": [vars(c) for c in self.checks]}


def _found(patterns: List[str], text: str) -> List[str]:
    low = text.lower()
    hits = []
    for p in patterns:
        if p in ("🔒", "💰", "🔥"):
            if p in text:
                hits.append(p)
        elif re.search(p, low):
            hits.append(p)
    return hits


def _allowed_numbers(source: Dict[str, Any]) -> List[float]:
    """Every numeric value the source record legitimately contains, in the forms copy
    might state them (raw, rounded, and *100 for fractions), plus years + the 50 coin
    flip baseline."""
    vals: List[float] = [50.0]
    vals += [float(y) for y in range(1990, 2100)]

    def walk(x):
        if isinstance(x, bool):
            return
        if isinstance(x, (int, float)):
            v = float(x)
            vals.extend([v, round(v, 1), round(v, 2), abs(v), round(abs(v), 2)])
            if abs(v) < 1:                       # fraction -> percent
                vals.extend([round(v * 100, 1), round(v * 100, 2), round(v * 100)])
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v)
    walk(source)
    return vals


_NUM = re.compile(r"(\d+(?:\.\d+)?)(%?)")


def _caption_stat_numbers(text: str):
    """Numbers in the copy that look like STATS (have a decimal or % or sit in a
    score like 27-24). Plain small integers are ignored (counts are hard to enumerate)."""
    out = []
    scores = set()
    for m in re.finditer(r"\d+\s*[–\-]\s*\d+", text):        # score pairs
        a, b = re.findall(r"\d+", m.group())
        scores.update({float(a), float(b)})
    for m in _NUM.finditer(text):
        raw, pct = m.group(1), m.group(2)
        val = float(raw)
        is_stat = ("." in raw) or bool(pct) or (val in scores)
        if is_stat:
            out.append(val)
    return out


def _numbers_reconcile(caption: str, source: Dict[str, Any], tol: float = 0.06):
    if not source:
        return Check("numbers_reconcile", "skip", "no source record to reconcile against")
    allowed = _allowed_numbers(source)
    bad = [n for n in _caption_stat_numbers(caption)
           if not any(abs(n - a) <= tol for a in allowed)]
    if bad:
        return Check("numbers_reconcile", "fail", f"unsourced number(s): {sorted(set(bad))}")
    return Check("numbers_reconcile", "pass")


def run_guardrails(draft, *, store=None, on_voice=None) -> GuardrailReport:
    """Run all eight checks on a draft. ``on_voice`` is an optional callable
    (caption)->bool for the LLM voice check; without it, #6 is a neutral hold."""
    cap = draft.caption or ""
    kind = getattr(draft, "kind", "")
    checks: List[Check] = []

    tout = _found(_TOUT, cap)
    checks.append(Check("tout_denylist", "fail" if tout else "pass",
                        f"tout: {tout}" if tout else ""))

    retired = _found(_RETIRED, cap)
    checks.append(Check("retired_phrasing", "flag" if retired else "pass",
                        f"retired/stamp/self-deprecating: {retired}" if retired else ""))

    checks.append(_numbers_reconcile(cap, getattr(draft, "source", {}) or {}))

    need_nba = "not betting advice" in cap.lower()
    has_research = "a research project" in cap.lower()
    if not has_research or (kind in _PICK_KINDS and not need_nba):
        checks.append(Check("disclaimer", "fail", "missing required research-project disclaimer"))
    else:
        checks.append(Check("disclaimer", "pass"))

    if kind == "experiment_log":
        nd = (getattr(draft, "source", {}) or {}).get("next_desc", "")
        checks.append(Check("next_explains", "pass" if len(str(nd)) >= 15 else "flag",
                            "" if len(str(nd)) >= 15 else "NEXT lacks a plain-English explanation"))

    if on_voice is None:
        checks.append(Check("on_voice", "skip", "no LLM voice check configured (neutral hold)"))
    else:
        ok = bool(on_voice(cap))
        checks.append(Check("on_voice", "pass" if ok else "flag", "" if ok else "off-voice"))

    trag = _found(_TRAGEDY, cap + " " + str(getattr(draft, "source", {})))
    checks.append(Check("tragedy_screen", "escalate" if trag else "pass",
                        f"tragedy/injury: {trag}" if trag else ""))

    if store is not None and store.get(draft.id, draft.platform) is not None:
        checks.append(Check("idempotency", "fail", "already posted (would double-post)"))
    else:
        checks.append(Check("idempotency", "pass"))

    # Gate resolution.
    hard = {"tout_denylist", "numbers_reconcile", "disclaimer", "idempotency"}
    gate = "pass"
    if any(c.status == "fail" and c.name in hard for c in checks):
        gate = "block"
    elif any(c.status == "escalate" for c in checks):
        gate = "escalate"
    elif any(c.status == "flag" for c in checks):
        gate = "escalate"       # soft/ambiguous -> hold for the human (Constitution #4)
    return GuardrailReport(gate=gate, checks=checks)
