"""structured tender sheet fields and status workflow

Adds the columns needed for the redesigned tender detail page (a structured
information sheet - see templates/tender_detail.html and README):
tender_type, priority, publish_date, instructions, financial_requirement,
purchase_status, special_note.

Also migrates the status workflow: the old ad-hoc "shortlisted" value becomes
"selected" (the new workflow is new -> tbd -> selected -> applied, plus the
side actions rejected/filtered_out/expired). Every other existing status value
(new, applied, rejected, filtered_out, expired) keeps its value unchanged -
none of those names moved.

publish_date is a real gap being closed here: app.services.digest_parse has
always parsed the digest's Issue Date correctly, but Tender had no column for
it, so every digest run was discarding it. New digest runs after this
migration store it directly (see services.pipeline); existing rows are left
null rather than guessed at, matching this project's existing policy on dates
it can't parse with confidence (see 91db58dcffb0's docstring).

purchase_status is backfilled to "not_purchased" for every existing row -
matching the column's application-level default (models.Tender.purchase_status)
so existing rows read the same as new ones would, rather than showing as
blank/unknown on the redesigned detail page.

Revision ID: cd43a33c54d3
Revises: 91db58dcffb0
Create Date: 2026-08-17 11:04:35.113071

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cd43a33c54d3'
down_revision: Union[str, Sequence[str], None] = '91db58dcffb0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('tenders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tender_type', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('priority', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('publish_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('instructions', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('financial_requirement', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('purchase_status', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('special_note', sa.Text(), nullable=True))

    connection = op.get_bind()
    connection.execute(sa.text("UPDATE tenders SET status = 'selected' WHERE status = 'shortlisted'"))
    connection.execute(sa.text("UPDATE tenders SET purchase_status = 'not_purchased' WHERE purchase_status IS NULL"))


def downgrade() -> None:
    """Downgrade schema."""
    connection = op.get_bind()
    connection.execute(sa.text("UPDATE tenders SET status = 'shortlisted' WHERE status = 'selected'"))

    with op.batch_alter_table('tenders', schema=None) as batch_op:
        batch_op.drop_column('special_note')
        batch_op.drop_column('purchase_status')
        batch_op.drop_column('financial_requirement')
        batch_op.drop_column('instructions')
        batch_op.drop_column('publish_date')
        batch_op.drop_column('priority')
        batch_op.drop_column('tender_type')
