"""Publishing layer (ARCHITECTURE §5i): the ``Publisher`` seam (mirrors OddsProvider).

DARK by default and safe by construction:
  * ``publishing_killed()`` (the global kill switch) halts ALL posting.
  * ``dry_run_default()`` (True until launch) makes every publisher LOG intent and
    return a synthetic PostRef WITHOUT calling any real platform API.
  * a ``PostStore`` keyed by (draft_id, platform) enforces idempotency; an item is
    never double-posted, even across re-runs.

Real platform calls live in the per-platform adapters' ``_publish`` (reddit/x/ig),
reached only when a run is explicitly live (dry_run=False) AND credentials exist.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional, Sequence

from config.settings import dry_run_default, publishing_killed

logger = logging.getLogger(__name__)

QUEUE_DIR = Path(__file__).resolve().parent / "queue"
POSTED_PATH = QUEUE_DIR / "posted.jsonl"


@dataclass
class PostRef:
    platform: str
    ref_id: str
    url: str
    dry_run: bool
    posted_at: str


class PostStore:
    """Append-only idempotency store: (draft_id, platform) -> PostRef."""

    def __init__(self, path: Optional[Path] = None):
        # Late-bound default so tests can monkeypatch POSTED_PATH.
        self.path = Path(path) if path is not None else POSTED_PATH

    def _rows(self):
        if not self.path.exists():
            return []
        return [json.loads(ln) for ln in self.path.read_text(encoding="utf-8").splitlines() if ln.strip()]

    def get(self, draft_id: str, platform: str) -> Optional[PostRef]:
        for r in reversed(self._rows()):
            if r.get("draft_id") == draft_id and r.get("ref", {}).get("platform") == platform:
                return PostRef(**r["ref"])
        return None

    def record(self, draft_id: str, ref: PostRef) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"draft_id": draft_id, "ref": asdict(ref)}) + "\n")


class Publisher:
    """A platform adapter. Subclasses set ``platform`` and implement ``_publish``."""

    platform: str = ""

    def supports(self, platform: str) -> bool:
        return platform == self.platform

    def _publish(self, draft) -> PostRef:  # pragma: no cover - real API, live only
        raise NotImplementedError(f"{self.platform} live publish not wired")

    def publish(self, draft, *, dry_run: Optional[bool] = None,
                store: Optional[PostStore] = None) -> Optional[PostRef]:
        """Kill-switch + idempotency + dry-run wrapper around ``_publish``.
        Returns the PostRef (synthetic in dry-run), or None if the kill switch is on."""
        store = store or PostStore()
        if publishing_killed():
            logger.warning("kill switch ON, refusing to post %s (%s)", draft.id, self.platform)
            return None
        prior = store.get(draft.id, self.platform)
        if prior is not None:
            logger.info("idempotent skip: %s already on %s (%s)", draft.id, self.platform, prior.ref_id)
            return prior
        dry = dry_run_default() if dry_run is None else dry_run
        if dry:
            ref = PostRef(self.platform, f"dry-{draft.id}", "(dry-run)", True,
                          dt.datetime.now().isoformat(timespec="seconds"))
            logger.info("[dry-run] would post %s to %s", draft.id, self.platform)
        else:
            ref = self._publish(draft)
        store.record(draft.id, ref)
        return ref


class MultiPublisher:
    """Fan-out over platform adapters (mirrors odds/MultiProvider)."""

    def __init__(self, publishers: Sequence[Publisher]):
        self.publishers = list(publishers)

    def for_platform(self, platform: str) -> Optional[Publisher]:
        return next((p for p in self.publishers if p.supports(platform)), None)

    def publish(self, draft, **kw) -> Optional[PostRef]:
        pub = self.for_platform(draft.platform)
        if pub is None:
            raise ValueError(f"no publisher registered for platform {draft.platform!r}")
        return pub.publish(draft, **kw)
