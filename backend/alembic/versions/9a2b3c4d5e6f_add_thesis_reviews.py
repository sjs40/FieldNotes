"""Sprint 2 review queue settings and review history."""
from alembic import op
import sqlalchemy as sa
revision="9a2b3c4d5e6f"
down_revision="8f1a2b3c4d5e"
branch_labels=depends_on=None
def upgrade():
    op.create_table("user_review_settings",sa.Column("user_id",sa.String(36),primary_key=True),sa.Column("stale_warning_days",sa.Integer,nullable=False),sa.Column("stale_critical_days",sa.Integer,nullable=False),sa.Column("absolute_move_threshold",sa.Numeric(8,6),nullable=False),sa.Column("relative_move_threshold",sa.Numeric(8,6),nullable=False),sa.Column("daily_move_threshold",sa.Numeric(8,6),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True)))
    op.create_table("thesis_reviews",sa.Column("id",sa.String(36),primary_key=True),sa.Column("user_id",sa.String(36),nullable=False),sa.Column("tracked_call_id",sa.String(36),sa.ForeignKey("tracked_calls.id"),nullable=False),sa.Column("review_type",sa.String(32),nullable=False),sa.Column("scheduled_for",sa.DateTime(timezone=True)),sa.Column("completed_at",sa.DateTime(timezone=True)),sa.Column("review_status",sa.String(16),nullable=False),sa.Column("outcome",sa.String(32)),sa.Column("confidence_before",sa.String(16)),sa.Column("confidence_after",sa.String(16)),sa.Column("thesis_state_before",sa.String(32)),sa.Column("thesis_state_after",sa.String(32)),sa.Column("target_changed",sa.Boolean,nullable=False),sa.Column("explanation",sa.Text),sa.Column("snapshot_json",sa.JSON),sa.Column("metadata_json",sa.JSON),sa.Column("created_at",sa.DateTime(timezone=True)),sa.Column("updated_at",sa.DateTime(timezone=True)))
    op.create_index("ix_review_pending_reason","thesis_reviews",["user_id","tracked_call_id","review_type","review_status"])
def downgrade(): op.drop_table("thesis_reviews");op.drop_table("user_review_settings")
