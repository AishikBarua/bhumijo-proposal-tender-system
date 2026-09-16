"""Parses BDTender digest emails into individual listing records.

BDTender digests are structured, labelled text (rendered from HTML) - each
listing is anchored by a "#N  <tender_ref>" marker followed by a title and a
fixed set of labelled fields. This is parsed in code, not via an AI call:
the format is consistent and free to parse, and it appears ~1,000 times a
month, so an AI call per listing here would dominate the monthly API cost
for no accuracy benefit.
"""
import re
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup

from app.services.dates import parse_ddmmyyyy

_ANCHOR_RE = re.compile(r"#(\d+)\s+(\d{4,})")
_NOTICE_LINK_RE = re.compile(r"\x00NOTICE_LINK_(\d+)\x00")

_LABELS = [
    ("issue_date", "Issue Date:"),
    ("organization", "Organization:"),
    ("district", "District:"),
    ("document_price", "Document Price:"),
    ("doc_purchase_last_date", "Doc Purchase Last Date:"),
    ("submission_last_date", "Submission Last Date:"),
]

# Stop at the next known label, the next listing anchor, or end of block.
# re.S is required: get_text("\n") puts a newline between a bold label and its
# value, so the value often starts on the line after the label.
_VALUE_STOP = (
    r"(?=Issue Date:|Organization:|District:|Document Price:"
    r"|Doc Purchase Last Date:|Submission Last Date:"
    r"|\x00NOTICE_LINK_|#\d+\s+\d{4,}|\Z)"
)

_FIELD_PATTERNS = {
    key: re.compile(re.escape(label) + r"\s*(.*?)" + _VALUE_STOP, re.S)
    for key, label in _LABELS
}

_STOP_RE = re.compile(
    r"(Issue Date:|Organization:|District:|Document Price:"
    r"|Doc Purchase Last Date:|Submission Last Date:|\x00NOTICE_LINK_)"
)


def parse_bdtender_digest(html_body: str) -> list:
    """Split a BDTender digest email into individual listing records.

    Each dict contains: tender_ref, title, issue_date, organization, district,
    document_price, doc_purchase_last_date, submission_last_date, notice_url.
    Blank/unparseable fields are None. Returns [] if no listings are found -
    callers should treat that as a signal the format may have changed and
    fall back to AI extraction, not as a hard failure.
    """
    if not html_body or not html_body.strip():
        return []

    soup = BeautifulSoup(html_body, "html.parser")

    # Replace "View Notice" links with a positional marker before flattening
    # to text, so hrefs can be recovered after get_text() drops all markup.
    link_hrefs = []
    for a in soup.find_all("a"):
        href = a.get("href")
        text = a.get_text(" ", strip=True)
        if href and re.search(r"view\s*notice", text, re.IGNORECASE):
            link_hrefs.append(href)
            a.string = f"\x00NOTICE_LINK_{len(link_hrefs) - 1}\x00"

    full_text = soup.get_text("\n")
    full_text = "\n".join(line.strip() for line in full_text.splitlines())

    matches = list(_ANCHOR_RE.finditer(full_text))
    if not matches:
        return []

    listings = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        block = full_text[start:end]
        listing = _parse_block(block, m.group(2), link_hrefs)
        if listing:
            listings.append(listing)

    return listings


def _parse_block(block: str, tender_ref: str, link_hrefs: list) -> dict:
    after_ref = block.split(tender_ref, 1)[1] if tender_ref in block else block
    stop_m = _STOP_RE.search(after_ref)
    title_raw = after_ref[: stop_m.start()] if stop_m else after_ref
    title = _clean_title(title_raw)

    if not title:
        return None

    fields = {}
    for key, pattern in _FIELD_PATTERNS.items():
        m = pattern.search(block)
        value = " ".join(m.group(1).split()) if m else ""
        fields[key] = value or None

    notice_url = None
    nm = _NOTICE_LINK_RE.search(block)
    if nm:
        idx = int(nm.group(1))
        if idx < len(link_hrefs):
            notice_url = link_hrefs[idx]

    return {
        "tender_ref": tender_ref,
        "title": title,
        "issue_date": parse_ddmmyyyy(fields["issue_date"]),
        "organization": fields["organization"],
        "district": fields["district"],
        "document_price": _parse_decimal(fields["document_price"]),
        "doc_purchase_last_date": parse_ddmmyyyy(fields["doc_purchase_last_date"]),
        "submission_last_date": parse_ddmmyyyy(fields["submission_last_date"]),
        "notice_url": notice_url,
    }


def _clean_title(raw: str) -> str:
    lines = [ln.strip(" .\t") for ln in raw.splitlines()]
    lines = [ln for ln in lines if ln]
    return " ".join(lines).strip()


def _parse_decimal(value):
    if not value:
        return None
    cleaned = re.sub(r"[^\d.]", "", value)
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None
