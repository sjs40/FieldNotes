"""Add immutable forecast revisions and reusable KPI observations.

Revision ID: 29c0d1e2f3a4
Revises: 18b9c0d1e2f3
"""

from alembic import op
import sqlalchemy as sa


revision = "29c0d1e2f3a4"
down_revision = "18b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kpi_definitions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("security_id", sa.String(length=36), sa.ForeignKey("securities.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("definition", sa.Text(), nullable=True),
        sa.Column("value_unit", sa.String(length=32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "security_id", "name", name="uq_kpi_definition_name"),
    )
    op.create_index("ix_kpi_definitions_user_id", "kpi_definitions", ["user_id"])
    op.create_index("ix_kpi_definitions_security_id", "kpi_definitions", ["security_id"])
    op.create_table(
        "kpi_observations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("kpi_definition_id", sa.String(length=36), sa.ForeignKey("kpi_definitions.id"), nullable=False),
        sa.Column("earnings_event_id", sa.String(length=36), sa.ForeignKey("earnings_events.id"), nullable=True),
        sa.Column("note_id", sa.String(length=36), sa.ForeignKey("notes.id"), nullable=True),
        sa.Column("source_id", sa.String(length=36), sa.ForeignKey("sources.id"), nullable=True),
        sa.Column("period", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Numeric(20, 6), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("interpretation", sa.Text(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_kpi_observations_user_id", "kpi_observations", ["user_id"])
    op.create_index("ix_kpi_observations_kpi_definition_id", "kpi_observations", ["kpi_definition_id"])
    op.create_index("ix_kpi_observations_earnings_event_id", "kpi_observations", ["earnings_event_id"])
    op.add_column("forecasts", sa.Column("expected_outcome", sa.Text(), nullable=True))
    op.add_column("forecasts", sa.Column("confidence", sa.String(length=16), nullable=True))
    op.add_column("forecasts", sa.Column("resolution_event", sa.String(length=255), nullable=True))
    op.add_column("forecasts", sa.Column("resolution_observation_id", sa.String(length=36), sa.ForeignKey("kpi_observations.id"), nullable=True))
    op.add_column("forecasts", sa.Column("supersedes_forecast_id", sa.String(length=36), sa.ForeignKey("forecasts.id"), nullable=True))
    op.add_column("forecasts", sa.Column("revision_number", sa.Integer(), nullable=False, server_default="1"))
    op.create_index("ix_forecasts_supersedes_forecast_id", "forecasts", ["supersedes_forecast_id"])


def downgrade() -> None:
    op.drop_index("ix_forecasts_supersedes_forecast_id", table_name="forecasts")
    op.drop_column("forecasts", "revision_number")
    op.drop_column("forecasts", "supersedes_forecast_id")
    op.drop_column("forecasts", "resolution_observation_id")
    op.drop_column("forecasts", "resolution_event")
    op.drop_column("forecasts", "confidence")
    op.drop_column("forecasts", "expected_outcome")
    op.drop_index("ix_kpi_observations_earnings_event_id", table_name="kpi_observations")
    op.drop_index("ix_kpi_observations_kpi_definition_id", table_name="kpi_observations")
    op.drop_index("ix_kpi_observations_user_id", table_name="kpi_observations")
    op.drop_table("kpi_observations")
    op.drop_index("ix_kpi_definitions_security_id", table_name="kpi_definitions")
    op.drop_index("ix_kpi_definitions_user_id", table_name="kpi_definitions")
    op.drop_table("kpi_definitions")
