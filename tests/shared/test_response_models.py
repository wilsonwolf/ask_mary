"""Tests for Pydantic response models — validates construction and field defaults."""

import pytest
from pydantic import ValidationError

from src.shared.response_models import (
    AppointmentBookingResult,
    CallContextResult,
    CallOutcomeResult,
    CommunicationResult,
    DeceptionResult,
    DncCheckResult,
    DuplicateDetectionResult,
    EligibilityResult,
    GeoEligibilityResult,
    HardExcludeResult,
    IdentityVerificationResult,
    OutreachCallResult,
    ReminderResult,
    SafetyGateResult,
    ScreeningCriteriaResult,
    ScreeningResponseResult,
    SlotAvailabilityResult,
    SlotHoldResult,
    SupervisorAuditResult,
    TeachBackResult,
    TransportBookingResult,
    VerificationPromptsResult,
)
from src.shared.types import (
    AdversarialCheckStatus,
    CallOutcome,
    Channel,
    EligibilityStatus,
    HandoffReason,
    HandoffSeverity,
)


class TestAgentResultDictProtocol:
    """AgentResult supports full dict-style access for webhook compat."""

    def test_getitem(self) -> None:
        result = IdentityVerificationResult(verified=True, attempts=2)
        assert result["verified"] is True
        assert result["attempts"] == 2

    def test_contains(self) -> None:
        result = IdentityVerificationResult(verified=True)
        assert "verified" in result
        assert "nonexistent" not in result

    def test_get_with_default(self) -> None:
        result = IdentityVerificationResult(verified=True)
        assert result.get("verified") is True
        assert result.get("nonexistent", "fallback") == "fallback"
        assert result.get("nonexistent") is None

    def test_dict_unpacking(self) -> None:
        result = IdentityVerificationResult(verified=True, attempts=3)
        unpacked = {**result}
        assert unpacked["verified"] is True
        assert unpacked["attempts"] == 3

    def test_keys(self) -> None:
        result = IdentityVerificationResult(verified=True)
        field_names = result.keys()
        assert "verified" in field_names
        assert "attempts" in field_names

    def test_dict_merge(self) -> None:
        result = EligibilityResult(
            eligible=True,
            status=EligibilityStatus.ELIGIBLE,
            reason="all criteria met",
        )
        merged = {**result, "trial_name": "Study A"}
        assert merged["eligible"] is True
        assert merged["trial_name"] == "Study A"


class TestIdentityVerificationResult:
    """Tests for IdentityVerificationResult model."""

    def test_from_dict(self) -> None:
        data = {"verified": True, "attempts": 1}
        result = IdentityVerificationResult(**data)
        assert result.verified is True
        assert result.attempts == 1
        assert result.error is None

    def test_defaults(self) -> None:
        result = IdentityVerificationResult(verified=False)
        assert result.handoff_required is False
        assert result.attempts == 0
        assert result.reason is None

    def test_rejects_missing_required(self) -> None:
        with pytest.raises(ValidationError):
            IdentityVerificationResult()  # type: ignore[call-arg]


class TestDuplicateDetectionResult:
    """Tests for DuplicateDetectionResult model."""

    def test_from_dict(self) -> None:
        data = {"is_duplicate": True, "duplicate_ids": ["abc", "def"]}
        result = DuplicateDetectionResult(**data)
        assert result.is_duplicate is True
        assert result.duplicate_ids == ["abc", "def"]

    def test_defaults(self) -> None:
        result = DuplicateDetectionResult(is_duplicate=False)
        assert result.duplicate_ids == []
        assert result.error is None


class TestScreeningCriteriaResult:
    """Tests for ScreeningCriteriaResult model."""

    def test_from_dict(self) -> None:
        data = {
            "inclusion": {"age_min": 18},
            "exclusion": {"pregnant": True},
            "trial_name": "TRIAL-001",
        }
        result = ScreeningCriteriaResult(**data)
        assert result.inclusion == {"age_min": 18}
        assert result.trial_name == "TRIAL-001"

    def test_defaults(self) -> None:
        result = ScreeningCriteriaResult()
        assert result.inclusion == {}
        assert result.exclusion == {}
        assert result.trial_name == ""


class TestHardExcludeResult:
    """Tests for HardExcludeResult model."""

    def test_excluded(self) -> None:
        result = HardExcludeResult(excluded=True, reason="pregnant")
        assert result.excluded is True
        assert result.reason == "pregnant"

    def test_not_excluded(self) -> None:
        result = HardExcludeResult(excluded=False)
        assert result.reason == ""


