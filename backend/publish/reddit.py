"""Reddit publisher (PRAW): auto-publishes when live. Reddit + X carry the launch
(IG is manual-interim). The real API call runs only when dry_run=False AND creds are
present; otherwise the base Publisher.publish() dry-runs and this is never reached.
"""
from __future__ import annotations

import datetime as dt
import os

from publish.publisher import PostRef, Publisher

_REQUIRED = ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_REFRESH_TOKEN", "REDDIT_USER_AGENT")


class RedditPublisher(Publisher):
    platform = "reddit"

    def _publish(self, draft) -> PostRef:  # pragma: no cover - live only
        missing = [k for k in _REQUIRED if not os.environ.get(k)]
        if missing:
            raise RuntimeError(f"reddit not configured (missing {missing}), stays dark")
        import praw  # imported only on a live post
        reddit = praw.Reddit(
            client_id=os.environ["REDDIT_CLIENT_ID"],
            client_secret=os.environ["REDDIT_CLIENT_SECRET"],
            refresh_token=os.environ["REDDIT_REFRESH_TOKEN"],
            user_agent=os.environ["REDDIT_USER_AGENT"],
        )
        sub = reddit.subreddit(os.environ.get("REDDIT_SUBREDDIT", "playthechalk"))
        title = (draft.caption or draft.id).split("\n", 1)[0][:300]
        if draft.asset_paths:
            sub_ref = sub.submit_image(title=title, image_path=draft.asset_paths[0])
        else:
            sub_ref = sub.submit(title=title, selftext=draft.caption)
        return PostRef("reddit", sub_ref.id, f"https://reddit.com{sub_ref.permalink}",
                       False, dt.datetime.now().isoformat(timespec="seconds"))
