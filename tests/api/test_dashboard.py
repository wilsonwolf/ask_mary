"""Tests for dashboard REST API endpoints."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.app import create_app
from src.db.session import get_async_session
from src.shared.types import (
    AppointmentStatus,
    Channel,
    ConversationStatus,
    Direction,
    HandoffReason,
    HandoffSeverity,
    HandoffStatus,
    IdentityStatus,
)


@pytest.fixture
def app():
    """Create test FastAPI app."""
    return create_app()


def _mock_participant(pid: uuid.UUID | None = None) -> MagicMock:
    """Build a mock Participant ORM object."""
    p = MagicMock()
    p.participant_id = pid or uuid.uuid4()
    p.first_name = "Jane"
    p.last_name = "Tester"
    p.phone = "+15550001234"
    p.identity_status = IdentityStatus.VERIFIED
    p.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    p.trials = []
    return p


def _mock_appointment() -> MagicMock:
    """Build a mock Appointment ORM object."""
    a = MagicMock()
    a.appointment_id = uuid.uuid4()
    a.participant_id = uuid.uuid4()
    a.trial_id = "diabetes-study-a"
    a.visit_type = "screening"
    a.scheduled_at = datetime(2026, 2, 10, 9, 0, tzinfo=UTC)
    a.status = AppointmentStatus.BOOKED
    a.site_name = "City Clinic"
    return a


def _mock_handoff() -> MagicMock:
    """Build a mock HandoffQueue ORM object."""
    h = MagicMock()
    h.handoff_id = uuid.uuid4()
    h.participant_id = uuid.uuid4()
    h.reason = HandoffReason.MEDICAL_ADVICE
    h.severity = HandoffSeverity.HANDOFF_NOW
    h.status = HandoffStatus.OPEN
    h.summary = "Participant reports chest pain"
    h.created_at = datetime(2026, 2, 8, tzinfo=UTC)
    return h


def _mock_conversation() -> MagicMock:
    """Build a mock Conversation ORM object."""
    c = MagicMock()
    c.conversation_id = uuid.uuid4()
    c.participant_id = uuid.uuid4()
    c.channel = Channel.VOICE
    c.direction = Direction.OUTBOUND
    c.status = ConversationStatus.COMPLETED
    c.started_at = datetime(2026, 2, 8, 10, 0, tzinfo=UTC)
    return c


def _mock_event() -> MagicMock:
    """Build a mock Event ORM object."""
    e = MagicMock()
    e.event_id = uuid.uuid4()
    e.participant_id = uuid.uuid4()
    e.event_type = "IDENTITY_VERIFIED"
    e.trial_id = "diabetes-study-a"
    e.payload = {}
    e.created_at = datetime(2026, 2, 8, 10, 30, tzinfo=UTC)
    return e


def _fake_session(execute_result: MagicMock) -> AsyncMock:
    """Build a fake AsyncSession that returns pre-configured results.

    Args:
        execute_result: Mock result to return from execute().

    Returns:
        AsyncMock session.
    """
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=execute_result)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


def _override_session(mock_session: AsyncMock):
    """Create a dependency override for get_async_session.

    Args:
        mock_session: The mock session to yield.

    Returns:
        Async generator function for FastAPI dependency override.
    """

    async def _override() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    return _override


class TestListParticipants:
    """GET /api/participants endpoint."""

    async def test_returns_participant_list(self, app) -> None:
        """Returns a list of participants."""
        mock_p = _mock_participant()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_p]

        session = _fake_session(mock_result)
        app.dependency_overrides[get_async_session] = _override_session(session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.get("/api/participants")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["first_name"] == "Jane"
        finally:
            app.dependency_overrides.clear()


class TestListAppointments:
    """GET /api/appointments endpoint."""

    async def test_returns_appointment_list(self, app) -> None:
        """Returns a list of appointments."""
        mock_a = _mock_appointment()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_a]

        session = _fake_session(mock_result)
        app.dependency_overrides[get_async_session] = _override_session(session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.get("/api/appointments")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["trial_id"] == "diabetes-study-a"
        finally:
            app.dependency_overrides.clear()


class TestHandoffQueue:
    """GET /api/handoff-queue endpoint."""

    async def test_returns_open_handoffs(self, app) -> None:
        """Returns active handoff tickets."""
        mock_h = _mock_handoff()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_h]

        session = _fake_session(mock_result)
        app.dependency_overrides[get_async_session] = _override_session(session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.get("/api/handoff-queue")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["severity"] == HandoffSeverity.HANDOFF_NOW
        finally:
            app.dependency_overrides.clear()


class TestConversations:
    """GET /api/conversations endpoint."""

    async def test_returns_recent_conversations(self, app) -> None:
        """Returns recent conversations."""
        mock_c = _mock_conversation()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_c]

        session = _fake_session(mock_result)
        app.dependency_overrides[get_async_session] = _override_session(session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.get("/api/conversations")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["channel"] == Channel.VOICE
        finally:
            app.dependency_overrides.clear()


class TestEvents:
    """GET /api/events endpoint."""

    async def test_returns_paginated_events(self, app) -> None:
        """Returns paginated event feed."""
        mock_e = _mock_event()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_e]

        session = _fake_session(mock_result)
        app.dependency_overrides[get_async_session] = _override_session(session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.get("/api/events")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["event_type"] == "IDENTITY_VERIFIED"
        finally:
            app.dependency_overrides.clear()


class TestAnalyticsSummary:
    """GET /api/analytics/summary endpoint."""

    async def test_returns_aggregate_counts(self, app) -> None:
        """Returns participant, appointment, handoff counts."""
        mock_count = MagicMock()
        mock_count.scalar.return_value = 42

        session = _fake_session(mock_count)
        app.dependency_overrides[get_async_session] = _override_session(session)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.get("/api/analytics/summary")

            assert response.status_code == 200
            data = response.json()
            assert data["total_participants"] == 42
        finally:
            app.dependency_overrides.clear()

    async def test_returns_all_three_integer_fields(self, app) -> None:
        """Response contains all three expected keys with integer values."""
        participants_result = MagicMock()
        participants_result.scalar.return_value = 10

        appointments_result = MagicMock()
        appointments_result.scalar.return_value = 5

        handoffs_result = MagicMock()
        handoffs_result.scalar.return_value = 2

        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock(
            side_effect=[
                participants_result,
                appointments_result,
                handoffs_result,
            ],
        )

        app.dependency_overrides[get_async_session] = _override_session(
            session,
        )

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.get("/api/analytics/summary")

            assert response.status_code == 200
            data = response.json()
            assert data["total_participants"] == 10
            assert data["total_appointments"] == 5
            assert data["open_handoffs"] == 2
            assert isinstance(data["total_participants"], int)
            assert isinstance(data["total_appointments"], int)
            assert isinstance(data["open_handoffs"], int)
        finally:
            app.dependency_overrides.clear()

    async def test_returns_zero_when_no_records(self, app) -> None:
        """Returns zero for all counts when database has no records."""
        mock_count = MagicMock()
        mock_count.scalar.return_value = None

        session = _fake_session(mock_count)
        app.dependency_overrides[get_async_session] = _override_session(
            session,
        )

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.get("/api/analytics/summary")

            assert response.status_code == 200
            data = response.json()
            assert data["total_participants"] == 0
            assert data["total_appointments"] == 0
            assert data["open_handoffs"] == 0
        finally:
            app.dependency_overrides.clear()


class TestDemoStartCall:
    """POST /api/demo/start-call endpoint."""

    async def test_calls_elevenlabs_and_returns_result(self, app) -> None:
        """Demo endpoint looks up participant and calls ElevenLabs."""
        pid = uuid.uuid4()
        mock_p = _mock_participant(pid)
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_p

        session = _fake_session(mock_result)
        app.dependency_overrides[get_async_session] = _override_session(session)

        elevenlabs_response = {
            "status": "initiated",
            "conversation_id": "conv-123",
            "participant_id": str(pid),
            "trial_id": "diabetes-study-a",
        }

        try:
            with (
                patch(
                    "src.api.dashboard._call_elevenlabs",
                    new_callable=AsyncMock,
                    return_value=elevenlabs_response,
                ),
                patch(
                    "src.db.events.log_event",
                    new_callable=AsyncMock,
                ),
            ):
                transport = ASGITransport(app=app)
                async with AsyncClient(
                    transport=transport,
                    base_url="http://test",
                ) as client:
                    response = await client.post(
                        "/api/demo/start-call",
                        json={
                            "participant_id": str(pid),
                            "trial_id": "diabetes-study-a",
                        },
                    )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "initiated"
            assert data["conversation_id"] == "conv-123"
        finally:
            app.dependency_overrides.clear()


class TestDemoConfig:
    """GET /api/demo/config endpoint."""

    async def test_returns_demo_participant(self, app) -> None:
        """Config endpoint returns demo participant info."""
        pid = uuid.uuid4()
        mock_p = _mock_participant(pid)
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_p

        session = _fake_session(mock_result)
        app.dependency_overrides[get_async_session] = _override_session(session)

        try:
            with patch(
                "src.config.settings.get_settings",
                return_value=MagicMock(
                    demo_participant_phone="+15550001234",
                    demo_trial_id="diabetes-study-a",
                ),
            ):
                transport = ASGITransport(app=app)
                async with AsyncClient(
                    transport=transport,
                    base_url="http://test",
                ) as client:
                    response = await client.get("/api/demo/config")

            assert response.status_code == 200
            data = response.json()
            assert data["participant_id"] == str(pid)
            assert data["trial_id"] == "diabetes-study-a"
            assert data["participant_name"] == "Jane Tester"
        finally:
            app.dependency_overrides.clear()

    async def test_falls_back_to_trial_lookup_when_no_phone(self, app) -> None:
        """Config endpoint queries by trial when phone not set."""
        mock_participant = MagicMock()
        mock_participant.participant_id = uuid.uuid4()
        mock_participant.first_name = "Eleanor"
        mock_participant.last_name = "Vasquez"
        mock_participant.phone = "+15551234567"

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_participant
        session = _fake_session(mock_result)
        app.dependency_overrides[get_async_session] = _override_session(session)

        try:
            with patch(
                "src.config.settings.get_settings",
                return_value=MagicMock(
                    demo_participant_phone="",
                    demo_trial_id="diabetes-study-a",
                ),
            ):
                transport = ASGITransport(app=app)
                async with AsyncClient(
                    transport=transport,
                    base_url="http://test",
                ) as client:
                    response = await client.get("/api/demo/config")

            assert response.status_code == 200
            data = response.json()
            assert data["participant_name"] == "Eleanor Vasquez"
            assert data["trial_id"] == "diabetes-study-a"
        finally:
            app.dependency_overrides.clear()

    async def test_returns_error_when_participant_not_found(self, app) -> None:
        """Config endpoint returns error when participant missing."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None

        session = _fake_session(mock_result)
        app.dependency_overrides[get_async_session] = _override_session(session)

        try:
            with patch(
                "src.config.settings.get_settings",
                return_value=MagicMock(
                    demo_participant_phone="+15550009999",
                    demo_trial_id="diabetes-study-a",
                ),
            ):
                transport = ASGITransport(app=app)
                async with AsyncClient(
                    transport=transport,
                    base_url="http://test",
                ) as client:
                    response = await client.get("/api/demo/config")

            assert response.status_code == 200
            data = response.json()
            assert data["error"] == "demo participant not found"
        finally:
            app.dependency_overrides.clear()


