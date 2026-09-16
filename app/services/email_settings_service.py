"""DB helper for EmailSettings - there is always exactly one row (single-tenant app),
created on first access. Shared by routes/settings.py and services/scheduler.py.
"""
from sqlalchemy.orm import Session

from app.models import EmailSettings


def get_or_create_email_settings(db: Session) -> EmailSettings:
    settings = db.query(EmailSettings).first()
    if not settings:
        settings = EmailSettings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings
