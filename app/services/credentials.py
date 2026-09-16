"""Resolves the IMAP/SMTP App Password used for both IMAP fetch (app.services.pipeline)
and SMTP notify (app.services.notify) - see docs/SECURITY.md for the full migration
story.

IMAP_APP_PASSWORD in the environment is authoritative. GMAIL_APP_PASSWORD (the old name,
from when this mailbox was Gmail) is accepted as a deprecated fallback so a machine that
hasn't been updated to the new variable name doesn't just start failing auth.
EmailSettings.imap_app_password (the database column) is a second, older deprecated
fallback, kept only so nothing breaks mid-migration - see models.EmailSettings and
clear_db_app_password_if_env_configured() below, called at startup once an environment
variable is confirmed set.
"""
import logging

from app.config import IMAP_APP_PASSWORD, GMAIL_APP_PASSWORD

logger = logging.getLogger("tender_agent")


def get_app_password(settings) -> str:
    """Returns the App Password to use, or None if no source has one. Preference order:
    IMAP_APP_PASSWORD (current) -> GMAIL_APP_PASSWORD (deprecated env fallback, logs a
    warning) -> settings.imap_app_password (deprecated DB fallback, logs a warning)."""
    if IMAP_APP_PASSWORD:
        return IMAP_APP_PASSWORD
    if GMAIL_APP_PASSWORD:
        logger.warning(
            "GMAIL_APP_PASSWORD is deprecated - rename it to IMAP_APP_PASSWORD in the "
            "environment (see docs/SECURITY.md). Falling back to GMAIL_APP_PASSWORD for now."
        )
        return GMAIL_APP_PASSWORD
    if settings and settings.imap_app_password:
        logger.warning(
            "IMAP_APP_PASSWORD is not set in the environment - falling back to the "
            "App Password stored in the database (deprecated). Set the environment "
            "variable - see docs/SECURITY.md - so the plaintext database copy can be "
            "cleared."
        )
        return settings.imap_app_password
    return None


def is_app_password_configured() -> bool:
    """Env-only check (no DB fallback, no logging) for display purposes - see
    routes.settings and templates/email_settings.html."""
    return bool(IMAP_APP_PASSWORD or GMAIL_APP_PASSWORD)


def clear_db_app_password_if_env_configured(db, settings) -> None:
    """One-off migration, run at startup: once an App Password is confirmed set in the
    environment (IMAP_APP_PASSWORD, or the deprecated GMAIL_APP_PASSWORD), the plaintext
    copy in the database is no longer needed and must not linger - see
    models.EmailSettings.imap_app_password and docs/SECURITY.md."""
    if settings and settings.imap_app_password and (IMAP_APP_PASSWORD or GMAIL_APP_PASSWORD):
        settings.imap_app_password = None
        db.commit()
        logger.info("startup: an IMAP App Password is set in the environment - cleared "
                    "the plaintext App Password that was stored in the database")
