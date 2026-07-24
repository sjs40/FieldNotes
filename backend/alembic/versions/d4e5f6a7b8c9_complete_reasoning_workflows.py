"""Complete Sprint 1 reasoning workflow tables and integrity constraints.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
"""
from alembic import op
import sqlalchemy as sa

revision="d4e5f6a7b8c9"; down_revision="c3d4e5f6a7b8"; branch_labels=None; depends_on=None

def upgrade():
    # A database check complements service-level ownership checks.
    with op.batch_alter_table("note_relationships") as b:
        b.create_check_constraint("ck_note_relationship_not_self", "from_note_id <> to_note_id")
    op.create_table("evidence_theses",sa.Column("evidence_id",sa.String(36),sa.ForeignKey("evidence.id"),primary_key=True),sa.Column("thesis_note_id",sa.String(36),sa.ForeignKey("notes.id"),primary_key=True))
    op.create_table("evidence_forecasts",sa.Column("evidence_id",sa.String(36),sa.ForeignKey("evidence.id"),primary_key=True),sa.Column("forecast_id",sa.String(36),sa.ForeignKey("forecasts.id"),primary_key=True))
    op.create_table("evidence_questions",sa.Column("evidence_id",sa.String(36),sa.ForeignKey("evidence.id"),primary_key=True),sa.Column("question_id",sa.String(36),sa.ForeignKey("research_questions.id"),primary_key=True))
    op.create_table("question_events",sa.Column("id",sa.String(36),primary_key=True),sa.Column("question_id",sa.String(36),sa.ForeignKey("research_questions.id"),nullable=False),sa.Column("user_id",sa.String(36),nullable=False),sa.Column("event_type",sa.String(32),nullable=False),sa.Column("from_value",sa.Text),sa.Column("to_value",sa.Text),sa.Column("explanation",sa.Text),sa.Column("created_at",sa.DateTime(timezone=True)))
    op.create_table("forecast_events",sa.Column("id",sa.String(36),primary_key=True),sa.Column("forecast_id",sa.String(36),sa.ForeignKey("forecasts.id"),nullable=False),sa.Column("user_id",sa.String(36),nullable=False),sa.Column("event_type",sa.String(32),nullable=False),sa.Column("snapshot_json",sa.JSON),sa.Column("explanation",sa.Text),sa.Column("created_at",sa.DateTime(timezone=True)))
    op.create_table("saved_views",sa.Column("id",sa.String(36),primary_key=True),sa.Column("user_id",sa.String(36),nullable=False),sa.Column("name",sa.String(120),nullable=False),sa.Column("resource",sa.String(32),nullable=False),sa.Column("filters_json",sa.JSON,nullable=False),sa.Column("created_at",sa.DateTime(timezone=True)),sa.Column("updated_at",sa.DateTime(timezone=True)),sa.UniqueConstraint("user_id","resource","name",name="uq_saved_view_name"))
    for table in ("question_events","forecast_events","saved_views"):
        op.create_index("ix_%s_user_id" % table,table,["user_id"])

def downgrade():
    for table in ("saved_views","forecast_events","question_events","evidence_questions","evidence_forecasts","evidence_theses"): op.drop_table(table)
    with op.batch_alter_table("note_relationships") as b: b.drop_constraint("ck_note_relationship_not_self",type_="check")
