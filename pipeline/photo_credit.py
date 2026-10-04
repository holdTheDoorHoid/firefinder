#!/usr/bin/env python3
"""Pulls a photographer credit out of a register photo's caption, when one is hiding there.

NHLR and FFLOS (pipeline/fetch_registers.py) share one site template whose captions often
carry the photographer where the structured credit field doesn't: "9/10/05--Cabin (Bob Eckler
photo-courtesy Bill Starr)" while the photo's own credit is just "National Historic Lookout
Register". This recognises a conservative set of unambiguous patterns -- "X photo", "photo by
X", "photo courtesy (of) X", "courtesy X", "X photo-courtesy Y", "(X collection)", "Photo: X",
"USFS photo" -- pulls the credit out, and returns what's left of the caption.

Used by merge.py's photo_entry() (not fetch_registers.py): applying it at merge time, straight
off the already-committed data/sources/*.json captions, needs no re-crawl of nhlr.org/
firetower.org to benefit from an improved pattern -- the next merge run just picks it up.

Deliberately conservative: when a candidate credit doesn't look enough like a name/organisation
(see _looks_like_credit()), or the surrounding text doesn't match one of the shapes below, the
caption is left exactly as it was. False negatives (a credit stays buried) are fine; false
positives (plain caption prose mistaken for a name) are not.
"""
from __future__ import annotations

import re

# Capitalised-word phrase: 1-5 tokens, each starting with a capital letter (apostrophes,
# periods, hyphens and a trailing comma allowed within a token: "Michael T. Finch, Jr."),
# with a short list of lowercase connectors allowed between tokens ("City of Hamburg",
# "Friends of Red Hill"). Case-sensitive by construction -- capitalisation is the signal that
# a fragment is a name at all, so none of the regexes built from this get re.I; only their
# literal trigger words ("photo", "collection", "courtesy", "of") are matched case-insensitively,
# via inline (?i:...) groups.
_TOKEN = r"[A-Z][A-Za-z.'\-]*,?"
_CONNECTOR = r"(?:of|the|and|for|at)\s+"
_NAME_PHRASE = rf"{_TOKEN}(?:\s+(?:{_CONNECTOR})?{_TOKEN}){{0,4}}"
_NAME_SHAPE_RE = re.compile(rf"^{_NAME_PHRASE}$")

# Single capitalised words that would otherwise pass the shape check but are ordinary
# photo-description vocabulary, not a credit. Checked case-insensitively.
_NOT_A_NAME = {
    "historical", "vintage", "undated", "original", "color", "colour", "overview",
    "closeup", "panorama", "postcard", "unknown", "unidentified", "misc", "miscellaneous",
    "interior", "exterior", "aerial", "winter", "summer", "spring", "autumn", "current",
    "recent", "another", "same", "similar", "general", "wide", "scanned", "digitized",
}

# Qualifiers that may precede a bare year in leftover caption text ("Circa 1924", "Early
# 1950s") -- swallowed along with the year rather than kept as a stray caption.
_DATE_QUALIFIER = r"(?:circa|c\.?|early|late|mid|around|about)"
_MONTH = (r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
          r"aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)")
_YEAR = r"(?:1[89]\d{2}|20\d{2})s?"

_DATE_TOKEN_RE = re.compile(
    rf"^(?:{_DATE_QUALIFIER}|{_MONTH}|{_YEAR}|\d{{1,2}}(?:st|nd|rd|th)?)\.?,?$", re.I)


def _is_date_only(text: str) -> bool:
    """True for leftover caption text that is nothing but a date/qualifier ("1974",
    "Early 1950s", "October 11, 2008"), safe to drop rather than keep as a bare-date caption."""
    text = text.strip(" ,.-–")
    if not text:
        return True
    return all(_DATE_TOKEN_RE.match(tok) for tok in text.split())


