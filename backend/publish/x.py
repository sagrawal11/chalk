"""X (Twitter) publisher — API v2 + media; multi-part threads via reply-chain. The
real API call runs only when dry_run=False AND creds are present.
"""
from __future__ import annotations

import datetime as dt
import os

from publish.publisher import PostRef, Publisher

_REQUIRED = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET")


class XPublisher(Publisher):
    platform = "x"

    def _publish(self, draft) -> PostRef:  # pragma: no cover - live only
        missing = [k for k in _REQUIRED if not os.environ.get(k)]
        if missing:
            raise RuntimeError(f"x not configured (missing {missing}) — stays dark")
        import tweepy  # imported only on a live post
        client = tweepy.Client(
            consumer_key=os.environ["X_API_KEY"], consumer_secret=os.environ["X_API_SECRET"],
            access_token=os.environ["X_ACCESS_TOKEN"], access_token_secret=os.environ["X_ACCESS_SECRET"])
        media_ids = None
        if draft.asset_paths:
            auth = tweepy.OAuth1UserHandler(
                os.environ["X_API_KEY"], os.environ["X_API_SECRET"],
                os.environ["X_ACCESS_TOKEN"], os.environ["X_ACCESS_SECRET"])
            api = tweepy.API(auth)
            media_ids = [api.media_upload(p).media_id for p in draft.asset_paths]
        parts = draft.thread or [draft.caption]
        last_id = first_id = None
        for i, text in enumerate(parts):
            resp = client.create_tweet(
                text=text, media_ids=(media_ids if i == 0 else None), in_reply_to_tweet_id=last_id)
            last_id = resp.data["id"]
            first_id = first_id or last_id
        return PostRef("x", str(first_id), f"https://x.com/i/web/status/{first_id}",
                       False, dt.datetime.now().isoformat(timespec="seconds"))
