"""add Tender.entity

Adds Tender.entity: which of Bhumijo's four business entities a tender belongs
to - P&D, FM, WASH or Tech - i.e. WHAT KIND OF WORK it is.

This is deliberately separate from the existing `tender_type` column, which
records the PROCUREMENT FORMAT (EOI/RFQ/RFP/Proposal/Enlistment/Other). The two
answer different questions: tender_type says how you bid, entity says whose job
it is. "Construction of a Public Toilet Block" is tender_type=Other,
entity=WASH; both labels are useful and neither substitutes for the other.

The values match the entity codes the Proposal Tracker already uses, so a tender
picked up here can later be pushed into that system under the right entity
without a translation step.

Existing rows are left null rather than back-filled: the entity of a historical
row cannot be determined without re-running the classifier over it, and
inventing a value would be worse than an honest blank. The dashboard renders
null as an em dash.

Revision ID: b7e1d94c02aa
Revises: cd43a33c54d3
Create Date: 2026-09-09 16:05:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "b7e1d94c02aa"
down_revision = "cd43a33c54d3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tenders", sa.Column("entity", sa.String(), nullable=True))
    op.create_index("ix_tenders_entity", "tenders", ["entity"])


def downgrade():
    op.drop_index("ix_tenders_entity", table_name="tenders")
    op.drop_column("tenders", "entity")
