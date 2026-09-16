"""Stage 5: full extraction + eligibility evaluation on a complete tender notice's text.

Shared by two callers that used to duplicate this sequence independently: the manual
paste/PDF route (routes/tenders.py) and the automated pipeline's non-digest fallback
(services/pipeline.py, used when an email is classified as a tender but digest parsing
finds zero listings - some other aggregator/sender format).
"""
from sqlalchemy.orm import Session

from app.models import Tender
from app.services import ai
from app.services.company_profile import profile_to_dict
from app.services.dates import parse_ddmmyyyy
from app.services.pdf_extract import extract_text_from_pdf
from app.services.usage import log_usage


def process_manual_tender(db: Session, raw_text: str, source: str, *, pdf_bytes: bytes = None,
                           tender_ref: str = None, source_email_message_id: str = None) -> Tender:
    """Extracts structured fields and an eligibility/fit evaluation from raw_text, saves
    a Tender, and logs both AI calls' usage. Returns None if there is no text to process
    (caller decides how to report that - e.g. "paste text or upload a PDF").

    If pdf_bytes is given, it is extracted (this is the one place extract_text_from_pdf
    is called from) and appended to raw_text before processing - the manual route hands
    over the raw uploaded file's bytes rather than doing extraction itself.

    tender_ref/source_email_message_id are only meaningful for the pipeline fallback
    caller, which needs them for its tender_ref-based dedup; the manual route never
    passes them and both stay None, matching a normal manually-added tender.

    Raises whatever the underlying AI calls raise (e.g. on a malformed/unavailable
    response) - callers are responsible for catching and reporting that.

    Does not commit - callers commit once they're ready to (this function only flushes,
    so the caller can decide the surrounding transaction's boundaries; the automated
    pipeline in particular batches many tenders into one commit per run)."""
    raw_text = raw_text.strip()
    if pdf_bytes:
        raw_text = (raw_text + "\n\n" + extract_text_from_pdf(pdf_bytes)).strip()
    if not raw_text:
        return None

    extracted, usage1 = ai.extract_tender_fields(raw_text)
    company_profile = profile_to_dict(db)
    evaluation, usage2 = ai.evaluate_tender(extracted, company_profile)

    # The AI extracts the deadline as free text in whatever format the notice used -
    # not always a clean date. Try DD/MM/YYYY (what Bangladeshi notices use); leave
    # deadline_date null on anything else rather than guess. The raw string is always
    # kept in `deadline` regardless, so nothing is lost even when this doesn't parse.
    deadline_text = extracted.get("deadline")
    deadline_date = parse_ddmmyyyy(deadline_text)

    tender = Tender(
        raw_text=raw_text[: ai.RAW_TEXT_CAP],
        source=source,
        tender_ref=tender_ref,
        source_email_message_id=source_email_message_id,
        title=extracted.get("title"),
        deadline=deadline_text,
        deadline_date=deadline_date,
        location=extracted.get("location"),
        estimated_value=extracted.get("estimated_value"),
        scope_summary=extracted.get("scope_summary"),
        eligibility_requirements=extracted.get("eligibility_requirements"),
        required_documents=extracted.get("required_documents"),
        instructions=extracted.get("instructions"),
        financial_requirement=extracted.get("financial_requirement"),
        tender_type=extracted.get("tender_type") or "Other",
        hard_filter_pass=evaluation.get("hard_filter_pass"),
        hard_filter_reason=evaluation.get("hard_filter_reason"),
        fit_score=evaluation.get("fit_score"),
        fit_reasons=evaluation.get("fit_reasons"),
        status="new",
    )
    db.add(tender)
    db.flush()

    log_usage(db, "extract", usage1, tender.id)
    log_usage(db, "evaluate", usage2, tender.id)

    return tender
