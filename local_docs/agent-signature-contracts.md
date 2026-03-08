# Agent Signature Contracts

> **STATUS: COMPLETED** (2026-02-20) — All 34 functions migrated to Pydantic response models.
> See `src/shared/response_models.py` for all model definitions.

> Contract sheet for the Foundation Then Flood Phase 0/1 type migration. All contracts fulfilled.

## Identity Agent (`src/agents/identity.py`)

| Line | Function | Current Return | Target Return |
|------|----------|---------------|---------------|
| 21 | `verify_identity()` | `-> dict` | `-> IdentityVerificationResult` |
| 88 | `detect_duplicate()` | `-> dict` | `-> DuplicateDetectionResult` |
| 133 | `mark_wrong_person()` | `-> dict` | `-> IdentityVerificationResult` |
| 160 | `update_identity_status()` | `-> dict` | `-> IdentityVerificationResult` |

## Screening Agent (`src/agents/screening.py`)

| Line | Function | Current Return | Target Return |
|------|----------|---------------|---------------|
| 19 | `get_screening_criteria()` | `-> dict` | `-> ScreeningCriteriaResult` |
| 42 | `check_hard_excludes()` | `-> dict` | `-> HardExcludeResult` |
| 70 | `record_screening_response()` | `-> dict` | `-> ScreeningResponseResult` |
| 213 | `determine_eligibility()` | `-> dict` | `-> EligibilityResult` |
| 304 | `record_caregiver_info()` | `-> dict` | `-> ScreeningResponseResult` |

## Scheduling Agent (`src/agents/scheduling.py`)

| Line | Function | Current Return | Target Return |
|------|----------|---------------|---------------|
| 25 | `check_geo_eligibility()` | `-> dict` | `-> GeoEligibilityResult` |
| 52 | `find_available_slots()` | `-> dict` | `-> SlotAvailabilityResult` |
| 82 | `hold_slot()` | `-> dict` | `-> SlotHoldResult` |
| 138 | `book_appointment()` | `-> dict` | `-> AppointmentBookingResult` |
| 264 | `verify_teach_back()` | `-> dict` | `-> TeachBackResult` |
| 320 | `release_expired_slot()` | `-> dict` | `-> AppointmentBookingResult` |

## Transport Agent (`src/agents/transport.py`)

| Line | Function | Current Return | Target Return |
|------|----------|---------------|---------------|
| 23 | `confirm_pickup_address()` | `-> dict` | `-> TransportBookingResult` |
| 54 | `book_transport()` | `-> dict` | `-> TransportBookingResult` |
| 94 | `check_ride_status()` | `-> dict` | `-> TransportBookingResult` |

## Outreach Agent (`src/agents/outreach.py`)

| Line | Function | Current Return | Target Return |
|------|----------|---------------|---------------|
| 33 | `check_dnc_before_contact()` | `-> dict` | `-> DncCheckResult` |
| 69 | `assemble_call_context()` | `-> dict` | `-> CallContextResult` |
| 117 | `initiate_outbound_call()` | `-> dict` | `-> OutreachCallResult` |
| 208 | `capture_consent()` | `-> dict` | `-> ScreeningResponseResult` |
| 240 | `log_outreach_attempt()` | `-> dict` | `-> CommunicationResult` |
| 271 | `handle_stop_keyword()` | `-> dict` | `-> DncCheckResult` |

## Comms Agent (`src/agents/comms.py`)

| Line | Function | Current Return | Target Return |
|------|----------|---------------|---------------|
| 21 | `send_communication()` | `-> dict` | `-> CommunicationResult` |
| 63 | `schedule_reminder()` | `-> dict` | `-> ReminderResult` |
| 118 | `handle_unreachable()` | `-> dict` | `-> CommunicationResult` |

## Supervisor Agent (`src/agents/supervisor.py`)

| Line | Function | Current Return | Target Return |
|------|----------|---------------|---------------|
| 31 | `audit_transcript()` | `-> dict` | `-> SupervisorAuditResult` |
| 70 | `check_phi_leak()` | `-> dict` | `-> SupervisorAuditResult` |
| 145 | `detect_answer_inconsistencies()` | `-> dict` | `-> DeceptionResult` |
| 198 | `audit_provenance()` | `-> dict` | `-> SupervisorAuditResult` |

## Adversarial Agent (`src/agents/adversarial.py`)

| Line | Function | Current Return | Target Return |
|------|----------|---------------|---------------|
| 25 | `detect_deception()` | `-> dict` | `-> DeceptionResult` |
| 68 | `schedule_recheck()` | `-> dict` | `-> ReminderResult` |
| 96 | `run_adversarial_rescreen()` | `-> dict` | `-> DeceptionResult` |

## Summary

- **Total functions to update**: 34
- **Response models used**: 20 (from `src/shared/response_models.py`)
- **Import to add in each agent file**: `from src.shared.response_models import <Models>`
