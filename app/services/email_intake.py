"""IMAP intake for tender alert emails. Host/port are configured (app.config.IMAP_HOST/
IMAP_PORT, currently Zoho) rather than hardcoded, so the mailbox can move providers
without a code change.

Pulls recent inbox mail broadly - NOT filtered by sender at the IMAP level.
Tender alerts can come from BDTender or other aggregators/portals we don't
know about in advance, so narrowing by sender here would silently drop
sources. Stage 1 classification (app.services.ai.is_tender_email) is what decides
whether a given email is actually a tender notice; an optional sender
denylist is the only hard exclusion applied here, for known noise.
"""
import imaplib
import email
import re
from email.header import decode_header
from datetime import datetime, timedelta, timezone

from app.config import APP_TZ, CLASSIFICATION_SNIPPET_CAP, IMAP_HOST, IMAP_PORT


def _decode(value) -> str:
    if value is None:
        return ""
    parts = decode_header(value)
    out = []
    for text, enc in parts:
        if isinstance(text, bytes):
            out.append(text.decode(enc or "utf-8", errors="ignore"))
        else:
            out.append(text)
    return "".join(out)


def _extract_bodies(msg):
    """Return (text_body, html_body) for an email.message.Message; either may be None.
    html_body is kept as real markup (not stripped) since app.digest_parse needs it."""
    text_body, html_body = None, None
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if "attachment" in disp:
                continue
            if ctype == "text/plain" and text_body is None:
                payload = part.get_payload(decode=True)
                if payload is not None:
                    text_body = payload.decode(errors="ignore")
            elif ctype == "text/html" and html_body is None:
                payload = part.get_payload(decode=True)
                if payload is not None:
                    html_body = payload.decode(errors="ignore")
    else:
        payload = msg.get_payload(decode=True)
        if payload is not None:
            decoded = payload.decode(errors="ignore")
            if msg.get_content_type() == "text/html":
                html_body = decoded
            else:
                text_body = decoded

    return (
        text_body.strip() if text_body else None,
        html_body.strip() if html_body else None,
    )


def plain_snippet(text_body, html_body, max_chars: int = CLASSIFICATION_SNIPPET_CAP) -> str:
    """Best-effort plain-text snippet, capped, for cheap Stage 1 classification calls."""
    text = text_body
    if not text and html_body:
        text = re.sub(r"<[^>]+>", " ", html_body)
        text = re.sub(r"\s+", " ", text)
    if not text:
        return ""
    return text.strip()[:max_chars]


def _connection_error_message(host: str, port: int, original: Exception) -> str:
    """Turns a raw imaplib/socket exception into something actionable. AUTHENTICATIONFAILED
    gets the Zoho-specific checklist (this mailbox's provider); anything else (DNS,
    connection refused, timeout) just gets the host/port made explicit, since "which
    server did it try" is the first question either way."""
    if "AUTHENTICATIONFAILED" in str(original).upper():
        return (
            f"IMAP login to {host}:{port} failed (AUTHENTICATIONFAILED). Likely causes:\n"
            "1. Using the normal Zoho account password instead of an app-specific "
            "password generated at accounts.zoho.com -> Security -> App Passwords\n"
            "2. IMAP Access disabled in Zoho Mail (Settings -> Mail Accounts -> IMAP)\n"
            "3. Wrong host - Zoho's IMAP endpoint varies by data centre and plan "
            "(imappro.zoho.com, imap.zoho.com, imap.zoho.in, imap.zoho.eu). "
            f"Currently configured host: {host}\n"
            "4. Wrong email address"
        )
    return f"Could not connect to {host}:{port}: {original}"


def _connect_and_login(host: str, port: int, imap_email: str, app_password: str) -> imaplib.IMAP4_SSL:
    try:
        imap = imaplib.IMAP4_SSL(host, port)
        imap.login(imap_email, app_password)
        return imap
    except Exception as e:
        raise RuntimeError(_connection_error_message(host, port, e)) from e


def test_connection(imap_email: str, app_password: str, host: str = None, port: int = None) -> None:
    """Attempts an IMAP login only - no fetch, no AI calls - so a credential can be
    verified in isolation at zero cost (see the "Test connection" button in Email
    settings). Raises RuntimeError with a diagnostic message on failure; returns None on
    success."""
    host = host or IMAP_HOST
    port = port or IMAP_PORT
    imap = _connect_and_login(host, port, imap_email, app_password)
    try:
        imap.logout()
    except Exception:
        pass


def fetch_recent_emails(imap_email: str, app_password: str, already_processed_ids: set,
                         denylist: list = None, max_results: int = 50,
                         since_days: int = 3, host: str = None, port: int = None) -> list:
    """
    Connects via IMAP (App Password auth) to `host`:`port` (defaults to the configured
    IMAP_HOST/IMAP_PORT - see app.config) and returns recent inbox emails not already in
    already_processed_ids, skipping any sender matching `denylist` (substring,
    case-insensitive). Each result dict: message_id, subject, from, body_text, body_html,
    received_at.
    """
    host = host or IMAP_HOST
    port = port or IMAP_PORT
    denylist = [d.strip().lower() for d in (denylist or []) if d.strip()]
    results = []
    imap = _connect_and_login(host, port, imap_email, app_password)
    try:
        imap.select("INBOX")

        # IMAP SINCE is date-only. Computed from local (APP_TIMEZONE) "now", not UTC -
        # otherwise, near local midnight, "N days ago" lands on the wrong calendar day
        # from a Dhaka reader's perspective and the search window shifts by a day.
        since_date = (datetime.now(APP_TZ) - timedelta(days=since_days)).strftime("%d-%b-%Y")
        status, data = imap.search(None, f'(SINCE "{since_date}")')
        if status != "OK":
            return results

        ids = data[0].split()
        ids = ids[-max_results:] if len(ids) > max_results else ids

        for eid in reversed(ids):
            status, msg_data = imap.fetch(eid, "(RFC822)")
            if status != "OK" or not msg_data or msg_data[0] is None:
                continue
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            message_id = msg.get("Message-ID") or f"{imap_email}-{eid.decode()}"
            if message_id in already_processed_ids:
                continue

            sender = _decode(msg.get("From"))
            if denylist and any(d in sender.lower() for d in denylist):
                continue

            subject = _decode(msg.get("Subject"))
            text_body, html_body = _extract_bodies(msg)

            if not text_body and not html_body:
                continue

            results.append({
                "message_id": message_id,
                "subject": subject,
                "from": sender,
                "body_text": text_body,
                "body_html": html_body,
                "received_at": datetime.now(timezone.utc),
            })
    finally:
        try:
            imap.logout()
        except Exception:
            pass

    return results
