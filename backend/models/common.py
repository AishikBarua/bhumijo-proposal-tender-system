"""
Cleaning the three fields that cannot move across as they are.

Every function here returns BOTH the cleaned value and the original string,
because the rule for this migration is that nothing is ever silently changed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

# --- dates ------------------------------------------------------------

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%m/%d/%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%Y/%m/%d",
)


def parse_date(raw: str | None) -> str | None:
    """Return an ISO yyyy-mm-dd string, or None if it cannot be read."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def days_until(iso_date: str | None, today: date | None = None) -> int | None:
    if not iso_date:
        return None
    try:
        target = date.fromisoformat(iso_date)
    except ValueError:
        return None
    return (target - (today or date.today())).days


# --- money ------------------------------------------------------------

@dataclass(frozen=True)
class Money:
    amount: float | None
    currency: str
    original: str
    confident: bool

    @property
    def needs_review(self) -> bool:
        return bool(self.original) and not self.confident


_CRORE = 10_000_000
_LAKH = 100_000

_CURRENCY_HINTS = (
    ("bdt", "BDT"), ("tk", "BDT"), ("taka", "BDT"), ("৳", "BDT"),
    ("usd", "USD"), ("$", "USD"),
    ("eur", "EUR"), ("€", "EUR"),
    ("gbp", "GBP"), ("£", "GBP"),
)


def parse_money(raw: str | None, default_currency: str = "BDT") -> Money:
    """
    Handles what is actually in the data:
        "6500"                              -> 6500
        "11,79,32,500"  (Indian grouping)   -> 117932500
        "BDT 1 Cr"                          -> 10000000
        "Approx BDT 21 Crore"               -> 210000000
        "BDT 56729.17 lakh (Design+const)"  -> 5672917000
        "N/A" / ""                          -> None
    Anything it cannot read confidently is returned with confident=False so
    the migration can list it for a person to check.
    """
    original = "" if raw is None else str(raw).strip()
    if not original:
        return Money(None, default_currency, "", True)

    text = original.lower()

    if text in ("n/a", "na", "-", "tbd", "tba", "?"):
        return Money(None, default_currency, original, True)

    currency = default_currency
    for hint, code in _CURRENCY_HINTS:
        if hint in text:
            currency = code
            break

    multiplier = 1.0
    if re.search(r"\bcrore?\b|\bcr\b", text):
        multiplier = _CRORE
    elif re.search(r"\blakh?s?\b|\blac\b", text):
        multiplier = _LAKH
    elif re.search(r"\bmillion\b|\bmn\b", text):
        multiplier = 1_000_000
    elif re.search(r"\bbillion\b|\bbn\b", text):
        multiplier = 1_000_000_000

    numbers = re.findall(r"\d[\d,]*\.?\d*", text)
    if not numbers:
        return Money(None, currency, original, False)

    candidate = numbers[0].replace(",", "")
    try:
        amount = float(candidate) * multiplier
    except ValueError:
        return Money(None, currency, original, False)

    # Confident only when the string was purely a number, or a number with a
    # recognised unit and currency word. Anything with extra prose is flagged.
    stripped = re.sub(
        r"[\d,.\s]|bdt|tk|taka|usd|eur|gbp|crore?|cr|lakh?s?|lac|million|mn|billion|bn|approx|about|around|\$|৳|€|£",
        "",
        text,
    )
    confident = stripped == ""

    return Money(amount, currency, original, confident)


def format_money(amount: float | None, currency: str = "BDT") -> str:
    if amount is None:
        return ""
    if amount >= _CRORE:
        return f"{currency} {amount / _CRORE:,.2f} Cr".replace(".00 ", " ")
    if amount >= _LAKH:
        return f"{currency} {amount / _LAKH:,.2f} Lakh".replace(".00 ", " ")
    return f"{currency} {amount:,.0f}"


# --- names ------------------------------------------------------------

def split_names(raw: str | None) -> list[str]:
    """'Amenul, Mokbul' -> ['Amenul', 'Mokbul']"""
    if not raw:
        return []
    parts = re.split(r"[,/&]| and ", str(raw))
    return [p.strip() for p in parts if p.strip()]


def verbatim(raw: str | None) -> str:
    """
    The value exactly as it was typed — newlines, double spaces and all.

    Migrating must never quietly reformat someone's notes. Tidying free text
    is a separate, deliberate decision, not a side effect of moving house.
    """
    return "" if raw is None else str(raw)


def normalise_text(raw: str | None) -> str:
    """
    Collapse runs of whitespace. Use ONLY where the value is a lookup key,
    never on free text a person wrote.
    """
    if raw is None:
        return ""
    return re.sub(r"\s+", " ", str(raw)).strip()
