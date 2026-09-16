"""Stage 1-4 orchestration: email fetch -> classify -> parse digest -> dedup -> relevance
screen -> preliminary fit score. Stage 5 (full eligibility) is services.tender_service,
shared with the manual paste/PDF route - it is human-triggered there, and used here only
as the fallback for a tender-classified email whose digest parsing found zero listings.

This module owns the DB writes for the automated pipeline; app.services.ai and
app.services.email_intake stay DB-free so they stay portable. Callers (a request
handler, or the APScheduler job) are responsible for supplying a Session and
committing/closing it.
"""
import logging
import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import APP_TZ, FETCH_MAX_RESULTS, FETCH_SINCE_DAYS
from app.models import EmailSettings, ProcessedEmail, Tender
from app.services import email_intake
from app.services import digest_parse
from app.services import ai
from app.services import tender_service
from app.services.company_profile import profile_to_dict, build_relevance_summary
from app.services.credentials import get_app_password
from app.services.usage import log_usage

logger = logging.getLogger("tender_agent")


def run_pipeline_check(db: Session) -> dict:
    """Runs one full Stage 1-4 pass. Returns a summary dict (see keys below), or
    {"error": "..."} if email settings aren't usable.

    Every exit path below sets last_checked_at (last ATTEMPT) plus last_status/
    last_error, and commits - including the early-return error paths. Without that,
    a failed run leaves no trace at all and the settings page keeps showing whatever
    timestamp/summary is left over from the last time it happened to work."""
    settings = db.query(EmailSettings).first()
    if not settings:
        # Nothing to persist to - get_or_create_email_settings() is expected to have
        # run before this in every real caller, so this should not normally happen.
        error = ("Email settings are not configured yet. Go to Email settings and "
                  "enter your email address and App Password.")
        logger.error(error)
        return {"error": error}

    app_password = get_app_password(settings)
    if not settings.imap_email or not app_password:
        error = ("Email settings are not configured yet. Go to Email settings and enter "
                  "your email address, and set IMAP_APP_PASSWORD in the environment "
                  "(see docs/SECURITY.md).")
        _record_failure(db, settings, error)
        return {"error": error}

    already_processed_ids = {row.message_id for row in db.query(ProcessedEmail.message_id).all()}
    denylist = _split_list(settings.sender_denylist)
    keyword_hints = settings.sender_filter

    try:
        emails = email_intake.fetch_recent_emails(
            settings.imap_email, app_password, already_processed_ids,
            denylist=denylist, max_results=FETCH_MAX_RESULTS, since_days=FETCH_SINCE_DAYS,
        )
    except Exception as e:
        # email_intake already produces a fully-formed, host-aware message (including
        # the Zoho AUTHENTICATIONFAILED diagnostic when applicable) - don't re-wrap it.
        error = str(e)
        _record_failure(db, settings, error)
        return {"error": error}

    company_profile = profile_to_dict(db)

    counters = {
        "emails_scanned": 0, "tender_digests": 0, "listings_parsed": 0,
        "relevant": 0, "new_tenders": 0, "already_seen": 0,
        "fallback_used": 0, "errors": 0, "listing_errors": 0, "new_tender_ids": [],
    }

    for msg in emails:
        counters["emails_scanned"] += 1
        try:
            _process_email(db, msg, keyword_hints, company_profile, counters)
        except Exception as e:
            logger.error("failed processing message_id=%s: %s", msg.get("message_id"), e, exc_info=True)
            counters["errors"] += 1

    counters["expired"] = _expire_overdue_tenders(db)

    now = datetime.now(timezone.utc)
    settings.last_checked_at = now
    settings.last_status = "ok"
    settings.last_error = None
    settings.last_success_at = now
    settings.last_summary = summary_message(counters)
    db.commit()
    logger.info(summary_message(counters))
    return counters


def _expire_overdue_tenders(db: Session) -> int:
    """Auto-archive: any tender whose deadline has passed and whose status is still
    "new" or "filtered_out" becomes "expired", so a dashboard running at ~1,000
    listings/month doesn't fill up with tenders nobody can act on anymore. Deliberately
    does NOT touch "tbd", "selected", "applied", or "rejected" - those are human
    decisions and must be preserved as a record even after the deadline passes. Runs at
    the end of every
    pipeline run (scheduled or "Check now"), not just when new mail arrived - a run that
    found nothing new should still catch yesterday's deadlines. Returns the count
    archived, for the run's summary."""
    today_local = datetime.now(APP_TZ).date()
    overdue = db.query(Tender).filter(
        Tender.deadline_date < today_local,
        Tender.status.in_(("new", "filtered_out")),
    ).all()
    for t in overdue:
        t.status = "expired"
    return len(overdue)


