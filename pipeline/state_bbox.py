"""Approximate state bounding boxes for sanity-checking coordinates (not authoritative).

Kept for the fetchers that import it; the table itself now lives in regions.py (2026-10-20),
which adds Canada's provinces and territories, Alaska's second box west of the 180th meridian and
Hawaii's northwestern islands. STATE_BBOX is the first box of each of the 50 states, as before.

Generous padding (~0.3-0.5 deg) around each state's extent, used only to flag likely
sign errors / transpositions / wrong-state rows for a human to look at -- never to
silently "correct" a coordinate.
"""

from regions import REGION_BOXES, US_STATES, flag_coordinate as _flag

STATE_BBOX = {code: REGION_BOXES[code][0] for code in US_STATES}


def flag_coordinate(abbr: str, lat: float, lon: float) -> str | None:
    """Returns a short problem code, or None if the coordinate looks plausible."""
    return _flag(abbr, lat, lon)
