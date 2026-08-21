"""LLM copy drafting (NEW — the 🟡 Yellow tier) — STUB.

Drafts captions/threads from *structured* experiment / prediction / result records
only (never free-form), applying the CONTENT_SPEC §1 voice + copy laws, into the
approval queue. Every draft is gated by ``publish/guardrails.py`` before it can post.

Wired in M4 (BUILD_PLAN M4; ARCHITECTURE.md §5g/§5h). Uses the latest Claude by
default (CONTENT_SPEC §1). This stub marks the seam so imports/structure resolve.
"""
from __future__ import annotations


def draft_caption(*_args, **_kwargs):  # pragma: no cover - implemented in M4
    raise NotImplementedError("content/copy.py is wired in M4 (see BUILD_PLAN).")