def _record_failure(db: Session, settings: EmailSettings, error: str):
    logger.error(error)
    settings.last_checked_at = datetime.now(timezone.utc)
    settings.last_status = "error"
    settings.last_error = error
    db.commit()


def _process_email(db: Session, msg: dict, keyword_hints: str, company_profile: dict, counters: dict):
    snippet = email_intake.plain_snippet(msg["body_text"], msg["body_html"])
    is_tender, usage = ai.is_tender_email(msg["subject"], snippet, keyword_hints)
    log_usage(db, "classify", usage, tender_id=None)

    if not is_tender:
        db.add(ProcessedEmail(message_id=msg["message_id"], was_tender=is_tender, listings_found=0))
        return

    counters["tender_digests"] += 1

    listings = digest_parse.parse_bdtender_digest(msg["body_html"]) if msg["body_html"] else []

    if not listings:
        logger.warning(
            "zero listings parsed from a tender-classified email (message_id=%s); the "
            "digest format may have changed - falling back to AI extraction",
            msg["message_id"],
        )
        counters["fallback_used"] += 1
        _process_fallback(db, msg, counters)
        db.add(ProcessedEmail(message_id=msg["message_id"], was_tender=is_tender, listings_found=0))
        return

    # Each listing gets its own try/except so one bad listing can't cost the other 23 -
    # but if ANY listing in this email failed, the ProcessedEmail row below is skipped
    # entirely, not just for the failed one. That's deliberate: Tender.tender_ref
    # dedup (see _process_listing's already_seen check) makes re-running this email
    # on the next check cheap - already-saved listings are skipped instantly - so
    # leaving the email unmarked buys a free retry of just the listing(s) that failed,
    # rather than losing them with no record.
    email_had_listing_error = False
    for listing in listings:
        counters["listings_parsed"] += 1
        try:
            _process_listing(db, listing, msg, company_profile, counters)
        except Exception as e:
            logger.error(
                "failed processing listing tender_ref=%s (message_id=%s): %s",
                listing.get("tender_ref"), msg["message_id"], e, exc_info=True,
            )
            counters["listing_errors"] += 1
            email_had_listing_error = True

    if not email_had_listing_error:
        db.add(ProcessedEmail(message_id=msg["message_id"], was_tender=is_tender, listings_found=len(listings)))


def _process_fallback(db: Session, msg: dict, counters: dict):
    fallback_text = (msg["body_text"] or _strip_html(msg["body_html"]) or "").strip()
    if not fallback_text:
        return

    tender_ref = f"email-{msg['message_id']}"
    if db.query(Tender).filter(Tender.tender_ref == tender_ref).first():
        counters["already_seen"] += 1
        return

    tender = tender_service.process_manual_tender(
        db, fallback_text, source="Email (auto, non-digest format)",
        tender_ref=tender_ref, source_email_message_id=msg["message_id"],
    )

    counters["listings_parsed"] += 1
    counters["relevant"] += 1
    counters["new_tenders"] += 1
    counters["new_tender_ids"].append(tender.id)


