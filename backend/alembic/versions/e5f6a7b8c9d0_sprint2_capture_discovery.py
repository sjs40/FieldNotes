"""Sprint 2 capture, metrics, ideas and review records.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
"""
from alembic import op
import sqlalchemy as sa
revision="e5f6a7b8c9d0";down_revision="d4e5f6a7b8c9";branch_labels=None;depends_on=None
def upgrade():
 with op.batch_alter_table("saved_views") as b:
  b.add_column(sa.Column("sort_json",sa.JSON,nullable=False,server_default="{}"));b.add_column(sa.Column("columns_json",sa.JSON,nullable=False,server_default="{}"));b.add_column(sa.Column("is_default",sa.Boolean,nullable=False,server_default=sa.false()));b.add_column(sa.Column("is_pinned",sa.Boolean,nullable=False,server_default=sa.false()))
 op.create_table("metric_cards",sa.Column("id",sa.String(36),primary_key=True),sa.Column("user_id",sa.String(36),nullable=False),sa.Column("security_id",sa.String(36),sa.ForeignKey("securities.id")),sa.Column("note_id",sa.String(36),sa.ForeignKey("notes.id")),sa.Column("source_id",sa.String(36),sa.ForeignKey("sources.id")),sa.Column("forecast_id",sa.String(36),sa.ForeignKey("forecasts.id")),sa.Column("metric_name",sa.String(255),nullable=False),sa.Column("metric_definition",sa.Text),sa.Column("value",sa.Numeric(20,6),nullable=False),sa.Column("value_unit",sa.String(32)),sa.Column("period",sa.String(128),nullable=False),sa.Column("prior_value",sa.Numeric(20,6)),sa.Column("consensus_value",sa.Numeric(20,6)),sa.Column("source_excerpt",sa.Text),sa.Column("interpretation",sa.Text),sa.Column("data_json",sa.JSON),sa.Column("created_at",sa.DateTime(timezone=True)),sa.Column("updated_at",sa.DateTime(timezone=True)))
 op.create_table("ideas",sa.Column("id",sa.String(36),primary_key=True),sa.Column("user_id",sa.String(36),nullable=False),sa.Column("originating_note_id",sa.String(36),sa.ForeignKey("notes.id")),sa.Column("source_id",sa.String(36),sa.ForeignKey("sources.id")),sa.Column("promoted_thesis_note_id",sa.String(36),sa.ForeignKey("notes.id")),sa.Column("title",sa.String(500),nullable=False),sa.Column("description",sa.Text),sa.Column("why_it_matters",sa.Text),sa.Column("why_now",sa.Text),sa.Column("expressions",sa.Text),sa.Column("next_step",sa.Text),sa.Column("priority",sa.String(16),nullable=False),sa.Column("stage",sa.String(32),nullable=False),sa.Column("review_at",sa.DateTime(timezone=True)),sa.Column("rejection_reason",sa.Text),sa.Column("created_at",sa.DateTime(timezone=True)),sa.Column("updated_at",sa.DateTime(timezone=True)))
 op.create_table("idea_securities",sa.Column("idea_id",sa.String(36),sa.ForeignKey("ideas.id"),primary_key=True),sa.Column("security_id",sa.String(36),sa.ForeignKey("securities.id"),primary_key=True))
 op.create_table("weekly_reviews",sa.Column("id",sa.String(36),primary_key=True),sa.Column("user_id",sa.String(36),nullable=False),sa.Column("week_start",sa.DateTime(timezone=True),nullable=False),sa.Column("week_end",sa.DateTime(timezone=True),nullable=False),sa.Column("summary_json",sa.JSON,nullable=False),sa.Column("conclusions_json",sa.JSON,nullable=False),sa.Column("completed_at",sa.DateTime(timezone=True)),sa.Column("created_at",sa.DateTime(timezone=True)),sa.Column("updated_at",sa.DateTime(timezone=True)),sa.UniqueConstraint("user_id","week_start",name="uq_weekly_review_period"))
 for table in ("metric_cards","ideas","weekly_reviews"):op.create_index("ix_%s_user_id"%table,table,["user_id"])
def downgrade():
 for table in ("weekly_reviews","idea_securities","ideas","metric_cards"):op.drop_table(table)
 with op.batch_alter_table("saved_views") as b:
  b.drop_column("is_pinned");b.drop_column("is_default");b.drop_column("columns_json");b.drop_column("sort_json")
