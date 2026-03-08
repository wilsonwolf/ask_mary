"""Tests for Cloud Tasks reminder worker routing."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from src.shared.types import RideStatus
from src.workers.reminders import (
    _handle_transport_reconfirm,
    handle_reminder_task,
)


class TestHandleReminderTask:
    """Cloud Tasks worker routing by template_id."""

    async def test_dedup_skips_existing_key(self) -> None:
        """Duplicate idempotency_key returns already_processed."""
        mock_session = AsyncMock()
        payload = {
            "idempotency_key": "key-1",
            "participant_id": str(uuid.uuid4()),
            "template_id": "confirmation_check",
        }

        with patch(
            "src.workers.reminders._is_duplicate",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await handle_reminder_task(mock_session, payload)

        assert result["processed"] is False
        assert result["reason"] == "duplicate"

    async def test_confirmation_check_routes(self) -> None:
        """confirmation_check template routes to its handler."""
        mock_session = AsyncMock()
        payload = {
            "idempotency_key": "key-2",
            "participant_id": str(uuid.uuid4()),
            "appointment_id": str(uuid.uuid4()),
            "template_id": "confirmation_check",
        }
        mock_handler = AsyncMock(return_value={"status": "confirmed"})

        with (
            patch(
                "src.workers.reminders._is_duplicate",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch.dict(
                "src.workers.reminders.TASK_HANDLERS",
                {"confirmation_check": mock_handler},
            ),
        ):
            result = await handle_reminder_task(mock_session, payload)

        assert result["processed"] is True
        assert result["status"] == "confirmed"
        mock_handler.assert_called_once_with(mock_session, payload)

    async def test_slot_release_routes(self) -> None:
        """slot_release template routes to its handler."""
        mock_session = AsyncMock()
        payload = {
            "idempotency_key": "key-3",
            "participant_id": str(uuid.uuid4()),
            "appointment_id": str(uuid.uuid4()),
            "template_id": "slot_release",
        }
        mock_handler = AsyncMock(return_value={"released": True})

        with (
            patch(
                "src.workers.reminders._is_duplicate",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch.dict(
                "src.workers.reminders.TASK_HANDLERS",
                {"slot_release": mock_handler},
            ),
        ):
            result = await handle_reminder_task(mock_session, payload)

        assert result["processed"] is True
        assert result["released"] is True
        mock_handler.assert_called_once()

    async def test_reminder_routes(self) -> None:
        """Generic reminder template routes to reminder handler."""
        mock_session = AsyncMock()
        payload = {
            "idempotency_key": "key-4",
            "participant_id": str(uuid.uuid4()),
            "template_id": "appointment_reminder",
            "channel": "sms",
        }
        mock_handler = AsyncMock(return_value={"sent": True})

        with (
            patch(
                "src.workers.reminders._is_duplicate",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch.dict(
                "src.workers.reminders.TASK_HANDLERS",
                {"appointment_reminder": mock_handler},
            ),
        ):
            result = await handle_reminder_task(mock_session, payload)

        assert result["processed"] is True
        assert result["sent"] is True
        mock_handler.assert_called_once()

    async def test_unknown_template_returns_error(self) -> None:
        """Unknown template_id returns error without crashing."""
        mock_session = AsyncMock()
        payload = {
            "idempotency_key": "key-5",
            "participant_id": str(uuid.uuid4()),
            "template_id": "nonexistent_template",
        }

        with patch(
            "src.workers.reminders._is_duplicate",
            new_callable=AsyncMock,
            return_value=False,
        ):
            result = await handle_reminder_task(mock_session, payload)

        assert result["processed"] is False
        assert "unknown_template" in result["reason"]

    async def test_missing_key_skips_dedup(self) -> None:
        """Missing idempotency_key skips dedup and processes."""
        mock_session = AsyncMock()
        payload = {
            "participant_id": str(uuid.uuid4()),
            "template_id": "confirmation_check",
            "appointment_id": str(uuid.uuid4()),
        }
        mock_handler = AsyncMock(return_value={"status": "confirmed"})

        with patch.dict(
            "src.workers.reminders.TASK_HANDLERS",
            {"confirmation_check": mock_handler},
        ):
            result = await handle_reminder_task(mock_session, payload)

        assert result["processed"] is True

    async def test_adversarial_recheck_handler(self) -> None:
        """adversarial_recheck routes to handler and returns processed."""
        mock_session = AsyncMock()
        participant_id = str(uuid.uuid4())
        payload = {
            "idempotency_key": "key-adv-1",
            "participant_id": participant_id,
            "trial_id": "trial-42",
            "template_id": "adversarial_recheck",
        }

        mock_deception_result = {"deception_detected": False}

        with (
            patch(
                "src.workers.reminders._is_duplicate",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "src.agents.adversarial.run_adversarial_rescreen",
                new_callable=AsyncMock,
                return_value=mock_deception_result,
            ) as mock_rescreen,
        ):
            result = await handle_reminder_task(mock_session, payload)

        assert result["processed"] is True
        mock_rescreen.assert_awaited_once()


class TestHandleTransportReconfirm:
    """Transport ride reconfirmation handler."""

    async def test_processes_active_ride(self) -> None:
        """Logs event for a ride that is not cancelled or failed."""
        mock_session = AsyncMock()
        ride_id = uuid.uuid4()
        participant_id = uuid.uuid4()
        ride = MagicMock()
        ride.ride_id = ride_id
        ride.status = RideStatus.CONFIRMED

        payload = {
            "ride_id": str(ride_id),
            "participant_id": str(participant_id),
            "idempotency_key": f"transport-reconfirm-24h-{ride_id}",
        }

        with (
            patch(
                "src.workers.reminders.get_ride",
                new_callable=AsyncMock,
                return_value=ride,
            ),
            patch(
                "src.workers.reminders.log_event",
                new_callable=AsyncMock,
            ) as mock_log,
        ):
            result = await _handle_transport_reconfirm(
                mock_session, payload,
            )

        assert result["ride_id"] == str(ride_id)
        mock_log.assert_awaited_once()

    async def test_skips_cancelled_ride(self) -> None:
        """Does not log event for a cancelled ride."""
        mock_session = AsyncMock()
        ride_id = uuid.uuid4()
        ride = MagicMock()
        ride.ride_id = ride_id
        ride.status = RideStatus.CANCELLED

        payload = {
            "ride_id": str(ride_id),
            "participant_id": str(uuid.uuid4()),
            "idempotency_key": f"transport-reconfirm-2h-{ride_id}",
        }

        with patch(
            "src.workers.reminders.get_ride",
            new_callable=AsyncMock,
            return_value=ride,
        ):
            result = await _handle_transport_reconfirm(
                mock_session, payload,
            )

        assert result["skipped"] is True
        assert result["reason"] == "ride_cancelled_or_failed"

    async def test_skips_failed_ride(self) -> None:
        """Does not log event for a failed ride."""
        mock_session = AsyncMock()
        ride_id = uuid.uuid4()
        ride = MagicMock()
        ride.ride_id = ride_id
        ride.status = RideStatus.FAILED

        payload = {
            "ride_id": str(ride_id),
            "participant_id": str(uuid.uuid4()),
            "idempotency_key": f"transport-reconfirm-2h-{ride_id}",
        }

        with patch(
            "src.workers.reminders.get_ride",
            new_callable=AsyncMock,
            return_value=ride,
        ):
            result = await _handle_transport_reconfirm(
                mock_session, payload,
            )

        assert result["skipped"] is True

    async def test_ride_not_found(self) -> None:
        """Returns not_found when ride does not exist."""
        mock_session = AsyncMock()
        ride_id = uuid.uuid4()

        payload = {
            "ride_id": str(ride_id),
            "participant_id": str(uuid.uuid4()),
        }

        with patch(
            "src.workers.reminders.get_ride",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await _handle_transport_reconfirm(
                mock_session, payload,
            )

        assert result["ride_id"] == str(ride_id)
        assert result["status"] == "not_found"

    async def test_routes_via_task_handlers(self) -> None:
        """Both reconfirm template_ids route to the handler."""
        mock_session = AsyncMock()
        ride_id = uuid.uuid4()
        ride = MagicMock()
        ride.ride_id = ride_id
        ride.status = RideStatus.CONFIRMED

        for template_id in (
            "transport_reconfirm_24h",
            "transport_reconfirm_2h",
        ):
            payload = {
                "idempotency_key": f"key-{template_id}",
                "participant_id": str(uuid.uuid4()),
                "ride_id": str(ride_id),
                "template_id": template_id,
            }

            with (
                patch(
                    "src.workers.reminders._is_duplicate",
                    new_callable=AsyncMock,
                    return_value=False,
                ),
                patch(
                    "src.workers.reminders.get_ride",
                    new_callable=AsyncMock,
                    return_value=ride,
                ),
                patch(
                    "src.workers.reminders.log_event",
                    new_callable=AsyncMock,
                ),
            ):
                result = await handle_reminder_task(
                    mock_session, payload,
                )

            assert result["processed"] is True

    async def test_outreach_retry_routes(self) -> None:
        """outreach_retry template routes to its handler."""
        mock_session = AsyncMock()
        participant_id = str(uuid.uuid4())
        payload = {
            "idempotency_key": "key-retry-1",
            "participant_id": participant_id,
            "trial_id": "trial-99",
            "template_id": "outreach_retry",
            "channel": "voice",
            "attempt_number": 1,
        }
        mock_handler = AsyncMock(
            return_value={"attempt": 1},
        )

        with (
            patch(
                "src.workers.reminders._is_duplicate",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch.dict(
                "src.workers.reminders.TASK_HANDLERS",
                {"outreach_retry": mock_handler},
            ),
        ):
            result = await handle_reminder_task(mock_session, payload)

        assert result["processed"] is True
        assert result["attempt"] == 1
        mock_handler.assert_called_once()


class TestHandleOutreachRetry:
    """Outreach retry worker handler tests."""

    async def test_voice_retry_calls_outbound(self) -> None:
        """Voice retry calls initiate_outbound_call."""
        from src.workers.reminders import _handle_outreach_retry

        mock_session = AsyncMock()
        participant_id = str(uuid.uuid4())
        payload = {
            "participant_id": participant_id,
            "trial_id": "trial-55",
            "channel": "voice",
            "attempt_number": 1,
        }

        mock_call_result = AsyncMock()
        mock_call_result.initiated = True

        with (
            patch(
                "src.agents.outreach.initiate_outbound_call",
                new_callable=AsyncMock,
                return_value=mock_call_result,
            ) as mock_call,
            patch(
                "src.agents.outreach.schedule_next_outreach",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result = await _handle_outreach_retry(
                mock_session, payload,
            )

        assert result["attempt"] == 1
        mock_call.assert_awaited_once()

    async def test_sms_retry_renders_template(self) -> None:
        """SMS retry renders outreach_nudge template and logs event."""
        from src.workers.reminders import _handle_outreach_retry

        mock_session = AsyncMock()
        participant_id = str(uuid.uuid4())
        payload = {
            "participant_id": participant_id,
            "trial_id": "trial-55",
            "channel": "sms",
            "attempt_number": 0,
        }

        with (
            patch(
                "src.shared.comms.render_template",
                return_value="Hello, follow up.",
            ) as mock_render,
            patch(
                "src.workers.reminders.log_event",
                new_callable=AsyncMock,
            ),
            patch(
                "src.agents.outreach.schedule_next_outreach",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result = await _handle_outreach_retry(
                mock_session, payload,
            )

        assert result["attempt"] == 0
        mock_render.assert_called_once_with("outreach_nudge")

    async def test_schedules_next_attempt(self) -> None:
        """After processing, schedules the next outreach attempt."""
        from src.workers.reminders import _handle_outreach_retry

        mock_session = AsyncMock()
        participant_id = str(uuid.uuid4())
        payload = {
            "participant_id": participant_id,
            "trial_id": "trial-55",
            "channel": "sms",
            "attempt_number": 0,
        }

        with (
            patch(
                "src.shared.comms.render_template",
                return_value="Hello.",
            ),
            patch(
                "src.workers.reminders.log_event",
                new_callable=AsyncMock,
            ),
            patch(
                "src.agents.outreach.schedule_next_outreach",
                new_callable=AsyncMock,
                return_value=None,
            ) as mock_schedule,
        ):
            await _handle_outreach_retry(mock_session, payload)

        mock_schedule.assert_awaited_once()
        call_kwargs = mock_schedule.call_args.kwargs
        assert call_kwargs["current_attempt"] == 1
