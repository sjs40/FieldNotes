"""Add analyst-owned company workspaces and active-company preferences."""

from alembic import op
import sqlalchemy as sa


revision = "07a8b9c0d1e2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_workspaces",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("security_id", sa.String(length=36), sa.ForeignKey("securities.id"), nullable=False),
        sa.Column("company_description", sa.Text(), nullable=True),
        sa.Column("business_model", sa.Text(), nullable=True),
        sa.Column("is_followed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "security_id", name="uq_company_workspace_user_security"),
    )
    op.create_index("ix_company_workspaces_user_id", "company_workspaces", ["user_id"])
    op.create_index("ix_company_workspaces_security_id", "company_workspaces", ["security_id"])
    op.create_table(
        "user_workspace_preferences",
        sa.Column("user_id", sa.String(length=36), primary_key=True),
        sa.Column("active_security_id", sa.String(length=36), sa.ForeignKey("securities.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("user_workspace_preferences")
    op.drop_index("ix_company_workspaces_security_id", table_name="company_workspaces")
    op.drop_index("ix_company_workspaces_user_id", table_name="company_workspaces")
    op.drop_table("company_workspaces")