def _looks_like_credit(who: str, *, level: str) -> bool:
    """Would `who` make a sensible credit by itself?

    level="loose": used for "courtesy"/"photo by" -- the trigger word itself is unambiguous,
      so `who` only needs to be short and not a run-on sentence.
    level="medium": used for "Photo: X" -- a real label/value convention, but one old-style
      register captions also use for a plain description ("Photo: 1936 L4 with new R6 under
      construction"), so `who` must additionally look like a name/phrase (see _NAME_SHAPE_RE).
    level="strict": used for "X photo"/"X collection" -- no trigger word at all, just shape, so
      a single word must be an ALL-CAPS acronym (USFS, NYS-DEC) rather than any capitalised
      word (which would also match ordinary vocabulary like "Historical" or "Vintage")."""
    who = who.strip().strip(",")
    if not who or len(who) > 80:
        return False
    if who.count(".") > 3:  # several sentences, or implausibly many abbreviations
        return False
    words = who.split()
    if len(words) > 10:
        return False
    if level == "loose":
        return True
    if any(w.strip(",.").lower() in _NOT_A_NAME for w in words):
        return False
    if len(words) == 1:
        token = words[0].rstrip(",")
        if level == "strict":
            letters = token.replace("-", "")
            return bool(re.fullmatch(r"[A-Z]+(?:-[A-Z]+)*", token)) and 2 <= len(letters) <= 8
        return bool(_NAME_SHAPE_RE.fullmatch(token))
    return bool(_NAME_SHAPE_RE.fullmatch(who))


def _strip_trailing_year(who: str) -> str:
    """"Ken Jones 2009" -> "Ken Jones": a year tacked on after the name (the photo's own
    `year` is already parsed from the whole caption elsewhere, so nothing is lost here)."""
    return re.sub(rf"\s+{_YEAR}$", "", who).strip()


_LEADING_DATE_RE = re.compile(
    rf"^(?:{_DATE_QUALIFIER}\.?\s+)?(?:{_MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+|"
    rf"\d{{1,2}}(?:st|nd|rd|th)?,?\s+(?:of\s+)?{_MONTH}\.?,?\s+)?{_YEAR}\s*[-,:]?\s*",
    re.I,
)

# Trigger-word patterns: (regex, validation level). An explicit word does some or all of the
# safety work, so `who` is validated more loosely than the no-trigger patterns below.
_TRIGGER_PATTERNS = [
    (re.compile(r"photos?\s+courtesy\s+(?:of\s+)?(?P<who>.+)", re.I), "loose"),
    (re.compile(r"courtesy\s+(?:of\s+)?(?P<who>.+)", re.I), "loose"),
    (re.compile(r"photos?\s+by\s+(?P<who>.+)", re.I), "loose"),
    (re.compile(r"photos?\s*:\s*(?P<who>.+)", re.I), "medium"),
]

# Two-name patterns: "<who> photo-courtesy <who2>" / "<who> collection-courtesy <who2>", a
# dash, comma or plain space before "courtesy". Both names are validated strictly, since
# nothing but their shape says "who"/"who2" are names here. Only the literal trigger words
# are case-insensitive (wrapped in (?i:...)); _NAME_PHRASE itself stays case-sensitive.
_PHOTO_COURTESY_RE = re.compile(
    rf"(?P<who>{_NAME_PHRASE})\s+(?i:photo)\s*[-,]?\s*(?i:courtesy)\s+(?i:of\s+)?(?P<who2>{_NAME_PHRASE})")
_COLLECTION_COURTESY_RE = re.compile(
    rf"(?P<who>{_NAME_PHRASE})\s+(?i:collection)\s*[-,]?\s*(?i:courtesy)\s+(?i:of\s+)?(?P<who2>{_NAME_PHRASE})")

# Single-name, no-trigger-word patterns: "<who> photo" / "<who> collection". Riskiest (no
# keyword, just shape), so `who` is validated strictly.
_PHOTO_RE = re.compile(rf"(?P<who>{_NAME_PHRASE})\s+(?i:photos?)")
_COLLECTION_RE = re.compile(rf"(?P<who>{_NAME_PHRASE})\s+(?i:collection)")


