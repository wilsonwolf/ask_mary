# src/api/ — FastAPI Routes

HTTP, WebSocket, and worker callback endpoints for Ask Mary.

## Files

| File | Role |
|------|------|
| `app.py` | Application factory (`create_app()`) with lifespan context manager, CORS, router wiring, frontend static mount |
| `webhooks.py` | ElevenLabs server tool callbacks + Twilio DTMF/status webhooks |
| `dashboard.py` | Coordinator dashboard REST API + WebSocket for real-time events |
| `event_bus.py` | In-memory WebSocket client registry and `broadcast_event()` |
| `worker_routes.py` | Cloud Tasks worker callback endpoints (reminder delivery) |

## app.py

- **`create_app()`** factory returns a configured `FastAPI` instance with `_lifespan` context manager.
- Lifespan starts/stops the in-memory Cloud Tasks executor (`start_task_executor` / `stop_task_executor`).
- Registers routers: `webhooks_router`, `dashboard_router`, `ws_router`, `worker_router`, and a health router.
- Mounts React frontend via `StaticFiles` from `frontend/dist/` (if built).
- Configures CORS middleware from `settings.cors_allowed_origins`.
- Wires `validators.get_participant_by_id` to the real Postgres implementation at startup.
- **`GET /health`** returns `{"status": "ok"}` for Cloud Run readiness probes.

## webhooks.py

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/webhooks/elevenlabs/server-tool` | Central dispatcher for all ElevenLabs server tool calls during live conversations |
| POST | `/webhooks/elevenlabs/call-complete` | Post-call processing: audio fetch/upload, transcript fetch, supervisor audit, retry scheduling |
| POST | `/webhooks/audio/signed-url` | Generate GCS signed URL for audio playback |
| POST | `/webhooks/twilio/dtmf` | Two-step DTMF capture (4-digit DOB year, then 5-digit ZIP) |
| POST | `/webhooks/twilio/dtmf-verify` | Direct identity verification with previously captured DTMF digits |
| POST | `/webhooks/twilio/status` | Capture Twilio CallSid and associate with conversation record |

### TOOL_HANDLERS (18 entries: 14 unique tools + 2 aliases)

| Tool Name | Handler | Agent Source |
|-----------|---------|-------------|
| `verify_identity` | `_handle_verify_identity` | `identity.verify_identity` |
| `detect_duplicate` | `_handle_detect_duplicate` | `identity.detect_duplicate` |
| `get_screening_criteria` | `_handle_get_screening_criteria` | `screening.get_screening_criteria` |
| `check_hard_excludes` | `_handle_check_hard_excludes` | `screening.check_hard_excludes` |
| `determine_eligibility` | `_handle_determine_eligibility` | `screening.determine_eligibility` |
| `record_screening_response` | `_handle_record_screening_response` | `screening.record_screening_response` |
| `check_availability` | `_handle_check_availability` | `scheduling.find_available_slots` |
| `book_appointment` | `_handle_book_appointment` | `scheduling.book_appointment` |
| `book_transport` | `_handle_book_transport` | `transport.book_transport` |
| `safety_check` | `_handle_safety_check` | `safety_service.run_safety_gate` |
| `capture_consent` | `_handle_capture_consent` | Direct DB update (consent + contactability) |
| `get_verification_prompts` | `_handle_get_verification_prompts` | `adversarial.generate_verification_prompts` |
| `check_geo_eligibility` | `_handle_check_geo` | `scheduling.check_geo_eligibility` |
| `verify_teach_back` | `_handle_verify_teach_back` | `scheduling.verify_teach_back` |
| `hold_slot` | `_handle_hold_slot` | `scheduling.hold_slot` |
| `mark_wrong_person` | `_handle_mark_wrong_person` | `identity.mark_wrong_person` |
| `mark_call_outcome` | `_handle_mark_call_outcome` | `outreach.mark_call_outcome` |
| `record_screening_answer` | (alias) `_handle_record_screening_response` | Same as `record_screening_response` |
| `check_eligibility` | (alias) `_handle_determine_eligibility` | Same as `determine_eligibility` |

All handlers accept `(session: AsyncSession, params: dict[str, Any])` and return `dict[str, Any]`.

### Gated Tools

Tools in `GATED_TOOLS` require DNC + disclosure + consent pre-checks before execution. `capture_consent` and `safety_check` are excluded from gating (consent IS the mechanism; safety is independent).

### Post-Call Processing

- **`_trigger_post_call_checks`** runs supervisor `audit_transcript`, `check_phi_leak`, and adversarial `schedule_recheck`.
- **`_check_and_schedule_retry`** queries the most recent `call_outcome_recorded` event and schedules retry via `outreach.schedule_next_outreach` if outcome is retryable.
- **`_schedule_comms_cadence`** enqueues T-48h prep, T-24h confirmation, and T-2h day-of reminders after appointment booking.

## dashboard.py

### REST Endpoints (prefix: `/api`)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/participants` | List participants (limit 50) |
| GET | `/api/participants/{id}` | Participant detail with nested trials, conversations, appointments |
| GET | `/api/participants/{id}/adversarial-status` | Adversarial check status for a participant |
| GET | `/api/appointments` | List appointments (limit 50) |
| GET | `/api/handoff-queue` | List active handoff tickets |
| POST | `/api/handoffs/{id}/resolve` | Resolve a handoff ticket with resolution details |
| POST | `/api/handoffs/{id}/assign` | Assign a handoff ticket to a coordinator |
| GET | `/api/conversations` | List recent conversations |
| GET | `/api/events` | Paginated events feed (limit + offset) |
| GET | `/api/analytics/summary` | Aggregate counts: total participants, appointments, open handoffs |
| GET | `/api/tasks` | List in-memory scheduled Cloud Tasks |
| PATCH | `/api/trials/{id}/coordinator` | Update coordinator phone for a trial |
| GET | `/api/demo/config` | Demo participant and trial info for the frontend |
| POST | `/api/demo/start-call` | Trigger outbound demo call via ElevenLabs |

### WebSocket

| Path | Purpose |
|------|---------|
| `/ws/events` | Real-time event stream to dashboard; broadcasts all events logged via `_log_and_broadcast` |

All REST handlers return `dict[str, Any]` or `list[dict[str, Any]]`.

## Key Decisions

- **App factory pattern**: `create_app()` returns a configured `FastAPI` instance, enabling test isolation via `TestClient(create_app())`.
- **Health endpoint**: `GET /health` returns `{"status": "ok"}` for Cloud Run readiness probes.
- **ElevenLabs as live orchestrator**: During calls, ElevenLabs server tools POST to `/webhooks/elevenlabs/server-tool` which dispatches to agent helper functions via `TOOL_HANDLERS`. The OpenAI Agents SDK objects are used for programmatic orchestration, not live call routing.
- **Event broadcast**: All significant tool handler results are persisted via `log_event` and broadcast to WebSocket clients via `broadcast_event`.
