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
    # SQLite cannot ALTER a table to add constraints. Batch mode rebuilds the
    # table there; PostgreSQL keeps its straightforward ALTER path.
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("call_events") as batch:
            batch.add_column(sa.Column("tracked_call_id", sa.String(length=36), nullable=True))
            batch.add_column(sa.Column("idempotency_key", sa.String(length=128), nullable=True))
            batch.create_foreign_key("fk_call_events_tracked_call", "tracked_calls", ["tracked_call_id"], ["id"])
            batch.create_index("ix_call_events_tracked_call_id", ["tracked_call_id"])
            batch.create_unique_constraint("uq_call_event_idempotency", ["tracked_call_id", "idempotency_key"])
        return
    op.add_column("call_events", sa.Column("tracked_call_id", sa.String(length=36), nullable=True))
    op.add_column("call_events", sa.Column("idempotency_key", sa.String(length=128), nullable=True))
    op.create_foreign_key("fk_call_events_tracked_call", "call_events", "tracked_calls", ["tracked_call_id"], ["id"])
    op.create_index("ix_call_events_tracked_call_id", "call_events", ["tracked_call_id"])
    op.create_unique_constraint("uq_call_event_idempotency", "call_events", ["tracked_call_id", "idempotency_key"])


def downgrade():
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("call_events") as batch:
            batch.drop_constraint("uq_call_event_idempotency", type_="unique")
            batch.drop_index("ix_call_events_tracked_call_id")
            batch.drop_constraint("fk_call_events_tracked_call", type_="foreignkey")
            batch.drop_column("idempotency_key")
            batch.drop_column("tracked_call_id")
        return
    op.drop_constraint("uq_call_event_idempotency", "call_events", type_="unique")
    op.drop_index("ix_call_events_tracked_call_id", table_name="call_events")
    op.drop_constraint("fk_call_events_tracked_call", "call_events", type_="foreignkey")
    op.drop_column("call_events", "idempotency_key")
    op.drop_column("call_events", "tracked_call_id")
