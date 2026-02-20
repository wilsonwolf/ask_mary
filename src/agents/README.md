# src/agents/ — Agent Implementations

One file per agent, using the OpenAI Agents SDK (`from agents import Agent`).

## Architecture

- **No agent imports another agent.** Agents communicate only via orchestrator handoffs.
- `pipeline.py` is the assembly module that wires the orchestrator SDK agent handoffs for programmatic orchestration.
- Each agent file defines:
  1. **Implemented helper functions** — async functions with full DB/service access, called by ElevenLabs webhook handlers in `src/api/webhooks.py`.
  2. **SDK `@function_tool` wrappers** — JSON-serializable stubs for the OpenAI Agents SDK runtime.
  3. **An `Agent()` object** — SDK agent definition with instructions and tool list.
- During live calls, **ElevenLabs Conversational AI acts as the orchestrator**. It calls server tool endpoints which route to agent helper functions via `TOOL_HANDLERS` in `webhooks.py`.
- All agents use `StrEnum` values from `src/shared/types` instead of magic strings (e.g., `Channel.VOICE`, `Provenance.SYSTEM`, `HandoffSeverity.CALLBACK_TICKET`).
- All handler functions return typed Pydantic response models from `src/shared/response_models`.

## Files

| File | Agent | Role | Key Functions |
|------|-------|------|---------------|
| `orchestrator.py` | orchestrator | Central coordinator — routes conversations, enforces gate sequence | — |
| `outreach.py` | outreach | Initiates contact, enforces DNC, manages retry cadence | `check_dnc_before_contact`, `assemble_call_context`, `initiate_outbound_call`, `capture_consent`, `mark_call_outcome`, `schedule_next_outreach`, `log_outreach_attempt`, `handle_stop_keyword` |
| `identity.py` | identity | Verifies identity (DOB year + ZIP via DTMF), detects duplicates | `verify_identity`, `detect_duplicate`, `mark_wrong_person`, `update_identity_status` |
| `screening.py` | screening | Eligibility screening, FAQ, caregiver auth, provenance annotation | `get_screening_criteria`, `check_hard_excludes`, `record_screening_response`, `determine_eligibility`, `record_caregiver_info` |
| `scheduling.py` | scheduling | Geo gate, Google Calendar slot booking, 12h confirmation window | `check_geo_eligibility`, `find_available_slots`, `hold_slot`, `book_appointment`, `verify_teach_back`, `release_expired_slot` |
| `transport.py` | transport | Uber Health ride booking (mock), pickup verification, reconfirmation | `confirm_pickup_address`, `book_transport`, `check_ride_status` |
| `comms.py` | comms | Event-driven communications cadence (T-48h through T+0) | `send_communication`, `schedule_reminder`, `handle_unreachable` |
| `supervisor.py` | supervisor | Post-call transcript audit, compliance check, deception detection | `audit_transcript`, `check_phi_leak`, `detect_answer_inconsistencies`, `audit_provenance` |
| `adversarial.py` | adversarial | Re-screens eligibility with different phrasing, EHR cross-reference | `detect_deception`, `generate_verification_prompts`, `schedule_recheck`, `run_adversarial_rescreen` |
| `pipeline.py` | — | Assembly module: wires orchestrator SDK agent handoffs for programmatic orchestration | — |

## Notable Constants and Enums

| Agent | Constant / Enum | Purpose |
|-------|-----------------|---------|
| `outreach.py` | `OUTREACH_CADENCE` | Retry cadence: `[("sms", 1h), ("voice", 24h), ("voice", 48h), ("sms", 49h)]` |
| `outreach.py` | `RETRY_OUTCOMES` | `frozenset` of `CallOutcome` enums triggering retry (`NO_ANSWER`, `VOICEMAIL`, `EARLY_HANGUP`) |
| `identity.py` | `MAX_IDENTITY_ATTEMPTS` | 2 attempts before handoff |
| `scheduling.py` | `CONFIRMATION_WINDOW_HOURS` | 12-hour window (BOOKED -> CONFIRMED) |
| `scheduling.py` | `SLOT_HOLD_MINUTES` | 15-minute temporary hold |
| `transport.py` | `_RECONFIRM_OFFSETS` | Ride reconfirmation at T-24h and T-2h |
| `comms.py` | `CHANNEL_FALLBACK` | Fallback map using `Channel` enums: `VOICE->SMS`, `SMS->WHATSAPP`, `WHATSAPP->SMS` |
| `adversarial.py` | `RECHECK_DELAY_DAYS` | 14-day recheck via Cloud Tasks, uses `Channel.SYSTEM` |
| `supervisor.py` | `REQUIRED_STEPS` | `["disclosure", "consent", "identity_verified"]` |
| `supervisor.py` | `PHI_KEYWORDS` | Keywords scanned before identity verification |

## Key Decision

The `from agents import Agent` import refers to the **OpenAI Agents SDK** third-party package (`openai-agents`), not to files within this directory.
