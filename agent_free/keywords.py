"""
The keyword list, and the matching that replaces the AI relevance check.

This is the heart of the no-API agent. Where the AI version asks Claude
"is this tender relevant to Bhumijo?", this asks "does its title, organisation
or scope contain any of these words?" — which is cruder, but free, instant,
and completely explainable: every decision comes with the exact words that
caused it.

The list lives in a JSON file under data/, not in this code, so it can be
edited from the settings page without anyone touching Python.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from backend.config import get_logger, settings

log = get_logger("agent_free.keywords")

KEYWORDS_FILE = settings.data_dir / "agent_free_keywords.json"


# --- the starting list -------------------------------------------------
# Drawn from Bhumijo's company profile: WASH/sanitation infrastructure and
# urban planning & design consultancy.

DEFAULT_ENGLISH = [
    # sanitation — the core business
    "toilet", "washroom", "latrine", "sanitation", "sanitary", "wash",
    "sewerage", "sewage", "septic", "drainage", "drain", "water supply",
    "hygiene", "public convenience", "waste management",
    # planning and design consultancy
    "urban planning", "urban design", "town planning", "master plan",
    "architecture", "architectural", "landscape", "public space",
    "park", "feasibility study", "design consultancy", "detailed design",
    "supervision consultancy",
    # facility management — the second business line. Absent from the original
    # list, which meant cleaning and manpower tenders were never surfaced at
    # all, despite FM being a third of the proposals in the tracker.
    "cleaning", "janitorial", "housekeeping", "manpower", "outsourcing",
    "facility management", "support staff", "caretaking", "maintenance service",
    "deep cleaning", "glass cleaning", "pest control",
    # technology
    "cctv", "monitoring system", "automation", "software",
]

# Bengali terms for the same things. BDTender notices are often in Bengali or
# mixed, and an English-only list would silently miss them.
#
# NOTE: these were drafted rather than taken from real notices — worth
# checking against a few of your actual alerts and correcting on the settings
# page. A wrong term here means missed tenders, and nothing will warn you.
DEFAULT_BENGALI = [
    "টয়লেট",          # toilet
    "শৌচাগার",         # latrine / toilet
    "পয়ঃনিষ্কাশন",     # sewerage
    "স্যানিটেশন",      # sanitation
    "পানি সরবরাহ",     # water supply
    "নর্দমা",          # drain
    "ড্রেনেজ",         # drainage
    "বর্জ্য",           # waste
    "পরিচ্ছন্নতা",      # cleanliness / hygiene
    "নগর পরিকল্পনা",   # urban planning
    "স্থাপত্য",         # architecture
    "নকশা",           # design
    "পার্ক",           # park
    "জনবল",           # manpower
    "আউটসোর্সিং",      # outsourcing
    "পরিচ্ছন্নতা কর্মী",  # cleaning staff
]

# Words that mean "definitely not us" even if a keyword matched. Without
# these, "supply of drinking water bottles" matches "water supply".
# "security guard" was removed from this list on 9 Sep 2026: Bhumijo supplies
# security manpower as an FM service and has a signed contract for exactly that
# (B+plus Limited, "Facility Management Manpower (Security) Services"), so
# excluding it threw away winnable work. "catering" is kept, but note the
# related canteen/tea-server manpower jobs are caught by "support staff".
DEFAULT_EXCLUDE = [
    "bottle", "furniture supply", "stationery", "vehicle purchase",
    "computer supply", "printing", "catering",
    "insurance", "audit firm",
]


@dataclass
class KeywordSet:
    english: list[str] = field(default_factory=lambda: list(DEFAULT_ENGLISH))
    bengali: list[str] = field(default_factory=lambda: list(DEFAULT_BENGALI))
    exclude: list[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDE))

    def to_dict(self) -> dict:
        return {"english": self.english, "bengali": self.bengali,
                "exclude": self.exclude}


def load() -> KeywordSet:
    """The current list, creating the file with sensible defaults if missing."""
    if not KEYWORDS_FILE.exists():
        save(KeywordSet())
        log.info("created the default keyword list at %s", KEYWORDS_FILE.name)

    try:
        data = json.loads(KEYWORDS_FILE.read_text(encoding="utf-8"))
        return KeywordSet(
            english=[t for t in data.get("english", []) if t.strip()],
            bengali=[t for t in data.get("bengali", []) if t.strip()],
            exclude=[t for t in data.get("exclude", []) if t.strip()],
        )
    except (OSError, json.JSONDecodeError) as exc:
        # A broken file must not stop the agent finding tenders.
        log.error("could not read %s (%s) — using the defaults",
                  KEYWORDS_FILE.name, exc)
        return KeywordSet()


def save(keywords: KeywordSet) -> None:
    KEYWORDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    KEYWORDS_FILE.write_text(
        json.dumps(keywords.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# --- matching ----------------------------------------------------------

def _matches_english(term: str, haystack: str) -> bool:
    """
    Whole words only, so "park" does not match "parking" and "wash" does not
    match "washing machine". Multi-word terms are matched as a phrase.
    """
    pattern = r"\b" + r"\s+".join(re.escape(w) for w in term.split()) + r"\b"
    return re.search(pattern, haystack, re.IGNORECASE) is not None


def _matches_bengali(term: str, haystack: str) -> bool:
    """
    Plain substring for Bengali.

    Bengali script has no word boundaries that \\b understands — using \\b
    here would match nothing at all, silently. Substring is the honest
    approach for this script.
    """
    return term in haystack


# --- which business a matched term belongs to --------------------------
# The AI path asks Claude which of Bhumijo's four entities a tender is (see
# services.ai._ENTITIES). Without an API key we infer it from the keywords
# that actually matched, which is cruder but free and completely explainable.
#
# A term missing from this map contributes nothing to the decision rather than
# breaking it - the keyword list is user-editable from the settings page, so
# new terms appear here all the time and must not crash the classifier.

ENTITY_BY_TERM = {
    # WASH / toilets
    "toilet": "WASH", "washroom": "WASH", "latrine": "WASH",
    "sanitation": "WASH", "sanitary": "WASH", "wash": "WASH",
    "sewerage": "WASH", "sewage": "WASH", "septic": "WASH",
    "drainage": "WASH", "drain": "WASH", "water supply": "WASH",
    "hygiene": "WASH", "public convenience": "WASH",
    "waste management": "WASH",
    "টয়লেট": "WASH", "শৌচাগার": "WASH", "পয়ঃনিষ্কাশন": "WASH",
    "স্যানিটেশন": "WASH", "পানি সরবরাহ": "WASH", "নর্দমা": "WASH",
    "ড্রেনেজ": "WASH", "বর্জ্য": "WASH",
    # Planning & Design
    "urban planning": "P&D", "urban design": "P&D", "town planning": "P&D",
    "master plan": "P&D", "architecture": "P&D", "architectural": "P&D",
    "landscape": "P&D", "public space": "P&D", "park": "P&D",
    "feasibility study": "P&D", "design consultancy": "P&D",
    "detailed design": "P&D", "supervision consultancy": "P&D",
    "নগর পরিকল্পনা": "P&D", "স্থাপত্য": "P&D", "নকশা": "P&D", "পার্ক": "P&D",
    # Facility Management
    "cleaning": "FM", "janitorial": "FM", "manpower": "FM",
    "outsourcing": "FM", "facility management": "FM", "housekeeping": "FM",
    "support staff": "FM", "caretaking": "FM", "maintenance service": "FM",
    "deep cleaning": "FM", "glass cleaning": "FM", "pest control": "FM",
    "পরিচ্ছন্নতা": "FM", "জনবল": "FM", "আউটসোর্সিং": "FM",
    "পরিচ্ছন্নতা কর্মী": "FM",
    # Technology
    "software": "Tech", "cctv": "Tech", "monitoring system": "Tech",
    "automation": "Tech",
}

# Ties broken in this order. WASH first because it is the core business: a
# "public toilet in a park" tender is a WASH job that happens to be in a park,
# not a landscaping job.
_ENTITY_PRIORITY = ("WASH", "P&D", "FM", "Tech")


def entity_for(matched: list[str]) -> str:
    """Which business do these matched keywords point at? "Other" if none map."""
    counts: dict[str, int] = {}
    for term in matched:
        ent = ENTITY_BY_TERM.get(term.lower().strip())
        if ent:
            counts[ent] = counts.get(ent, 0) + 1
    if not counts:
        return "Other"
    best = max(counts.values())
    for ent in _ENTITY_PRIORITY:
        if counts.get(ent) == best:
            return ent
    return "Other"


@dataclass
class MatchResult:
    relevant: bool
    matched: list[str]
    excluded_by: str | None
    reason: str
    # Which of Bhumijo's four businesses this looks like - the no-API
    # equivalent of what services.ai.is_relevant_listing asks Claude for.
    entity: str = "Other"

    @property
    def score(self) -> int:
        """
        A rough 0-100 stand-in for the AI's fit score, from how many distinct
        keywords hit. It is a count, not a judgement — the dashboard labels it
        "keyword matches" rather than "fit", so nobody mistakes it for one.
        """
        if not self.relevant:
            return 0
        return min(100, 40 + 15 * len(self.matched))


def check(text: str, keywords: KeywordSet | None = None) -> MatchResult:
    """Is this tender worth a look? Returns the decision and why."""
    keywords = keywords or load()
    haystack = (text or "").strip()

    if not haystack:
        return MatchResult(False, [], None, "no text to check")

    # Exclusions win over matches: a stationery tender that happens to say
    # "office washroom" is still a stationery tender.
    for term in keywords.exclude:
        if _matches_english(term, haystack):
            return MatchResult(
                False, [], term,
                f"excluded — contains {term!r}",
            )

    matched: list[str] = []
    for term in keywords.english:
        if _matches_english(term, haystack):
            matched.append(term)
    for term in keywords.bengali:
        if _matches_bengali(term, haystack):
            matched.append(term)

    if not matched:
        return MatchResult(False, [], None, "no keyword matched")

    shown = ", ".join(matched[:6])
    if len(matched) > 6:
        shown += f" (+{len(matched) - 6} more)"
    return MatchResult(True, matched, None, f"matched: {shown}",
                       entity=entity_for(matched))
