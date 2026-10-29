"""Instagram publisher: INTERIM manual-post mode (ARCHITECTURE §5i).

Until Meta app-review clears, IG NEVER auto-posts: it stages the rendered asset to a
public R2 URL and returns a MANUAL-post marker for the owner to publish by hand.
(Flip to a real Graph API publish when access lands; the seam is here.)
"""
from __future__ import annotations

import datetime as dt
import os

from publish.publisher import PostRef, Publisher


class IGPublisher(Publisher):
    platform = "ig"
    interim_manual = True

    def _stage_to_r2(self, draft) -> str:
        bucket = os.environ.get("R2_BUCKET_NAME")
        if not (bucket and draft.asset_paths):
            return "(R2 staging pending: set R2_* creds + a rendered asset)"
        try:  # pragma: no cover - needs R2 creds
            from utils.storage import public_url
            return public_url(draft.asset_paths[0])
        except Exception:
            return "(R2 staging pending)"

    def _publish(self, draft) -> PostRef:
        # Interim: stage + hand off to a manual post; the Graph API is NOT called.
        url = self._stage_to_r2(draft)
        return PostRef("ig", f"manual-{draft.id}", url, False,
                       dt.datetime.now().isoformat(timespec="seconds"))
