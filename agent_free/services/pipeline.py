"""
The no-API pipeline: mailbox in, filtered tenders out, nothing paid for.

The AI version calls Claude five times per run. This calls it zero times.
Everything here is either reused rule-based code or plain keyword matching:

    1. fetch the mail                 IMAP          (reused, free)
    2. split the digest into listings BeautifulSoup (reused, free)
    3. decide which ones matter       keywords      (this module, free)
    4. save them                      SQLAlchemy    (shared database)

Deliberately reuses app.services.digest_parse and app.services.email_intake
rather than copying them. They are already rule-based and already tested —
a second copy would just be a second thing to fix.

Tenders it saves are marked source="rules" so they are distinguishable from
AI-found ones in the same dashboard.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import EmailSettings, ProcessedEmail, Tender
from app.services.digest_parse import parse_bdtender_digest
from app.services.credentials import get_app_password
from app.services.email_intake import fetch_recent_emails, plain_snippet
from backend.config import get_logger

from .. import keywords as kw

log = get_logger("agent_free.pipeline")

SOURCE = "rules"


def _counters() -> dict:
    return {"emails": 0, "listings": 0, "matched": 0,
            "skipped": 0, "already_seen": 0, "errors": 0}


def summary_message(counters: dict) -> str:
    if counters.get("error"):
        return counters["error"]
    return (f"{counters['emails']} email(s), {counters['listings']} listing(s): "
            f"{counters['matched']} matched your keywords, "
            f"{counters['skipped']} skipped, "
            f"{counters['already_seen']} already known.")


# --- saving one listing ------------------------------------------------

def save_listing(db: Session, listing: dict, match: "kw.MatchResult",
                 *, message_id: str | None = None) -> Tender | None:
    """
    Store one matched listing.

    Every field here comes from the rule-based parser — no AI produced any of
    it. The fields the AI would have filled (eligibility, scope summary,
    required documents) are deliberately left empty rather than guessed at.
    """
    ref = listing.get("tender_ref")
    if ref:
        existing = db.query(Tender).filter(Tender.tender_ref == ref).first()
        if existing:
            # Deadlines get revised; keep the newest without duplicating.
            new_date = listing.get("submission_last_date")
            if new_date and existing.deadline_date != new_date:
                existing.deadline_date = new_date
                existing.deadline = new_date.isoformat()
            return None

    deadline_date = listing.get("submission_last_date")

    tender = Tender(
        source=SOURCE,
        tender_ref=ref,
        source_email_message_id=message_id,
        notice_url=listing.get("notice_url"),
        organization=listing.get("organization"),
        district=listing.get("district"),
        title=listing.get("title"),
        # Rule-based, from the keywords that matched - see keywords.entity_for.
        entity=match.entity,
        location=listing.get("district"),
        deadline=deadline_date.isoformat() if deadline_date else None,
        deadline_date=deadline_date,
        document_price=(str(listing["document_price"])
                        if listing.get("document_price") else None),
        publish_date=listing.get("issue_date"),
        raw_text=listing.get("raw_text") or listing.get("title") or "",
        status="new",

        # Where the AI would have judged, this records what actually happened.
        # hard_filter_pass stays None — "needs review" — because keywords
        # cannot check eligibility and pretending otherwise would be worse
        # than admitting it.
        hard_filter_pass=None,
        hard_filter_reason=("Not checked — this tender was found by keyword "
                            "matching, which cannot read eligibility rules. "
                            "Open the notice to confirm you qualify."),
        fit_score=match.score,
        fit_reasons=f"Keyword match ({match.reason}). No AI evaluation.",
        processed_at=datetime.now(),
    )
    db.add(tender)
    return tender


# --- processing one email ----------------------------------------------

def process_email(db: Session, msg: dict, counters: dict) -> None:
    listings = []
    try:
        if msg.get("html_body"):
            listings = parse_bdtender_digest(msg["html_body"])
    except Exception as exc:  # noqa: BLE001 — one bad email must not stop the run
        log.warning("could not parse digest %r: %s", msg.get("subject", "")[:60], exc)
        counters["errors"] += 1

    if not listings:
        # Not a digest we recognise. The AI version would ask Claude to read
        # it; without that we can only check the subject line and say so.
        text = f"{msg.get('subject','')}\n{plain_snippet(msg.get('text_body'), msg.get('html_body'))}"
        match = kw.check(text)
        if match.relevant:
            log.info("non-digest email matched keywords: %r — needs a human",
                     msg.get("subject", "")[:60])
            counters["matched"] += 1
            save_listing(db, {
                "title": msg.get("subject", "(no subject)"),
                "raw_text": text,
                "tender_ref": None,
            }, match, message_id=msg.get("message_id"))
        else:
            counters["skipped"] += 1
        return

    for listing in listings:
        counters["listings"] += 1
        haystack = " ".join(str(listing.get(f) or "") for f in
                            ("title", "organization", "district"))
        match = kw.check(haystack)

        if not match.relevant:
            counters["skipped"] += 1
            continue

        saved = save_listing(db, listing, match, message_id=msg.get("message_id"))
        if saved is None:
            counters["already_seen"] += 1
        else:
            counters["matched"] += 1


# --- the run ------------------------------------------------------------

def run_check(db: Session) -> dict:
    """
    One pass over the mailbox. Called by the scheduler every 15 minutes and
    by the "Check now" button.
    """
    counters = _counters()

    settings_row = db.query(EmailSettings).first()
    # The password lives in the environment (IMAP_APP_PASSWORD), not in the
    # database - see app.services.credentials. Reading the column directly
    # meant this agent always bailed out here on a correctly configured
    # machine, because the env-var path deliberately nulls that column.
    app_password = get_app_password(settings_row)
    if not settings_row or not settings_row.imap_email or not app_password:
        counters["error"] = ("The mailbox is not set up yet. Add the email address "
                             "under Email settings and IMAP_APP_PASSWORD in .env, "
                             "then try again.")
        return counters

    already = {row.message_id for row in db.query(ProcessedEmail).all()}

    try:
        messages = fetch_recent_emails(
            settings_row.imap_email, app_password, already
        )
    except Exception as exc:  # noqa: BLE001 — the message is what the user needs
        counters["error"] = f"Could not read the mailbox: {exc}"
        settings_row.last_status = "error"
        settings_row.last_error = str(exc)[:500]
        settings_row.last_checked_at = datetime.now()
        db.commit()
        return counters

    for msg in messages:
        counters["emails"] += 1
        try:
            process_email(db, msg, counters)
            db.add(ProcessedEmail(message_id=msg["message_id"]))
        except Exception as exc:  # noqa: BLE001
            log.exception("failed on one email")
            counters["errors"] += 1

    settings_row.last_checked_at = datetime.now()
    settings_row.last_status = "ok"
    settings_row.last_error = None
    settings_row.last_success_at = datetime.now()
    settings_row.last_summary = summary_message(counters)
    db.commit()

    log.info("no-API check: %s", summary_message(counters))
    return counters


def process_pasted_digest(db: Session, html_or_text: str) -> dict:
    """
    Run a pasted digest through the same code path, for testing before the
    mailbox is configured. Same parsing, same keywords, same saving.
    """
    counters = _counters()
    counters["emails"] = 1
    process_email(db, {"subject": "(pasted by hand)",
                       "html_body": html_or_text,
                       "text_body": html_or_text,
                       "message_id": None}, counters)
    db.commit()
    return counters