def _process_listing(db: Session, listing: dict, msg: dict, company_profile: dict, counters: dict):
    existing = db.query(Tender).filter(Tender.tender_ref == listing["tender_ref"]).first()
    if existing:
        counters["already_seen"] += 1
        new_deadline_date = listing["submission_last_date"]
        new_deadline = new_deadline_date.isoformat() if new_deadline_date else None
        if new_deadline and existing.deadline != new_deadline:
            existing.deadline = new_deadline
        if new_deadline_date and existing.deadline_date != new_deadline_date:
            existing.deadline_date = new_deadline_date
        return

    company_summary = build_relevance_summary(company_profile)
    relevant, tender_type, entity, usage1 = ai.is_relevant_listing(
        listing["title"], listing["organization"], listing["district"], company_summary,
    )
    log_usage(db, "relevance", usage1, tender_id=None)

    deadline_date = listing["submission_last_date"]  # already a real date - store it directly, not as a string
    deadline = deadline_date.isoformat() if deadline_date else None
    # The digest's "Document Price" is the fee to buy the tender document (typically a
    # few hundred to a few thousand BDT) - NOT the contract value. It goes in its own
    # field; estimated_value stays None here since the digest genuinely doesn't contain
    # the contract value (only Stage 5, working from the real notice text, does).
    document_price = str(listing["document_price"]) if listing["document_price"] else None

    if not relevant:
        db.add(Tender(
            raw_text=_listing_raw_text(listing),
            source="BDTender email (auto)",
            tender_ref=listing["tender_ref"],
            source_email_message_id=msg["message_id"],
            notice_url=listing["notice_url"],
            organization=listing["organization"],
            district=listing["district"],
            title=listing["title"],
            tender_type=tender_type,
            entity=entity,
            publish_date=listing["issue_date"],
            deadline=deadline,
            deadline_date=deadline_date,
            location=listing["district"],
            document_price=document_price,
            status="filtered_out",
        ))
        return

    counters["relevant"] += 1

    fit, usage2 = ai.score_preliminary_fit(_serialize_listing(listing), company_profile)

    tender = Tender(
        raw_text=_listing_raw_text(listing),
        source="BDTender email (auto)",
        tender_ref=listing["tender_ref"],
        source_email_message_id=msg["message_id"],
        notice_url=listing["notice_url"],
        organization=listing["organization"],
        district=listing["district"],
        title=listing["title"],
        tender_type=tender_type,
        entity=entity,
        publish_date=listing["issue_date"],
        deadline=deadline,
        deadline_date=deadline_date,
        location=listing["district"],
        document_price=document_price,
        hard_filter_pass=None,
        hard_filter_reason="Eligibility not available from digest — open the notice to check.",
        fit_score=fit.get("fit_score"),
        fit_reasons=fit.get("fit_reasons"),
        status="new",
    )
    db.add(tender)
    db.flush()
    log_usage(db, "prelim_fit", usage2, tender_id=tender.id)

    counters["new_tenders"] += 1
    counters["new_tender_ids"].append(tender.id)


def _serialize_listing(listing: dict) -> dict:
    return {
        "tender_ref": listing["tender_ref"],
        "title": listing["title"],
        "organization": listing["organization"],
        "district": listing["district"],
        "issue_date": listing["issue_date"].isoformat() if listing["issue_date"] else None,
        "submission_last_date": listing["submission_last_date"].isoformat() if listing["submission_last_date"] else None,
        "document_price": str(listing["document_price"]) if listing["document_price"] else None,
    }


def _listing_raw_text(listing: dict) -> str:
    return "\n".join([
        f"Tender Ref: {listing['tender_ref']}",
        f"Title: {listing['title']}",
        f"Organization: {listing['organization'] or ''}",
        f"District: {listing['district'] or ''}",
        f"Issue Date: {listing['issue_date'].isoformat() if listing['issue_date'] else ''}",
        f"Document Price: {listing['document_price'] if listing['document_price'] else ''}",
        f"Doc Purchase Last Date: {listing['doc_purchase_last_date'].isoformat() if listing['doc_purchase_last_date'] else ''}",
        f"Submission Last Date: {listing['submission_last_date'].isoformat() if listing['submission_last_date'] else ''}",
        f"Notice URL: {listing['notice_url'] or ''}",
    ])


def _strip_html(html):
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _split_list(value: str):
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def summary_message(counters: dict) -> str:
    if "error" in counters:
        return counters["error"]
    return (
        f"Scanned {counters['emails_scanned']} emails, {counters['tender_digests']} were "
        f"tender digests, {counters['listings_parsed']} listings parsed, "
        f"{counters['relevant']} relevant, {counters['new_tenders']} new, "
        f"{counters['already_seen']} already seen."
        + (f" ({counters['fallback_used']} used AI-extraction fallback.)" if counters.get("fallback_used") else "")
        + (f" {counters['errors']} email(s) failed to process - see server logs." if counters.get("errors") else "")
        + (f" {counters['listing_errors']} listing(s) failed to process - see server logs." if counters.get("listing_errors") else "")
        + (f" {counters['expired']} tender(s) auto-archived as expired." if counters.get("expired") else "")
    )