def _parse_fragment(text: str) -> str | None:
    """Tries `text` (the whole caption, or a parenthetical's contents) as a self-contained
    credit phrase, with an optional leading date ("2009 Rod Bacon photo"). Returns the
    formatted credit, or None if nothing here is unambiguous enough to extract."""
    text = text.strip()
    m = _LEADING_DATE_RE.match(text)
    body = text[m.end():].strip() if m else text
    if not body:
        return None

    fm = _PHOTO_COURTESY_RE.fullmatch(body)
    if fm and _looks_like_credit(fm["who"], level="strict") and _looks_like_credit(fm["who2"], level="strict"):
        return f"{fm['who'].rstrip(',')} (courtesy {fm['who2'].rstrip(',')})"

    fm = _COLLECTION_COURTESY_RE.fullmatch(body)
    if fm and _looks_like_credit(fm["who"], level="strict") and _looks_like_credit(fm["who2"], level="strict"):
        return f"{fm['who'].rstrip(',')} collection (courtesy {fm['who2'].rstrip(',')})"

    for pat, level in _TRIGGER_PATTERNS:
        fm = pat.fullmatch(body)
        if not fm:
            continue
        who = _strip_trailing_year(fm["who"])
        if _looks_like_credit(who, level=level):
            return who.rstrip(",")

    fm = _COLLECTION_RE.fullmatch(body)
    if fm and _looks_like_credit(fm["who"], level="strict"):
        return f"{fm['who'].rstrip(',')} collection"

    fm = _PHOTO_RE.fullmatch(body)
    if fm and _looks_like_credit(fm["who"], level="strict"):
        return fm["who"].rstrip(",")

    return None


def extract_photo_credit(caption: str | None) -> tuple[str | None, str | None]:
    """(new_caption, credit) -- `credit` is None (and the caption untouched) when nothing
    unambiguous was found."""
    if not caption:
        return caption, None
    text = caption.strip()

    # A trailing parenthetical: "<rest> (<credit phrase>)". Tried before the whole-string
    # form so "Historical Marker (Andrew Zerbe photo)" extracts from inside the parens rather
    # than failing to match (or worse, mismatching) against the whole string. The balance
    # check lets an earlier, unrelated parenthetical stay put: "Vintage (c 1920) Photo (Bob
    # Eckler Collection-courtesy Bill Starr)" extracts only the trailing group.
    m = re.fullmatch(r"(?P<rest>.*?)\s*\((?P<inner>[^()]+)\)", text, re.S)
    if m and m.group("rest").count("(") == m.group("rest").count(")"):
        credit = _parse_fragment(m.group("inner"))
        if credit:
            rest = m.group("rest").strip(" -,")
            return (None if _is_date_only(rest) else (rest or None)), credit

    # The whole caption (after an optional leading date) is itself the credit phrase.
    credit = _parse_fragment(text)
    if credit:
        return None, credit

    # No parens, but prose leads into a trigger-word phrase that runs to the end: "Hadley
    # Mtn. Observatory Sept. 2003-courtesy Bill Starr". Deliberately excludes the no-trigger
    # "X photo"/"X collection" shapes here -- without parens or an explicit trigger word,
    # clipping a trailing "<capitalised word> photo" off of real prose is too easy to get
    # wrong, so that combination is left alone.
    m = re.search(
        r"[-,:]\s*(?P<phrase>photos?\s+courtesy\s+(?:of\s+)?.+|courtesy\s+(?:of\s+)?.+|"
        r"photos?\s+by\s+.+|photos?\s*:\s*.+)$",
        text, re.I,
    )
    if m:
        credit = _parse_fragment(m.group("phrase"))
        if credit:
            rest = text[: m.start()].strip(" -,:")
            return (None if _is_date_only(rest) else (rest or None)), credit

    return caption, None
