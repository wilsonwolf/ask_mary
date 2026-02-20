# src/workers/ -- Background Task Handlers

Cloud Tasks callback handlers and background job processors.

## Files

| File | Role |
|------|------|
| `reminders.py` | Cloud Tasks callback router with 12 task handlers covering confirmations, reminders, transport, outreach, no-show rescue, and adversarial rechecks |

**Note**: `cdc.py` (Pub/Sub to Databricks bridge) is not implemented. Databricks is stubbed for the MVP; all analytics remain in Postgres.

## reminders.py -- Task Handler Details

### Entry Point

`handle_reminder_task(session, payload)` is the main dispatcher. It:

1. Checks the `idempotency_key` against the events table to prevent duplicate processing from Cloud Tasks redelivery.
2. Routes by `template_id` to the matching handler in the `TASK_HANDLERS` dictionary.
3. Returns a dict with `processed: True/False` and handler-specific results.

### TASK_HANDLERS Dictionary (12 entries, 6 unique handlers)

| template_id | Handler | Description |
|-------------|---------|-------------|
| `confirmation_check` | `_handle_confirmation_check` | Checks if BOOKED appointment was confirmed in time; marks EXPIRED_UNCONFIRMED and triggers slot release + follow-up if not |
| `slot_release` | `_handle_slot_release` | Releases HELD slots by updating status to RELEASED |
| `appointment_reminder` | `_handle_reminder` | Renders template and sends reminder via configured channel |
| `visit_reminder` | `_handle_reminder` | Same generic reminder handler (different template_id) |
| `prep_instructions` | `_handle_reminder` | Sends prep instructions via generic reminder handler |
| `confirmation_prompt` | `_handle_reminder` | Sends confirmation prompt via generic reminder handler |
| `day_of_checkin` | `_handle_reminder` | Sends day-of check-in via generic reminder handler |
| `adversarial_recheck` | `_handle_adversarial_recheck` | Runs adversarial rescreen for a participant-trial pair (lazy import from agents) |
| `transport_reconfirm_24h` | `_handle_transport_reconfirm` | Reconfirms ride at T-24h; skips if ride is cancelled or failed |
| `transport_reconfirm_2h` | `_handle_transport_reconfirm` | Reconfirms ride at T-2h; same logic as 24h |
| `outreach_retry` | `_handle_outreach_retry` | Executes voice or SMS retry based on channel, then schedules next cadence step |
| `no_show_rescue` | `_handle_no_show_rescue` | Marks BOOKED/CONFIRMED appointment as NO_SHOW and creates a CALLBACK_TICKET handoff for coordinators |

### Notable Handler Behaviors

- **`_handle_confirmation_check`**: On expiry, enqueues both a `slot_release` task and a follow-up `appointment_reminder` 24 hours later via `_release_and_follow_up`.
- **`_handle_no_show_rescue`**: Creates a `HandoffQueue` entry with `HandoffReason.NO_SHOW` and `HandoffSeverity.CALLBACK_TICKET` so coordinators can follow up.
- **`_handle_outreach_retry`**: Routes to `_execute_voice_retry` (calls `initiate_outbound_call` from agents.outreach) or `_execute_sms_retry` (renders `outreach_nudge` template), then calls `schedule_next_outreach` to enqueue the following cadence step.
- **`_handle_transport_reconfirm`**: Skips rides with CANCELLED or FAILED status; logs `transport_reconfirm_sent` event for active rides.

## Architecture Rules

- Workers receive Cloud Tasks HTTP callbacks via the `POST /workers/task` endpoint (defined in `src/api/app.py`).
- Each handler uses an `idempotency_key` dedup guard before execution (checked against the events table).
- Workers import from `services/`, `db/`, and `shared/`. Two handlers use lazy imports from `agents/` (outreach and adversarial) to avoid circular dependencies at module load time.
