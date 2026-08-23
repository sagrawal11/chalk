"""The 🟡 Yellow draft queue (ARCHITECTURE §5h, OPS_RUNBOOK §4).

Pending posts live in publish/queue/drafts.json. Each draft targets ONE platform;
posting an item to Reddit + X + IG creates three drafts sharing the same base id.
Status flow: pending -> approved -> posted, or -> rejected, or -> escalated (🔴).

Nothing here posts — a draft only reaches a platform via publish/publisher.Publisher
after it is approved AND the guardrails passed (see publish/guardrails.py).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

QUEUE_DIR = Path(__file__).resolve().parent / "queue"
DRAFTS_PATH = QUEUE_DIR / "drafts.json"

PENDING, APPROVED, REJECTED, POSTED, ESCALATED = (
    "pending", "approved", "rejected", "posted", "escalated")


@dataclass
class Draft:
    id: str                                  # item key, e.g. "2026-08-23-exp-NFL-10"
    platform: str                            # reddit | x | ig
    kind: str                                # experiment_log | score | results | carousel | reel | triptych
    caption: str
    asset_paths: List[str] = field(default_factory=list)
    thread: List[str] = field(default_factory=list)     # optional multi-part (X)
    checks: Dict[str, Any] = field(default_factory=dict)  # guardrail verdicts
    source: Dict[str, Any] = field(default_factory=dict)  # the structured record copy was drafted from
    status: str = PENDING
    post_ref: Optional[Dict[str, Any]] = None

    def key(self) -> str:
        return f"{self.id}:{self.platform}"


class DraftQueue:
    def __init__(self, path: Optional[Path] = None):
        # Late-bound default so tests can monkeypatch DRAFTS_PATH.
        self.path = Path(path) if path is not None else DRAFTS_PATH

    def _load(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, rows: List[Dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

    def enqueue(self, draft: Draft) -> Draft:
        rows = self._load()
        rows = [r for r in rows if not (r["id"] == draft.id and r["platform"] == draft.platform)]
        rows.append(asdict(draft))
        self._save(rows)
        return draft

    def list(self, status: Optional[str] = None) -> List[Draft]:
        return [Draft(**r) for r in self._load() if status is None or r.get("status") == status]

    def get(self, draft_id: str, platform: str) -> Optional[Draft]:
        for r in self._load():
            if r["id"] == draft_id and r["platform"] == platform:
                return Draft(**r)
        return None

    def set_status(self, draft_id: str, platform: str, status: str,
                   post_ref: Optional[Dict[str, Any]] = None) -> None:
        rows = self._load()
        for r in rows:
            if r["id"] == draft_id and r["platform"] == platform:
                r["status"] = status
                if post_ref is not None:
                    r["post_ref"] = post_ref
        self._save(rows)

    def approve(self, draft_id: str, platform: str) -> None:
        self.set_status(draft_id, platform, APPROVED)

    def reject(self, draft_id: str, platform: str) -> None:
        self.set_status(draft_id, platform, REJECTED)
