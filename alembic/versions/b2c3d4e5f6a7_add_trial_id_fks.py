"""add_trial_id_fks

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-08 14:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add trial_id foreign keys to referencing tables."""
    op.create_foreign_key(
        "fk_participant_trials_trial_id",
        "participant_trials",
        "trials",
        ["trial_id"],
        ["trial_id"],
    )
    op.create_foreign_key(
        "fk_appointments_trial_id",
        "appointments",
        "trials",
        ["trial_id"],
        ["trial_id"],
    )
    op.create_foreign_key(
        "fk_conversations_trial_id",
        "conversations",
        "trials",
        ["trial_id"],
        ["trial_id"],
    )
    op.create_foreign_key(
        "fk_events_trial_id",
        "events",
        "trials",
        ["trial_id"],
        ["trial_id"],
    )
    op.create_foreign_key(
        "fk_handoff_queue_trial_id",
        "handoff_queue",
        "trials",
        ["trial_id"],
        ["trial_id"],
    )


def downgrade() -> None:
    """Remove trial_id foreign keys."""
    op.drop_constraint(
        "fk_handoff_queue_trial_id",
        "handoff_queue",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_events_trial_id",
        "events",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_conversations_trial_id",
        "conversations",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_appointments_trial_id",
        "appointments",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_participant_trials_trial_id",
        "participant_trials",
        type_="foreignkey",
    )
