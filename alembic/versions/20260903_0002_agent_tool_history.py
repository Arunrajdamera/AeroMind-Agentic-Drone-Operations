"""Add Phase 4 agent/tool execution history fields."""

import sqlalchemy as sa
from alembic import op

revision = "20260903_0002"
down_revision = "20260903_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    agent_columns = {column["name"] for column in sa.inspect(bind).get_columns("agent_runs")}
    tool_columns = {column["name"] for column in sa.inspect(bind).get_columns("tool_executions")}
    for name, column in [
        (
            "execution_status",
            sa.Column("execution_status", sa.String(32), server_default="PLANNED", nullable=False),
        ),
        ("final_decision", sa.Column("final_decision", sa.String(64))),
        ("error", sa.Column("error", sa.Text())),
        (
            "payload",
            sa.Column("payload", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        ),
    ]:
        if name not in agent_columns:
            op.add_column("agent_runs", column)
    for name, column in [
        ("run_id", sa.Column("run_id", sa.Uuid())),
        (
            "payload",
            sa.Column("payload", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        ),
    ]:
        if name not in tool_columns:
            op.add_column("tool_executions", column)


def downgrade() -> None:
    # Fresh databases obtain these fields from the metadata-backed 0001 baseline.
    # Existing deployments retain history columns on downgrade to avoid destructive loss.
    pass
