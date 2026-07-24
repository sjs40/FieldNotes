"""Add the normalized reasoning graph and research ledgers.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
"""
from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    # Existing relationship rows remain valid legacy ``update_of`` rows.
    with op.batch_alter_table("note_relationships") as b:
        b.add_column(sa.Column("user_id", sa.String(36), nullable=True))
        b.add_column(sa.Column("explanation", sa.Text(), nullable=True))
        b.add_column(sa.Column("created_by_workflow", sa.String(64), nullable=True))
        b.create_index("ix_note_relationships_user_id", ["user_id"])
        b.create_unique_constraint("uq_note_relationship", ["from_note_id", "to_note_id", "relationship_type"])
    op.execute("UPDATE note_relationships SET user_id = (SELECT user_id FROM notes WHERE notes.id = note_relationships.from_note_id) WHERE user_id IS NULL")
    op.create_table("thinking_updates", sa.Column("id",sa.String(36),primary_key=True),sa.Column("user_id",sa.String(36),nullable=False),sa.Column("security_id",sa.String(36),sa.ForeignKey("securities.id")),sa.Column("update_note_id",sa.String(36),sa.ForeignKey("notes.id"),nullable=False),sa.Column("prior_note_id",sa.String(36),sa.ForeignKey("notes.id")),sa.Column("tracked_call_id",sa.String(36),sa.ForeignKey("tracked_calls.id")),sa.Column("change_direction",sa.String(16),nullable=False),sa.Column("confidence_before",sa.String(16)),sa.Column("confidence_after",sa.String(16)),sa.Column("thesis_state_before",sa.String(32)),sa.Column("thesis_state_after",sa.String(32)),sa.Column("target_before",sa.Numeric(18,6)),sa.Column("target_after",sa.Numeric(18,6)),sa.Column("target_unit",sa.String(16)),sa.Column("horizon_before_days",sa.Integer),sa.Column("horizon_after_days",sa.Integer),sa.Column("change_reason",sa.Text),sa.Column("created_at",sa.DateTime(timezone=True)))
    op.create_table("assumptions", sa.Column("id",sa.String(36),primary_key=True),sa.Column("user_id",sa.String(36),nullable=False),sa.Column("security_id",sa.String(36),sa.ForeignKey("securities.id")),sa.Column("thesis_note_id",sa.String(36),sa.ForeignKey("notes.id")),sa.Column("originating_note_id",sa.String(36),sa.ForeignKey("notes.id")),sa.Column("statement",sa.Text,nullable=False),sa.Column("category",sa.String(64)),sa.Column("status",sa.String(20),nullable=False),sa.Column("importance",sa.String(16),nullable=False),sa.Column("current_value",sa.String(255)),sa.Column("value_unit",sa.String(32)),sa.Column("expected_value",sa.String(255)),sa.Column("expected_period",sa.String(128)),sa.Column("review_at",sa.DateTime(timezone=True)),sa.Column("resolved_at",sa.DateTime(timezone=True)),sa.Column("created_at",sa.DateTime(timezone=True)),sa.Column("updated_at",sa.DateTime(timezone=True)))
    op.create_table("assumption_events", sa.Column("id",sa.String(36),primary_key=True),sa.Column("assumption_id",sa.String(36),sa.ForeignKey("assumptions.id"),nullable=False),sa.Column("user_id",sa.String(36),nullable=False),sa.Column("event_type",sa.String(32),nullable=False),sa.Column("from_value",sa.Text),sa.Column("to_value",sa.Text),sa.Column("explanation",sa.Text),sa.Column("created_at",sa.DateTime(timezone=True)))
    op.create_table("evidence", sa.Column("id",sa.String(36),primary_key=True),sa.Column("user_id",sa.String(36),nullable=False),sa.Column("security_id",sa.String(36),sa.ForeignKey("securities.id")),sa.Column("originating_note_id",sa.String(36),sa.ForeignKey("notes.id")),sa.Column("source_id",sa.String(36),sa.ForeignKey("sources.id")),sa.Column("source_excerpt",sa.Text),sa.Column("statement",sa.Text,nullable=False),sa.Column("evidence_direction",sa.String(16),nullable=False),sa.Column("strength",sa.String(16),nullable=False),sa.Column("status",sa.String(16),nullable=False),sa.Column("observed_at",sa.DateTime(timezone=True)),sa.Column("expires_at",sa.DateTime(timezone=True)),sa.Column("reliability",sa.String(32)),sa.Column("commentary",sa.Text),sa.Column("created_at",sa.DateTime(timezone=True)),sa.Column("updated_at",sa.DateTime(timezone=True)))
    op.create_table("evidence_assumptions",sa.Column("evidence_id",sa.String(36),sa.ForeignKey("evidence.id"),primary_key=True),sa.Column("assumption_id",sa.String(36),sa.ForeignKey("assumptions.id"),primary_key=True))
    op.create_table("research_questions", sa.Column("id",sa.String(36),primary_key=True),sa.Column("user_id",sa.String(36),nullable=False),sa.Column("security_id",sa.String(36),sa.ForeignKey("securities.id")),sa.Column("originating_note_id",sa.String(36),sa.ForeignKey("notes.id")),sa.Column("thesis_note_id",sa.String(36),sa.ForeignKey("notes.id")),sa.Column("assumption_id",sa.String(36),sa.ForeignKey("assumptions.id")),sa.Column("question",sa.Text,nullable=False),sa.Column("status",sa.String(24),nullable=False),sa.Column("priority",sa.String(16),nullable=False),sa.Column("answer_summary",sa.Text),sa.Column("answered_by_note_id",sa.String(36),sa.ForeignKey("notes.id")),sa.Column("answered_by_source_id",sa.String(36),sa.ForeignKey("sources.id")),sa.Column("due_at",sa.DateTime(timezone=True)),sa.Column("resolved_at",sa.DateTime(timezone=True)),sa.Column("created_at",sa.DateTime(timezone=True)),sa.Column("updated_at",sa.DateTime(timezone=True)))
    op.create_table("forecasts", sa.Column("id",sa.String(36),primary_key=True),sa.Column("user_id",sa.String(36),nullable=False),sa.Column("security_id",sa.String(36),sa.ForeignKey("securities.id")),sa.Column("originating_note_id",sa.String(36),sa.ForeignKey("notes.id")),sa.Column("thesis_note_id",sa.String(36),sa.ForeignKey("notes.id")),sa.Column("assumption_id",sa.String(36),sa.ForeignKey("assumptions.id")),sa.Column("metric_name",sa.String(255),nullable=False),sa.Column("metric_definition",sa.Text),sa.Column("forecast_type",sa.String(16),nullable=False),sa.Column("target_value",sa.Numeric(18,6)),sa.Column("lower_bound",sa.Numeric(18,6)),sa.Column("upper_bound",sa.Numeric(18,6)),sa.Column("value_unit",sa.String(32)),sa.Column("direction",sa.String(16)),sa.Column("probability",sa.Numeric(6,5)),sa.Column("target_period_start",sa.DateTime(timezone=True),nullable=False),sa.Column("target_period_end",sa.DateTime(timezone=True)),sa.Column("status",sa.String(16),nullable=False),sa.Column("resolution_value",sa.Numeric(18,6)),sa.Column("resolution_source_id",sa.String(36),sa.ForeignKey("sources.id")),sa.Column("resolution_note",sa.Text),sa.Column("resolved_at",sa.DateTime(timezone=True)),sa.Column("error_value",sa.Numeric(18,6)),sa.Column("error_percentage",sa.Numeric(18,6)),sa.Column("outcome",sa.String(24)),sa.Column("created_at",sa.DateTime(timezone=True)),sa.Column("updated_at",sa.DateTime(timezone=True)))
    for table in ("thinking_updates","assumptions","assumption_events","evidence","research_questions","forecasts"):
        op.create_index("ix_%s_user_id" % table, table, ["user_id"])


def downgrade():
    for table in ("forecasts","research_questions","evidence_assumptions","evidence","assumption_events","assumptions","thinking_updates"):
        op.drop_table(table)
    with op.batch_alter_table("note_relationships") as b:
        b.drop_constraint("uq_note_relationship", type_="unique")
        b.drop_index("ix_note_relationships_user_id")
        b.drop_column("created_by_workflow"); b.drop_column("explanation"); b.drop_column("user_id")
