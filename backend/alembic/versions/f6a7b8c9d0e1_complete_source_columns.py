"""Add source metadata columns that were introduced after the initial inbox migration."""

from alembic import op
import sqlalchemy as sa


revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("author", sa.String(length=255), nullable=True))
    op.add_column("sources", sa.Column("publisher", sa.String(length=255), nullable=True))
    op.add_column("sources", sa.Column("sender_name", sa.String(length=255), nullable=True))
    op.add_column("sources", sa.Column("sender_email", sa.String(length=320), nullable=True))
    op.add_column("sources", sa.Column("subject", sa.String(length=500), nullable=True))
    op.add_column("sources", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sources", sa.Column("received_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sources", sa.Column("language", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("sources", "language")
    op.drop_column("sources", "received_at")
    op.drop_column("sources", "published_at")
    op.drop_column("sources", "subject")
    op.drop_column("sources", "sender_email")
    op.drop_column("sources", "sender_name")
    op.drop_column("sources", "publisher")
    op.drop_column("sources", "author")
