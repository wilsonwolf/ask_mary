"""Seed the database with demo data for end-to-end demo.

Creates trials, participants, enrollments, and events that exercise
every part of the Ask Mary pipeline: outreach → identity → screening →
scheduling → transport → handoff.

Usage:
    python -m scripts.seed_demo

All data is synthetic. The demo participant phone number is the real
number that ElevenLabs will call during the live demo.
"""

import asyncio
import logging
import uuid
from datetime import UTC, date, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config.settings import get_settings
from src.db.models import Base, Participant, ParticipantTrial, Trial
from src.shared.identity import generate_mary_id

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Demo Participant ---
# Identity verification: DOB year 1972, ZIP 97205
DEMO_PARTICIPANT = {
    "first_name": "Eleanor",
    "last_name": "Vasquez",
    "date_of_birth": date(1972, 6, 15),
    "phone": "+16505077348",
    "address_street": "2847 NW Thurman St",
    "address_city": "Portland",
    "address_state": "OR",
    "address_zip": "97205",
    "timezone": "America/Los_Angeles",
    "distance_to_site_km": 12.3,
    "preferred_channel": "voice",
    "best_time_to_reach": "morning",
    "language": "en",
}

# --- Additional Participants (dashboard realism) ---
EXTRA_PARTICIPANTS = [
    {
        "first_name": "Marcus",
        "last_name": "Chen",
        "date_of_birth": date(1958, 11, 2),
        "phone": "+15035559001",
        "address_street": "410 SE Hawthorne Blvd",
        "address_city": "Portland",
        "address_state": "OR",
        "address_zip": "97214",
        "timezone": "America/Los_Angeles",
        "distance_to_site_km": 8.1,
        "language": "en",
    },
    {
        "first_name": "Priya",
        "last_name": "Ramirez",
        "date_of_birth": date(1984, 3, 28),
        "phone": "+15035559002",
        "address_street": "1923 NE Broadway",
        "address_city": "Portland",
        "address_state": "OR",
        "address_zip": "97232",
        "timezone": "America/Los_Angeles",
        "distance_to_site_km": 6.5,
        "language": "en",
    },
    {
        "first_name": "Robert",
        "last_name": "Kim",
        "date_of_birth": date(1965, 9, 10),
        "phone": "+15035559003",
        "address_street": "7300 SW Beaverton-Hillsdale Hwy",
        "address_city": "Portland",
        "address_state": "OR",
        "address_zip": "97225",
        "timezone": "America/Los_Angeles",
        "distance_to_site_km": 14.7,
        "language": "en",
    },
]

# --- Trials ---
DIABETES_TRIAL = {
    "trial_id": "diabetes-study-a",
    "trial_name": "Diabetes Study A — Metformin XR Efficacy",
    "pi_name": "Dr. Sarah Chen",
    "coordinator_name": "Maria Rodriguez",
    "coordinator_phone": "+15035551234",
    "site_address": "3181 SW Sam Jackson Park Rd, Portland, OR 97239",
    "site_name": "OHSU Knight Clinical Research Center",
    "calendar_id": "diabetes-study-a@group.calendar.google.com",
    "max_distance_km": 80.0,
    "inclusion_criteria": {
        "min_age": 18,
        "max_age": 75,
        "diagnosis": "type_2_diabetes",
        "hba1c_min": 7.0,
        "hba1c_max": 10.5,
    },
    "exclusion_criteria": {
        "pregnant_or_nursing": True,
        "insulin_dependent": True,
        "egfr_below_30": True,
        "active_cancer_treatment": True,
    },
    "visit_templates": {
        "screening": {
            "duration_min": 90,
            "fasting": True,
            "prep": "No food or drink (except water) for 8 hours before.",
        },
        "baseline": {
            "duration_min": 120,
            "fasting": True,
            "prep": "No food or drink (except water) for 8 hours before. Bring current medications.",
        },
        "follow_up": {
            "duration_min": 60,
            "fasting": False,
            "prep": "No special preparation needed.",
        },
    },
    "operating_hours": {
        "monday": {"open": "08:00", "close": "17:00"},
        "tuesday": {"open": "08:00", "close": "17:00"},
        "wednesday": {"open": "08:00", "close": "17:00"},
        "thursday": {"open": "08:00", "close": "17:00"},
        "friday": {"open": "08:00", "close": "15:00"},
    },
}

