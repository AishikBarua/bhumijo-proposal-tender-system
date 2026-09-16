from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Date, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone

from app.config import APP_TZ

Base = declarative_base()

# All DateTime columns below store UTC (see docs/MIGRATIONS.md and the timestamp
# columns' comments) - SQLite drops tzinfo on round-trip (confirmed: a tz-aware
# datetime comes back naive), so every value read from one of these columns is UTC
# even though .tzinfo is None. `default=` needs a callable (not a call) so it's
# evaluated per-row at insert time, not once at import time.
def _utcnow():
    return datetime.now(timezone.utc)


class PastContract(Base):
    """A completed project used as evidence of experience for eligibility checks."""
    __tablename__ = "past_contracts"

    id = Column(Integer, primary_key=True)
    client_name = Column(String, nullable=False)
    contract_value_bdt = Column(Float, nullable=True)
    year = Column(Integer, nullable=True)
    scope_of_work = Column(Text, nullable=False)
    location = Column(String, nullable=True)


class Certification(Base):
    """A license, enlistment, or certification the company holds."""
    __tablename__ = "certifications"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)          # e.g. "LGED Enlistment - Class A"
    issuing_body = Column(String, nullable=True)    # e.g. "LGED"
    valid_until = Column(String, nullable=True)     # free text, e.g. "2027" or "No expiry"
    notes = Column(Text, nullable=True)


class CompanyProfile(Base):
    """Free-text company description used as extra context for the AI (sectors, capabilities, etc.)."""
    __tablename__ = "company_profile"

    id = Column(Integer, primary_key=True)
    company_name = Column(String, nullable=False, default="Bhumijo")
    sectors = Column(Text, nullable=True)           # e.g. "WASH/sanitation, urban planning, consultancy"
    capabilities_summary = Column(Text, nullable=True)
    geographic_reach = Column(String, nullable=True)
    updated_at = Column(DateTime, default=_utcnow)


class EmailSettings(Base):
    """IMAP address/filters used for automatic tender email intake. The App Password
    itself is no longer stored here in normal operation - see imap_app_password below
    and docs/SECURITY.md."""
    __tablename__ = "email_settings"

    id = Column(Integer, primary_key=True)
    imap_email = Column(String, nullable=True)

    # DEPRECATED - do not write to this from the UI anymore. The IMAP App Password is
    # now read from the IMAP_APP_PASSWORD environment variable, with GMAIL_APP_PASSWORD
    # (the old name, from when this mailbox was Gmail) accepted as a fallback (see
    # app.credentials.get_app_password and docs/SECURITY.md). This column is cleared
    # automatically at startup once one of those env vars is confirmed set (see
    # app.main's startup migration); it is kept only as a fallback during migration and
    # is not dropped yet to avoid a hard cutover for anyone who hasn't set the env var.
    imap_app_password = Column(String, nullable=True)
    sender_filter = Column(String, default="tender, procurement, RFP, EOI, quotation")
    # ^ optional keyword hint fed to the Stage 1 classifier prompt - NOT a hard IMAP
    # filter. Mail is pulled broadly by recency; sender is never used to exclude a
    # message except via sender_denylist below.
    sender_denylist = Column(String, nullable=True)     # comma-separated sender substrings to always skip
    enabled = Column(Boolean, default=False)
    check_interval_minutes = Column(Integer, default=15)

    # last_checked_at records the last ATTEMPT (success or failure); last_success_at
    # records the last run that actually completed. Without this split, a failed run
    # and a healthy one look identical on the settings page - see docs/AUTOSTART.md.
    last_checked_at = Column(DateTime, nullable=True)
    last_status = Column(String, nullable=True)         # "ok" or "error"
    last_error = Column(Text, nullable=True)             # error message from the last failed run
    last_success_at = Column(DateTime, nullable=True)
    last_summary = Column(Text, nullable=True)           # summary_message() from the last successful run

    notify_email = Column(String, nullable=True)         # defaults to imap_email if blank
    notify_enabled = Column(Boolean, default=True)


class ProcessedEmail(Base):
    """Tracks which emails have already been scanned, to avoid re-classifying/re-parsing
    the same email. Does NOT prevent re-seeing the same tender - the same tender_ref can
    legitimately arrive in a new email every day; see Tender.tender_ref for that dedup."""
    __tablename__ = "processed_emails"

    id = Column(Integer, primary_key=True)
    message_id = Column(String, unique=True, nullable=False)
    was_tender = Column(Boolean, nullable=True)   # Stage 1 result, cached so it's never re-asked
    listings_found = Column(Integer, default=0)
    processed_at = Column(DateTime, default=_utcnow)


class UsageLog(Base):
    """One row per AI call, so the cost estimates in the README can be checked against
    real token counts rather than trusted blindly."""
    __tablename__ = "usage_log"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=_utcnow)
    call_type = Column(String, nullable=False)   # classify / relevance / extract / evaluate
    model = Column(String, nullable=False)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    tender_id = Column(Integer, ForeignKey("tenders.id"), nullable=True)


