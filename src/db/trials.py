"""Trial CRUD operations for the trials table."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Trial


async def create_trial(
    session: AsyncSession,
    *,
    trial_id: str | None = None,
    trial_name: str,
    pi_name: str | None = None,
    coordinator_name: str | None = None,
    coordinator_phone: str | None = None,
    site_address: str | None = None,
    site_name: str | None = None,
    calendar_id: str | None = None,
    max_distance_km: float = 80.0,
    inclusion_criteria: dict | None = None,
    exclusion_criteria: dict | None = None,
    visit_templates: dict | None = None,
    operating_hours: dict | None = None,
) -> Trial:
    """Create a new clinical trial record.

    Args:
        session: Active database session.
        trial_id: Trial string identifier (auto-generated if omitted).
        trial_name: Human-readable trial name.
        pi_name: Principal investigator name.
        coordinator_name: Study coordinator name.
        coordinator_phone: Coordinator phone number.
        site_address: Trial site address.
        site_name: Trial site name.
        calendar_id: Google Calendar ID for scheduling.
        max_distance_km: Maximum participant distance to site.
        inclusion_criteria: JSONB inclusion criteria.
        exclusion_criteria: JSONB exclusion criteria.
        visit_templates: JSONB visit schedule templates.
        operating_hours: JSONB operating hours.

    Returns:
        Created Trial record.
    """
    trial = Trial(
        trial_id=trial_id or str(uuid.uuid4()),
        trial_name=trial_name,
        pi_name=pi_name,
        coordinator_name=coordinator_name,
        coordinator_phone=coordinator_phone,
        site_address=site_address,
        site_name=site_name,
        calendar_id=calendar_id,
        max_distance_km=max_distance_km,
        inclusion_criteria=inclusion_criteria or {},
        exclusion_criteria=exclusion_criteria or {},
        visit_templates=visit_templates or {},
        operating_hours=operating_hours or {},
        active=True,
        created_at=datetime.now(UTC),
    )
    session.add(trial)
    await session.flush()
    return trial


async def get_trial(
    session: AsyncSession,
    trial_id: str,
) -> Trial | None:
    """Look up a trial by string ID.

    Args:
        session: Active database session.
        trial_id: Trial string identifier.

    Returns:
        Trial if found, else None.
    """
    result = await session.execute(select(Trial).where(Trial.trial_id == trial_id))
    return result.scalar_one_or_none()


async def get_trial_criteria(
    session: AsyncSession,
    trial_id: str,
) -> dict:
    """Get inclusion and exclusion criteria for a trial.

    Args:
        session: Active database session.
        trial_id: Trial string identifier.

    Returns:
        Dict with 'inclusion' and 'exclusion' keys.

    Raises:
        ValueError: If trial not found.
    """
    trial = await get_trial(session, trial_id)
    if trial is None:
        raise ValueError(f"Trial {trial_id} not found")
    return {
        "inclusion": trial.inclusion_criteria or {},
        "exclusion": trial.exclusion_criteria or {},
    }


async def list_active_trials(
    session: AsyncSession,
) -> list[Trial]:
    """List all active trials.

    Args:
        session: Active database session.

    Returns:
        List of active Trial records.
    """
    result = await session.execute(select(Trial).where(Trial.active.is_(True)))
    return list(result.scalars().all())


async def seed_diabetes_study_a(
    session: AsyncSession,
) -> Trial:
    """Seed the Diabetes Study A demo trial.

    Args:
        session: Active database session.

    Returns:
        Created Trial record for Diabetes Study A.
    """
    return await create_trial(
        session,
        trial_id="diabetes-study-a",
        trial_name="Diabetes Study A",
        pi_name="Dr. Sarah Chen",
        coordinator_name="Maria Rodriguez",
        coordinator_phone="+15035551234",
        site_address="3181 SW Sam Jackson Park Rd, Portland, OR 97239",
        site_name="OHSU Knight Clinical Research Center",
        calendar_id="diabetes-study-a@group.calendar.google.com",
        max_distance_km=80.0,
        inclusion_criteria={
            "min_age": 18,
            "max_age": 75,
            "diagnosis": "type_2_diabetes",
            "hba1c_min": 7.0,
            "hba1c_max": 10.5,
        },
        exclusion_criteria={
            "pregnant_or_nursing": True,
            "insulin_dependent": True,
            "egfr_below_30": True,
            "active_cancer_treatment": True,
        },
        visit_templates={
            "screening": {"duration_min": 90, "fasting": True},
            "baseline": {"duration_min": 120, "fasting": True},
            "follow_up": {"duration_min": 60, "fasting": False},
        },
        operating_hours={
            "monday": {"open": "08:00", "close": "17:00"},
            "tuesday": {"open": "08:00", "close": "17:00"},
            "wednesday": {"open": "08:00", "close": "17:00"},
            "thursday": {"open": "08:00", "close": "17:00"},
            "friday": {"open": "08:00", "close": "15:00"},
        },
    )
