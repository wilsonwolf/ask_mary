"""add_trials_table

Revision ID: a1b2c3d4e5f6
Revises: c5637630ca54
Create Date: 2026-02-08 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "c5637630ca54"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add trials table."""
    op.create_table(
        "trials",
        sa.Column("trial_id", sa.String(100), primary_key=True),
        sa.Column("trial_name", sa.String(200), nullable=False),
        sa.Column(
            "inclusion_criteria",
            postgresql.JSONB(),
            server_default="{}",
        ),
        sa.Column(
            "exclusion_criteria",
            postgresql.JSONB(),
            server_default="{}",
        ),
        sa.Column(
            "visit_templates",
            postgresql.JSONB(),
            server_default="{}",
        ),
        sa.Column("pi_name", sa.String(200)),
        sa.Column("coordinator_name", sa.String(200)),
        sa.Column("coordinator_phone", sa.String(20)),
        sa.Column("site_address", sa.String(300)),
        sa.Column("site_name", sa.String(200)),
        sa.Column("calendar_id", sa.String(200)),
        sa.Column("max_distance_km", sa.Float(), server_default="80.0"),
        sa.Column(
            "operating_hours",
            postgresql.JSONB(),
            server_default="{}",
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Remove trials table."""
    op.drop_table("trials")
