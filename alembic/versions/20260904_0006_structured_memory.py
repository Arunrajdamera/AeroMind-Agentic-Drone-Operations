"""Add structured, provenance-backed operational memory."""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "20260904_0006"
down_revision = "20260903_0005"
branch_labels = None
depends_on = None


def _columns() -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns("memory_records")}


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    columns = _columns()
    additions = [
        (
            "memory_type",
            sa.Column(
                "memory_type", sa.String(64), server_default="SYSTEM_OBSERVATION", nullable=False
            ),
        ),
        ("scope", sa.Column("scope", sa.String(32), server_default="RUN", nullable=False)),
        ("mission_id", sa.Column("mission_id", sa.Uuid(), sa.ForeignKey("missions.id"))),
        ("agent_run_id", sa.Column("agent_run_id", sa.Uuid(), sa.ForeignKey("agent_runs.id"))),
        (
            "structured_data",
            sa.Column("structured_data", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        ),
        ("source", sa.Column("source", sa.String(128), server_default="legacy", nullable=False)),
        (
            "source_type",
            sa.Column(
                "source_type", sa.String(64), server_default="SYSTEM_OBSERVATION", nullable=False
            ),
        ),
        (
            "source_id",
            sa.Column("source_id", sa.String(128), server_default="legacy", nullable=False),
        ),
        ("confidence", sa.Column("confidence", sa.Float(), server_default="0.5", nullable=False)),
        ("importance", sa.Column("importance", sa.Float(), server_default="0.5", nullable=False)),
        ("status", sa.Column("status", sa.String(32), server_default="ACTIVE", nullable=False)),
        ("expires_at", sa.Column("expires_at", sa.DateTime(timezone=True))),
        ("content_hash", sa.Column("content_hash", sa.String(64))),
        ("embedding", sa.Column("embedding", Vector(8))),
        ("embedding_model", sa.Column("embedding_model", sa.String(128))),
    ]
    for name, column in additions:
        if name not in columns:
            op.add_column("memory_records", column)
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_memory_records_content_hash "
        "ON memory_records (content_hash) WHERE content_hash IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_memory_records_scope_status "
        "ON memory_records (scope, status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_memory_records_mission_status "
        "ON memory_records (mission_id, status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_memory_records_embedding_hnsw "
        "ON memory_records USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS ix_memory_records_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_memory_records_mission_status")
    op.execute("DROP INDEX IF EXISTS ix_memory_records_scope_status")
    op.execute("DROP INDEX IF EXISTS ix_memory_records_content_hash")
    # Preserve audited memory records and provenance, consistent with existing rollback policy.