class TestEligibilityResult:
    """Tests for EligibilityResult model."""

    def test_eligible(self) -> None:
        result = EligibilityResult(
            eligible=True,
            status=EligibilityStatus.ELIGIBLE,
            reason="meets all criteria",
        )
        assert result.eligible is True
        assert result.status == EligibilityStatus.ELIGIBLE

    def test_rejects_invalid_status(self) -> None:
        with pytest.raises(ValidationError):
            EligibilityResult(
                eligible=True,
                status="not_a_status",  # type: ignore[arg-type]
                reason="bad",
            )

    def test_rejects_missing_required(self) -> None:
        with pytest.raises(ValidationError):
            EligibilityResult(eligible=True)  # type: ignore[call-arg]


class TestScreeningResponseResult:
    """Tests for ScreeningResponseResult model."""

    def test_recorded(self) -> None:
        result = ScreeningResponseResult(recorded=True)
        assert result.recorded is True
        assert result.error is None


class TestGeoEligibilityResult:
    """Tests for GeoEligibilityResult model."""

    def test_eligible(self) -> None:
        result = GeoEligibilityResult(eligible=True, distance_km=15.5)
        assert result.distance_km == 15.5

    def test_ineligible_with_max(self) -> None:
        result = GeoEligibilityResult(
            eligible=False, distance_km=100.0, max_km=80.0
        )
        assert result.distance_km == 100.0
        assert result.max_km == 80.0

    def test_defaults(self) -> None:
        result = GeoEligibilityResult(eligible=False)
        assert result.distance_km is None
        assert result.reason == ""


class TestSlotAvailabilityResult:
    """Tests for SlotAvailabilityResult model."""

    def test_available(self) -> None:
        slots = [{"date": "2026-03-01", "time": "09:00"}]
        result = SlotAvailabilityResult(available=True, slots=slots)
        assert len(result.slots) == 1

    def test_defaults(self) -> None:
        result = SlotAvailabilityResult(available=False)
        assert result.slots == []


class TestSlotHoldResult:
    """Tests for SlotHoldResult model."""

    def test_held(self) -> None:
        result = SlotHoldResult(held=True, appointment_id="apt-123")
        assert result.appointment_id == "apt-123"


class TestAppointmentBookingResult:
    """Tests for AppointmentBookingResult model."""

    def test_booked(self) -> None:
        result = AppointmentBookingResult(
            booked=True,
            appointment_id="apt-123",
            confirmation_due_at="2026-03-01T21:00:00Z",
        )
        assert result.booked is True
        assert result.confirmation_due_at == "2026-03-01T21:00:00Z"


class TestTeachBackResult:
    """Tests for TeachBackResult model."""

    def test_passed(self) -> None:
        result = TeachBackResult(passed=True)
        assert result.handoff_required is False

    def test_failed_with_handoff(self) -> None:
        result = TeachBackResult(passed=False, handoff_required=True)
        assert result.handoff_required is True


class TestTransportBookingResult:
    """Tests for TransportBookingResult model."""

    def test_booked(self) -> None:
        result = TransportBookingResult(
            booked=True,
            ride_id="ride-456",
            pickup_address="123 Main St",
            dropoff_address="456 Clinic Ave",
        )
        assert result.ride_id == "ride-456"

    def test_defaults(self) -> None:
        result = TransportBookingResult(booked=False)
        assert result.pickup_address == ""
        assert result.dropoff_address == ""


class TestCommunicationResult:
    """Tests for CommunicationResult model."""

    def test_sent_sms(self) -> None:
        result = CommunicationResult(sent=True, channel=Channel.SMS)
        assert result.channel == Channel.SMS

    def test_defaults(self) -> None:
        result = CommunicationResult(sent=False)
        assert result.channel is None


class TestReminderResult:
    """Tests for ReminderResult model."""

    def test_scheduled(self) -> None:
        result = ReminderResult(scheduled=True, task_id="task-789")
        assert result.task_id == "task-789"


class TestSafetyGateResult:
    """Tests for SafetyGateResult model."""

    def test_triggered(self) -> None:
        result = SafetyGateResult(
            triggered=True,
            trigger_type=HandoffReason.MEDICAL_ADVICE,
            severity=HandoffSeverity.HANDOFF_NOW,
            elapsed_ms=42.5,
        )
        assert result.trigger_type == HandoffReason.MEDICAL_ADVICE

    def test_not_triggered(self) -> None:
        result = SafetyGateResult(triggered=False, elapsed_ms=10.0)
        assert result.trigger_type is None
        assert result.severity is None


