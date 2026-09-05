"""Add Phase 4 approval tool metadata."""

import sqlalchemy as sa
from alembic import op

revision = "20260903_0003"
down_revision = "20260903_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("approvals")}
    if "tool_name" not in columns:
        op.add_column("approvals", sa.Column("tool_name", sa.String(128)))
    if "payload" not in columns:
        op.add_column(
            "approvals",
            sa.Column("payload", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        )


def downgrade() -> None:
    # Preserve approval evidence rather than destructively deleting it during rollback.
    pass
