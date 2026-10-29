"""In-house line-art sport icons (CONTENT_SPEC §2): ink outline + a single red
accent, no trademarked league/team marks. Reused across cards + the carousel."""

# viewBox-normalized SVGs; callers set width/height via the wrapping element.
FOOTBALL = (
    '<svg viewBox="0 0 120 80" width="34" height="23" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M14 40 Q60 9 106 40 Q60 71 14 40 Z" stroke="#141210" stroke-width="6" stroke-linejoin="round"/>'
    '<path d="M60 27 V53" stroke="#D6482B" stroke-width="6" stroke-linecap="round"/>'
    '<path d="M50 34 H70 M50 40 H70 M50 46 H70" stroke="#D6482B" stroke-width="6" stroke-linecap="round"/>'
    '</svg>'
)
BASKETBALL = (
    '<svg viewBox="0 0 80 80" width="28" height="28" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<circle cx="40" cy="40" r="34" stroke="#141210" stroke-width="5"/>'
    '<path d="M6 40 H74" stroke="#141210" stroke-width="4"/>'
    '<path d="M40 6 V74" stroke="#D6482B" stroke-width="4"/>'
    '<path d="M15 15 Q40 40 15 65 M65 15 Q40 40 65 65" stroke="#141210" stroke-width="4"/>'
    '</svg>'
)
BASEBALL = (
    '<svg viewBox="0 0 80 80" width="28" height="28" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<circle cx="40" cy="40" r="34" stroke="#141210" stroke-width="5"/>'
    '<path d="M23 11 Q35 40 23 69 M57 11 Q45 40 57 69" stroke="#D6482B" stroke-width="4"/>'
    '</svg>'
)

BY_SPORT = {
    "nfl": FOOTBALL, "cfb": FOOTBALL,
    "nba": BASKETBALL,
    "mlb": BASEBALL,
    # nhl (puck), soccer (ball): drawn as those sports launch (CONTENT_SPEC §2).
}


def icon_for(sport: str) -> str:
    return BY_SPORT.get(str(sport).lower(), FOOTBALL)
