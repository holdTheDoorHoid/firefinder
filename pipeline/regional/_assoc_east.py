"""Helpers for the eastern association-project modules, on top of the shared driver ``_assoc_site``.

The driver (``_assoc_site.run``) fetches and caches the cited reports, builds the records, checks every
cited fact against the report's text and writes the extract; a module is its data plus a call to it.
The one thing the eastern modules add is ``doc()`` that works out whether a URL is a PDF or a page, so
a list of a hundred newsletter links needs no ``kind=`` on each line.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _assoc_site import E, doc as _doc, run  # noqa: E402,F401

__all__ = ["E", "doc", "run"]


def doc(doc_id: str, url: str, label: str, year: int | None = None, *, kind: str | None = None,
        cache: str | None = None, page: str | None = None) -> dict:
    """``_assoc_site.doc`` with ``kind`` taken from the URL ("pdf" when it ends in .pdf, else "html")."""
    kind = kind or ("pdf" if url.lower().split("?")[0].endswith(".pdf") else "html")
    return _doc(doc_id, url, label, year, kind=kind, cache=cache, page=page)
