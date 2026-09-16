"""add tender deadline_date

Adds Tender.deadline_date (a real Date, indexed) alongside the existing `deadline`
string column, and backfills it for existing rows whose `deadline` string parses as
DD/MM/YYYY - the format Bangladeshi tender notices use. Anything else (a digest-derived
ISO string like "2026-08-24", unparseable AI-extracted free text, or blank) is left
null deliberately - see app.services.dates.parse_ddmmyyyy's docstring on not guessing.
This only matters for rows that existed before this migration; every row created after
it gets deadline_date populated directly at write time (see app.services.pipeline and
app.services.tender_service), never via this string-parsing path.

The backfill regex is duplicated from app.services.dates rather than imported, on
purpose: a migration is a frozen snapshot of what ran at this point in time and must
keep working even if the application code it shares a repo with changes later.

Revision ID: 91db58dcffb0
Revises: f8b4f610f463
Create Date: 2026-08-14 15:58:30.794678

"""
import re
from datetime import date
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '91db58dcffb0'
down_revision: Union[str, Sequence[str], None] = 'f8b4f610f463'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DDMMYYYY_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('tenders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('deadline_date', sa.Date(), nullable=True))
        batch_op.create_index(batch_op.f('ix_tenders_deadline_date'), ['deadline_date'], unique=False)

    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, deadline FROM tenders WHERE deadline IS NOT NULL")).fetchall()
    for row in rows:
        m = _DDMMYYYY_RE.search(row.deadline)
        if not m:
            continue
        day, month, year = (int(x) for x in m.groups())
        try:
            parsed = date(year, month, day)
        except ValueError:
            continue
        connection.execute(
            sa.text("UPDATE tenders SET deadline_date = :d WHERE id = :row_id"),
            {"d": parsed.isoformat(), "row_id": row.id},
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('tenders', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tenders_deadline_date'))
        batch_op.drop_column('deadline_date')
