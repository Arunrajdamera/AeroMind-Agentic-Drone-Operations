"""Add pgvector-backed document chunks for Phase 5A knowledge retrieval."""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "20260903_0005"
down_revision = "20260903_0004"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    document_columns = _columns("documents")
    for name, column in [
        ("source", sa.Column("source", sa.String(512), server_default="local", nullable=False)),
        ("external_reference", sa.Column("external_reference", sa.String(512))),
        ("content_hash", sa.Column("content_hash", sa.String(64))),
        (
            "metadata",
            sa.Column("metadata", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        ),
    ]:
        if name not in document_columns:
            op.add_column("documents", column)
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_documents_content_hash "
        "ON documents (content_hash) WHERE content_hash IS NOT NULL"
    )

    chunk_columns = _columns("document_chunks")
    for name, column in [
        ("chunk_index", sa.Column("chunk_index", sa.Integer(), server_default="0", nullable=False)),
        (
            "metadata",
            sa.Column("metadata", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        ),
        ("embedding", sa.Column("embedding", Vector(8))),
        ("embedding_model", sa.Column("embedding_model", sa.String(128))),
    ]:
        if name not in chunk_columns:
            op.add_column("document_chunks", column)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_chunks_document_chunk "
        "ON document_chunks (document_id, chunk_index)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw "
        "ON document_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_document_chunk")
    op.execute("DROP INDEX IF EXISTS ix_documents_content_hash")
    # Retain persisted evidence, matching the existing non-destructive history policy.