def _mock_participant_trial(
    participant_id: uuid.UUID | None = None,
    adversarial_results: dict | None = None,
) -> MagicMock:
    """Build a mock ParticipantTrial ORM object.

    Args:
        participant_id: Optional participant UUID override.
        adversarial_results: Optional adversarial check results.

    Returns:
        MagicMock ParticipantTrial.
    """
    pt = MagicMock()
    pt.participant_trial_id = uuid.uuid4()
    pt.participant_id = participant_id or uuid.uuid4()
    pt.trial_id = "diabetes-study-a"
    pt.pipeline_status = "screening"
    pt.eligibility_status = "pending"
    pt.adversarial_results = adversarial_results
    pt.adversarial_recheck_done = adversarial_results is not None
    return pt


class TestAdversarialStatus:
    """GET /api/participants/{id}/adversarial-status endpoint."""

    async def test_get_adversarial_status_pending(self, app) -> None:
        """Returns pending when no adversarial_results exist."""
        pid = uuid.uuid4()
        mock_pt = _mock_participant_trial(pid, adversarial_results=None)
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_pt

        session = _fake_session(mock_result)
        app.dependency_overrides[get_async_session] = _override_session(
            session,
        )

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.get(
                    f"/api/participants/{pid}/adversarial-status",
                )

            assert response.status_code == 200
            data = response.json()
            assert data["check_status"] == "pending"
        finally:
            app.dependency_overrides.clear()

    async def test_get_adversarial_status_complete(self, app) -> None:
        """Returns complete with results when adversarial_results exist."""
        pid = uuid.uuid4()
        results = {
            "discrepancies": ["dob_mismatch"],
            "confidence": 0.85,
        }
        mock_pt = _mock_participant_trial(pid, adversarial_results=results)
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_pt

        session = _fake_session(mock_result)
        app.dependency_overrides[get_async_session] = _override_session(
            session,
        )

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.get(
                    f"/api/participants/{pid}/adversarial-status",
                )

            assert response.status_code == 200
            data = response.json()
            assert data["check_status"] == "complete"
            assert data["discrepancies"] == ["dob_mismatch"]
            assert data["confidence"] == 0.85
        finally:
            app.dependency_overrides.clear()


