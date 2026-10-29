"""Content generation: the product surface.

Turns normalized predictions / picks / track record into shareable, Instagram-
sized cards (+ captions with compliance disclaimers). Renderer is Pillow (works
everywhere, no browser); a higher-fidelity HTML/Chrome path can be added later.
"""
from content.render import (  # noqa: F401
    render_best_bet_card,
    render_props_card,
    render_record_card,
    render_score_card,
    render_slate,
)