CARDIOLOGY_TRIAL = {
    "trial_id": "cardio-prevention-b",
    "trial_name": "Cardiovascular Prevention Study B — PCSK9 Inhibitor",
    "pi_name": "Dr. James Okonkwo",
    "coordinator_name": "David Park",
    "coordinator_phone": "+15035555678",
    "site_address": "3181 SW Sam Jackson Park Rd, Portland, OR 97239",
    "site_name": "OHSU Heart and Vascular Institute",
    "calendar_id": "cardio-b@group.calendar.google.com",
    "max_distance_km": 100.0,
    "inclusion_criteria": {
        "min_age": 40,
        "max_age": 80,
        "diagnosis": "hyperlipidemia",
        "ldl_above": 130,
        "statin_intolerant": True,
    },
    "exclusion_criteria": {
        "active_liver_disease": True,
        "pregnant_or_nursing": True,
        "prior_pcsk9_use": True,
    },
    "visit_templates": {
        "screening": {"duration_min": 60, "fasting": True},
        "baseline": {"duration_min": 90, "fasting": True},
        "follow_up": {"duration_min": 45, "fasting": True},
    },
    "operating_hours": {
        "monday": {"open": "07:30", "close": "16:30"},
        "tuesday": {"open": "07:30", "close": "16:30"},
        "wednesday": {"open": "07:30", "close": "16:30"},
        "thursday": {"open": "07:30", "close": "16:30"},
        "friday": {"open": "07:30", "close": "14:00"},
    },
}


async def _seed_trial(session: AsyncSession, data: dict) -> Trial:
    """Insert a trial if it doesn't already exist.

    Args:
        session: Active database session.
        data: Trial field dict.

    Returns:
        Trial record (existing or new).
    """
    from sqlalchemy import select

    result = await session.execute(
        select(Trial).where(Trial.trial_id == data["trial_id"])
    )
    existing = result.scalar_one_or_none()
    if existing:
        logger.info("trial already exists: %s", data["trial_id"])
        return existing

    trial = Trial(
        created_at=datetime.now(UTC),
        active=True,
        **data,
    )
    session.add(trial)
    await session.flush()
    logger.info("created trial: %s", data["trial_id"])
    return trial


