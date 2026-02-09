"""HTTP routes for Cloud Tasks worker callbacks.

Cloud Tasks sends POST requests to these endpoints when deferred
jobs are due. Each route extracts the payload, delegates to the
appropriate worker handler, and returns the result.

Architecture note: lives in api/ because it's an HTTP entry point.
Imports from workers/ which imports from services/db/shared.
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_async_session
from src.workers.reminders import handle_reminder_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workers", tags=["workers"])


class ReminderTaskPayload(BaseModel):
    """Cloud Tasks reminder job payload.

    Attributes:
        participant_id: Participant UUID string.
        template_id: Task template identifier.
        channel: Delivery channel (sms, voice, system).
        idempotency_key: Dedup key for retry safety.
        appointment_id: Optional appointment UUID string.
    """

    participant_id: str
    template_id: str
    channel: str = "system"
    idempotency_key: str | None = None
    appointment_id: str | None = None


@router.post("/reminders")
async def worker_reminders(
    payload: ReminderTaskPayload,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Handle Cloud Tasks reminder callback.

    Args:
        payload: Task payload from Cloud Tasks.
        session: Injected database session.

    Returns:
        Processing result from handler.
    """
    logger.info(
        "worker_reminder_received",
        extra={"template_id": payload.template_id},
    )
    return await handle_reminder_task(
        session, payload.model_dump(),
    )
