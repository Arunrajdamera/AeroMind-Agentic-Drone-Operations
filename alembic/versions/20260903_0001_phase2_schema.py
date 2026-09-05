"""Create Phase 2 simulation foundation tables."""

from alembic import op

import aeromind.models.domain  # noqa: F401
from aeromind.db.base import Base

revision = "20260903_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(op.get_bind())
