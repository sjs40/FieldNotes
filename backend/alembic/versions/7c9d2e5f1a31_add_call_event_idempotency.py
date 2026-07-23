"""add call event idempotency

Revision ID: 7c9d2e5f1a31
Revises: 2741b21856ba
"""
from alembic import op
import sqlalchemy as sa


revision = "7c9d2e5f1a31"
down_revision = "2741b21856ba"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("call_events", sa.Column("tracked_call_id", sa.String(length=36), nullable=True))
    op.add_column("call_events", sa.Column("idempotency_key", sa.String(length=128), nullable=True))
    op.create_foreign_key("fk_call_events_tracked_call", "call_events", "tracked_calls", ["tracked_call_id"], ["id"])
    op.create_index("ix_call_events_tracked_call_id", "call_events", ["tracked_call_id"])
    op.create_unique_constraint("uq_call_event_idempotency", "call_events", ["tracked_call_id", "idempotency_key"])


def downgrade():
    op.drop_constraint("uq_call_event_idempotency", "call_events", type_="unique")
    op.drop_index("ix_call_events_tracked_call_id", table_name="call_events")
    op.drop_constraint("fk_call_events_tracked_call", "call_events", type_="foreignkey")
    op.drop_column("call_events", "idempotency_key")
    op.drop_column("call_events", "tracked_call_id")