class Tender(Base):
    """A tender notice/listing that has been ingested and processed.

    Digest-derived rows (source="BDTender email (auto)" etc.) carry tender_ref and the
    digest-listed fields (organization, district, notice_url) but have NO eligibility
    info - that only exists behind the notice link. hard_filter_pass is None for these
    ("needs review") until a human runs the full paste/PDF path (Stage 5) on the actual
    notice. Manually pasted/uploaded tenders go straight through the full path and get a
    real True/False hard_filter_pass."""
    __tablename__ = "tenders"

    id = Column(Integer, primary_key=True)
    raw_text = Column(Text, nullable=False)          # original pasted/extracted text
    source = Column(String, nullable=True)           # e.g. "BDTender email (auto)", "e-GP", "manual"

    tender_ref = Column(String, index=True, unique=True, nullable=True)  # dedup key; null for manual/PDF tenders
    source_email_message_id = Column(String, nullable=True)
    notice_url = Column(String, nullable=True)
    organization = Column(String, nullable=True)
    district = Column(String, nullable=True)

    # Extracted structured fields
    title = Column(String, nullable=True)
    tender_type = Column(String, nullable=True)  # EOI/RFQ/RFP/Proposal/Enlistment/Other - see services.ai.is_relevant_listing
    # Which of Bhumijo's four business entities this belongs to - P&D / FM /
    # WASH / Tech - i.e. what kind of WORK it is, as opposed to tender_type
    # above, which is the procurement FORMAT. Same codes the Proposal Tracker
    # uses, so a tender can move between the two systems unchanged. Set by
    # services.ai.is_relevant_listing (AI path) or agent_free.keywords.check
    # (no-API path); null on rows created before either could label them.
    entity = Column(String, index=True, nullable=True)
    priority = Column(String, nullable=True)  # high/medium/low - user-set, not derived
    publish_date = Column(Date, nullable=True)  # digest's Issue Date; None for manually-pasted notices that didn't state one
    deadline = Column(String, nullable=True)  # raw string as extracted - keep alongside deadline_date, see below
    # A real date, populated whenever `deadline` could be parsed (digest listings always
    # have one - see services.pipeline; the manual/AI-extracted path only sometimes does,
    # since free-text dates aren't always clean DD/MM/YYYY - see services.tender_service
    # and services.dates.parse_ddmmyyyy). `deadline` is never dropped even once this is
    # populated: it's what the human reads, this is what sorting/countdown/auto-archive
    # (below) compute against.
    deadline_date = Column(Date, nullable=True, index=True)
    location = Column(String, nullable=True)
    estimated_value = Column(String, nullable=True)  # contract value - Stage 5 (paste/PDF/fallback) only
    document_price = Column(String, nullable=True)    # fee to buy the tender document (digest listings) - NOT the contract value
    scope_summary = Column(Text, nullable=True)
    eligibility_requirements = Column(Text, nullable=True)
    required_documents = Column(Text, nullable=True)
    instructions = Column(Text, nullable=True)          # submission instructions - Stage 5 (full notice) only
    financial_requirement = Column(Text, nullable=True)  # Stage 5 (full notice) only

    purchase_status = Column(String, default="not_purchased")  # not_purchased / purchased / na - user-set
    special_note = Column(Text, nullable=True)  # free-text, user-written

    # Filter results. hard_filter_pass: True/False = a real Stage 5 eligibility
    # decision; None = not yet known ("needs review" - digest-only data, or not yet run).
    hard_filter_pass = Column(Boolean, nullable=True)
    hard_filter_reason = Column(Text, nullable=True)
    fit_score = Column(Integer, nullable=True)        # 0-100
    fit_reasons = Column(Text, nullable=True)

    processed_at = Column(DateTime, default=_utcnow)
    status = Column(String, default="new")
    # ^ one of: new, tbd, selected, applied, rejected, filtered_out, expired.
    # "filtered_out" is set by the pipeline's Stage 3 relevance screen, never a human.
    # "expired" is set automatically (see services.pipeline._expire_overdue_tenders) on
    # any "new"/"filtered_out" tender whose deadline_date has passed. "tbd", "selected",
    # "applied", and "rejected" are human decisions and are never auto-changed - see that
    # function's docstring for why. "rejected" is reachable from any other status (a side
    # action, not a step in the new/tbd/selected/applied sequence) - see
    # templates/tender_detail.html.

    @property
    def days_remaining(self):
        """Days until the submission deadline, in APP_TIMEZONE (today's LOCAL calendar
        date, not UTC's - a deadline countdown computed against the wrong "today" is
        wrong for up to 6 hours a day). Negative if past. None when deadline_date is
        unknown."""
        if self.deadline_date is None:
            return None
        today_local = datetime.now(APP_TZ).date()
        return (self.deadline_date - today_local).days

    @property
    def urgency(self) -> str:
        """One of "expired", "urgent" (0-7 days), "soon" (8-14), "comfortable" (15+), or
        "unknown" (no deadline_date). Drives the coral/amber/normal/muted styling on the
        dashboard and detail page - see templates/_macros.html."""
        days = self.days_remaining
        if days is None:
            return "unknown"
        if days < 0:
            return "expired"
        if days <= 7:
            return "urgent"
        if days <= 14:
            return "soon"
        return "comfortable"

    @property
    def deadline_display(self) -> str:
        """Human phrase for the countdown - always non-empty, including for the
        unknown/expired cases, so the badge always has something to show rather than
        rendering blank."""
        days = self.days_remaining
        if days is None:
            return "Deadline unknown"
        if days == 0:
            return "Closes today"
        if days == 1:
            return "Closes tomorrow"
        if days > 1:
            return f"Closes in {days} days"
        if days == -1:
            return "Closed 1 day ago"
        return f"Closed {-days} days ago"
