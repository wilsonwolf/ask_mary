"""add_twilio_call_sid

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-09 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add twilio_call_sid column to conversations table."""
    op.add_column(
        "conversations",
        sa.Column("twilio_call_sid", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    """Remove twilio_call_sid column from conversations table."""
    op.drop_column("conversations", "twilio_call_sid")
