"""The one place that writes UsageLog rows - every AI call, from every path (automated
pipeline and manual paste/PDF alike), logs through here so the cost estimates in the
README can be checked against real token counts. Previously duplicated identically in
app.main and app.pipeline; consolidated so the two copies can't drift apart.
"""
from sqlalchemy.orm import Session

from app.models import UsageLog


def log_usage(db: Session, call_type: str, usage: dict, tender_id=None) -> None:
    db.add(UsageLog(
        call_type=call_type,
        model=usage["model"],
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
        tender_id=tender_id,
    ))