async def _seed_participant(
    session: AsyncSession,
    data: dict,
    pepper: str,
) -> Participant:
    """Insert a participant if they don't already exist.

    Args:
        session: Active database session.
        data: Participant field dict.
        pepper: MARY_ID_PEPPER for hashing.

    Returns:
        Participant record (existing or new).
    """
    from sqlalchemy import select

    mary_id = generate_mary_id(
        data["first_name"],
        data["last_name"],
        data["date_of_birth"],
        data["phone"],
        pepper,
    )

    result = await session.execute(
        select(Participant).where(Participant.mary_id == mary_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        logger.info("participant already exists: %s %s", data["first_name"], data["last_name"])
        return existing

    now = datetime.now(UTC)
    participant = Participant(
        participant_id=uuid.uuid4(),
        mary_id=mary_id,
        identity_status="unverified",
        dnc_flags={},
        contactability={},
        consent={},
        contactability_risk="none",
        outreach_attempt_count=0,
        created_at=now,
        updated_at=now,
        **data,
    )
    session.add(participant)
    await session.flush()
    logger.info(
        "created participant: %s %s (id=%s)",
        data["first_name"],
        data["last_name"],
        participant.participant_id,
    )
    return participant


async def _enroll_participant(
    session: AsyncSession,
    participant: Participant,
    trial: Trial,
) -> ParticipantTrial:
    """Enroll a participant in a trial if not already enrolled.

    Args:
        session: Active database session.
        participant: Participant record.
        trial: Trial record.

    Returns:
        ParticipantTrial junction record.
    """
    from sqlalchemy import select

    result = await session.execute(
        select(ParticipantTrial).where(
            ParticipantTrial.participant_id == participant.participant_id,
            ParticipantTrial.trial_id == trial.trial_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        logger.info(
            "already enrolled: %s in %s",
            participant.first_name,
            trial.trial_id,
        )
        return existing

    now = datetime.now(UTC)
    enrollment = ParticipantTrial(
        participant_trial_id=uuid.uuid4(),
        participant_id=participant.participant_id,
        trial_id=trial.trial_id,
        pipeline_status="new",
        enrollment_status="screening",
        eligibility_status="pending",
        screening_responses={},
        adversarial_recheck_done=False,
        created_at=now,
        updated_at=now,
    )
    session.add(enrollment)
    await session.flush()
    logger.info(
        "enrolled: %s in %s",
        participant.first_name,
        trial.trial_id,
    )
    return enrollment


async def seed_all(session: AsyncSession) -> dict:
    """Seed all demo data.

    Args:
        session: Active database session.

    Returns:
        Dict with created record counts and demo participant ID.
    """
    settings = get_settings()
    pepper = settings.mary_id_pepper

    # Seed trials
    diabetes = await _seed_trial(session, DIABETES_TRIAL)
    cardio = await _seed_trial(session, CARDIOLOGY_TRIAL)

    # Seed demo participant (the one that gets called)
    demo = await _seed_participant(session, DEMO_PARTICIPANT, pepper)

    # Enroll demo participant in diabetes trial
    await _enroll_participant(session, demo, diabetes)

    # Seed extra participants for dashboard realism
    extras = []
    for p_data in EXTRA_PARTICIPANTS:
        p = await _seed_participant(session, p_data, pepper)
        extras.append(p)

    # Marcus → diabetes trial (already screened, eligible)
    marcus_enrollment = await _enroll_participant(session, extras[0], diabetes)
    marcus_enrollment.pipeline_status = "scheduling"
    marcus_enrollment.eligibility_status = "eligible"
    marcus_enrollment.enrollment_status = "eligible"
    marcus_enrollment.screening_responses = {
        "min_age": {"answer": 66, "provenance": "ehr"},
        "max_age": {"answer": 66, "provenance": "ehr"},
        "diagnosis": {"answer": "type_2_diabetes", "provenance": "ehr"},
        "hba1c_min": {"answer": 8.2, "provenance": "ehr"},
        "hba1c_max": {"answer": 8.2, "provenance": "ehr"},
    }

    # Priya → cardio trial (new, not yet contacted)
    await _enroll_participant(session, extras[1], cardio)

    # Robert → diabetes trial (screening in progress)
    robert_enrollment = await _enroll_participant(session, extras[2], diabetes)
    robert_enrollment.pipeline_status = "screening"
    robert_enrollment.screening_responses = {
        "min_age": {"answer": 59, "provenance": "patient_stated"},
        "diagnosis": {"answer": "type_2_diabetes", "provenance": "patient_stated"},
    }

    logger.info("=== DEMO SEED COMPLETE ===")
    logger.info("Demo participant: %s %s", demo.first_name, demo.last_name)
    logger.info("Demo participant_id: %s", demo.participant_id)
    logger.info("Demo phone: %s", demo.phone)
    logger.info("Demo DOB year (for identity): %s", demo.date_of_birth.year)
    logger.info("Demo ZIP (for identity): %s", demo.address_zip)
    logger.info("Demo trial: %s", diabetes.trial_id)

    return {
        "trials": 2,
        "participants": 1 + len(extras),
        "enrollments": 4,
        "demo_participant_id": str(demo.participant_id),
        "demo_trial_id": diabetes.trial_id,
    }


async def main() -> None:
    """Run the seed script against the configured database."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)

    # Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        result = await seed_all(session)
        await session.commit()
        logger.info("Seed result: %s", result)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
