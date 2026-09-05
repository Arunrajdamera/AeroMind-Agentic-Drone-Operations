"""Add persisted expiry deadline to approvals."""

import sqlalchemy as sa
from alembic import op

revision = "20260903_0004"
down_revision = "20260903_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("approvals")}
    if "expires_at" not in columns:
        op.add_column("approvals", sa.Column("expires_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    pass
