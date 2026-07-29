"""Add user-owned earnings events and research links.

Revision ID: 18b9c0d1e2f3
Revises: 07a8b9c0d1e2
"""

from alembic import op
import sqlalchemy as sa


revision = "18b9c0d1e2f3"
down_revision = "07a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "earnings_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("security_id", sa.String(length=36), sa.ForeignKey("securities.id"), nullable=False),
        sa.Column("fiscal_period", sa.String(length=128), nullable=False),
        sa.Column("reporting_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pre_expectations", sa.Text(), nullable=True),
        sa.Column("pre_kpi_watch_list", sa.Text(), nullable=True),
        sa.Column("pre_debate_questions", sa.Text(), nullable=True),
        sa.Column("pre_catalysts", sa.Text(), nullable=True),
        sa.Column("pre_risks", sa.Text(), nullable=True),
        sa.Column("pre_notes", sa.Text(), nullable=True),
        sa.Column("earnings_results", sa.Text(), nullable=True),
        sa.Column("earnings_guidance", sa.Text(), nullable=True),
        sa.Column("earnings_kpi_observations", sa.Text(), nullable=True),
        sa.Column("earnings_management_quotes", sa.Text(), nullable=True),
        sa.Column("earnings_market_reaction", sa.Text(), nullable=True),
        sa.Column("earnings_notes", sa.Text(), nullable=True),
        sa.Column("post_expected_vs_actual", sa.Text(), nullable=True),
        sa.Column("post_thesis_impact", sa.Text(), nullable=True),
        sa.Column("post_question_resolution", sa.Text(), nullable=True),
        sa.Column("post_decision_action", sa.Text(), nullable=True),
        sa.Column("post_notes", sa.Text(), nullable=True),
        sa.Column("pre_recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "security_id", "fiscal_period", name="uq_earnings_event_period"),
    )
    op.create_index("ix_earnings_events_user_id", "earnings_events", ["user_id"])
    op.create_index("ix_earnings_events_security_id", "earnings_events", ["security_id"])
    op.create_table(
        "earnings_event_notes",
        sa.Column("earnings_event_id", sa.String(length=36), sa.ForeignKey("earnings_events.id"), primary_key=True),
        sa.Column("note_id", sa.String(length=36), sa.ForeignKey("notes.id"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "earnings_event_sources",
        sa.Column("earnings_event_id", sa.String(length=36), sa.ForeignKey("earnings_events.id"), primary_key=True),
        sa.Column("source_id", sa.String(length=36), sa.ForeignKey("sources.id"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("earnings_event_sources")
    op.drop_table("earnings_event_notes")
    op.drop_index("ix_earnings_events_security_id", table_name="earnings_events")
    op.drop_index("ix_earnings_events_user_id", table_name="earnings_events")
    op.drop_table("earnings_events")
