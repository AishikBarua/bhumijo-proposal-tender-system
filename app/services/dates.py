"""Shared date-parsing helper. DD/MM/YYYY is the format Bangladeshi tender notices and
BDTender digests consistently use - see app.services.digest_parse (structured digest
fields) and app.services.tender_service (the AI-extracted free-text deadline string on
the manual paste/PDF path), both of which parse dates through here so there is exactly
one definition of "what counts as a valid date" in this app.
"""
import re
from datetime import date

_DATE_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


def parse_ddmmyyyy(value: str) -> date:
    """Finds a DD/MM/YYYY-shaped date anywhere in value and returns it as a date.
    Returns None if not found or not a valid calendar date - never raises, and never
    guesses at other formats. Callers should leave the field null on a None return
    rather than attempt further interpretation."""
    if not value:
        return None
    m = _DATE_RE.search(value)
    if not m:
        return None
    day, month, year = (int(x) for x in m.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None