class TestResolveHandoff:
    """POST /api/handoffs/{id}/resolve endpoint."""

    async def test_resolve_handoff(self, app) -> None:
        """Resolves a handoff and updates status fields."""
        hid = uuid.uuid4()
        mock_handoff = _mock_handoff()
        mock_handoff.handoff_id = hid
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_handoff

        session = _fake_session(mock_result)
        app.dependency_overrides[get_async_session] = _override_session(
            session,
        )

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.post(
                    f"/api/handoffs/{hid}/resolve",
                    json={
                        "resolution": "Called participant back",
                        "resolved_by": "Dr. Smith",
                    },
                )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "resolved"
            assert data["resolution"] == "Called participant back"
            assert data["resolved_by"] == "Dr. Smith"
        finally:
            app.dependency_overrides.clear()


class TestAssignHandoff:
    """POST /api/handoffs/{id}/assign endpoint."""

    async def test_assign_handoff(self, app) -> None:
        """Assigns a handoff to a coordinator."""
        hid = uuid.uuid4()
        mock_handoff = _mock_handoff()
        mock_handoff.handoff_id = hid
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_handoff

        session = _fake_session(mock_result)
        app.dependency_overrides[get_async_session] = _override_session(
            session,
        )

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.post(
                    f"/api/handoffs/{hid}/assign",
                    json={"assigned_to": "Dr. Jones"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "assigned"
            assert data["assigned_to"] == "Dr. Jones"
        finally:
            app.dependency_overrides.clear()


class TestGetParticipantDetail:
    """GET /api/participants/{id} enhanced detail endpoint."""

    async def test_get_participant_detail(self, app) -> None:
        """Returns full participant detail with nested data."""
        pid = uuid.uuid4()
        mock_p = _mock_participant(pid)

        # Set up trial enrollments
        mock_trial = _mock_participant_trial(pid)
        mock_p.trials = [mock_trial]

        # Set up conversations
        mock_conv = _mock_conversation()
        mock_conv.participant_id = pid
        mock_p.conversations = [mock_conv]

        # Set up appointments
        mock_appt = _mock_appointment()
        mock_appt.participant_id = pid
        mock_appt.status = AppointmentStatus.BOOKED
        mock_p.appointments = [mock_appt]

        with patch(
            "src.api.dashboard.get_participant_by_id",
            new_callable=AsyncMock,
            return_value=mock_p,
        ):
            session = _fake_session(MagicMock())
            app.dependency_overrides[get_async_session] = _override_session(
                session,
            )

            try:
                transport = ASGITransport(app=app)
                async with AsyncClient(
                    transport=transport,
                    base_url="http://test",
                ) as client:
                    response = await client.get(
                        f"/api/participants/{pid}",
                    )

                assert response.status_code == 200
                data = response.json()
                assert data["participant_id"] == str(pid)
                assert data["first_name"] == "Jane"
                assert len(data["trials"]) == 1
                assert len(data["conversations"]) == 1
                assert len(data["appointments"]) == 1
            finally:
                app.dependency_overrides.clear()