class TestSupervisorAuditResult:
    """Tests for SupervisorAuditResult model."""

    def test_compliant(self) -> None:
        result = SupervisorAuditResult(compliant=True)
        assert result.violations == []
        assert result.phi_detected is False

    def test_violations(self) -> None:
        result = SupervisorAuditResult(
            compliant=False,
            violations=["missing_disclosure", "phi_leak"],
            phi_detected=True,
        )
        assert len(result.violations) == 2


class TestDeceptionResult:
    """Tests for DeceptionResult model."""

    def test_detected(self) -> None:
        result = DeceptionResult(
            deception_detected=True,
            discrepancies=[{"field": "dob", "stated": "1990-01-01", "ehr": "1985-06-15"}],
        )
        assert len(result.discrepancies) == 1

    def test_defaults(self) -> None:
        result = DeceptionResult(deception_detected=False)
        assert result.recheck_scheduled is False


class TestOutreachCallResult:
    """Tests for OutreachCallResult model."""

    def test_initiated(self) -> None:
        result = OutreachCallResult(initiated=True, conversation_id="conv-123")
        assert result.conversation_id == "conv-123"


class TestDncCheckResult:
    """Tests for DncCheckResult model."""

    def test_blocked(self) -> None:
        result = DncCheckResult(blocked=True, reason="twilio_opt_out")
        assert result.reason == "twilio_opt_out"

    def test_not_blocked(self) -> None:
        result = DncCheckResult(blocked=False)
        assert result.reason is None


class TestCallContextResult:
    """Tests for CallContextResult model."""

    def test_with_context(self) -> None:
        result = CallContextResult(
            context={"participant_name": "Jane Doe", "trial_id": "TRIAL-001"}
        )
        assert result.context["trial_id"] == "TRIAL-001"

    def test_defaults(self) -> None:
        result = CallContextResult()
        assert result.context == {}


class TestVerificationPromptsResult:
    """Tests for VerificationPromptsResult model."""

    def test_with_prompts(self) -> None:
        result = VerificationPromptsResult(
            check_status=AdversarialCheckStatus.COMPLETE,
            prompts=["Could you confirm your date of birth?"],
            discrepancies=[{"field": "dob", "stated": "1990", "ehr": "1985"}],
        )
        assert result.check_status == AdversarialCheckStatus.COMPLETE
        assert len(result.prompts) == 1

    def test_pending_defaults(self) -> None:
        result = VerificationPromptsResult()
        assert result.check_status == AdversarialCheckStatus.PENDING
        assert result.prompts == []
        assert result.discrepancies == []

    def test_str_enum_backward_compat(self) -> None:
        result = VerificationPromptsResult(
            check_status=AdversarialCheckStatus.COMPLETE,
        )
        assert result.check_status == "complete"


class TestCallOutcomeResult:
    """Tests for CallOutcomeResult model."""

    def test_recorded_outcome(self) -> None:
        result = CallOutcomeResult(
            recorded=True,
            outcome=CallOutcome.COMPLETED,
            should_retry=False,
        )
        assert result.recorded is True
        assert result.outcome == "completed"
        assert result.should_retry is False

    def test_retry_outcome(self) -> None:
        result = CallOutcomeResult(
            recorded=True,
            outcome=CallOutcome.NO_ANSWER,
            should_retry=True,
            next_attempt=2,
        )
        assert result.should_retry is True
        assert result.next_attempt == 2

    def test_defaults(self) -> None:
        result = CallOutcomeResult()
        assert result.recorded is False
        assert result.outcome == ""
        assert result.should_retry is False
        assert result.next_attempt is None

    def test_call_outcome_enum_values(self) -> None:
        assert CallOutcome.COMPLETED == "completed"
        assert CallOutcome.NO_ANSWER == "no_answer"
        assert CallOutcome.VOICEMAIL == "voicemail"
        assert CallOutcome.EARLY_HANGUP == "early_hangup"
        assert CallOutcome.WRONG_PERSON == "wrong_person"
        assert CallOutcome.REFUSED == "refused"
        assert CallOutcome.CONSENT_DENIED == "consent_denied"
