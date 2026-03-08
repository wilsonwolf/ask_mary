# src/services/ -- External Service Clients

Single-responsibility client wrappers for external APIs. Services never import from agents -- agents import services.

## Implemented Files

| File | Role |
|------|------|
| `twilio_client.py` | Twilio voice/SMS client -- `TwilioClient` class with `send_sms()`, `check_dnc_status()`, `initiate_warm_transfer()` (conference-based) |
| `elevenlabs_client.py` | ElevenLabs Conversational AI client -- `ElevenLabsClient` with `initiate_outbound_call()`, `get_conversation()`, `get_conversation_audio()`, workflow agent CRUD; plus standalone `build_system_prompt()` with trial criteria injection and `build_dynamic_variables()` |
| `elevenlabs_workflows.py` | ElevenLabs Workflow graph scaffold -- `WorkflowDefinition`, `WorkflowSubagentNode`, `Guardrail`, `TransitionEdge` dataclasses; `build_pipeline_workflow()` builder; `workflow_to_api_payload()` serializer; `create_workflow_agent()` / `update_workflow_agent()` async stubs (pending API GA) |
| `cloud_tasks_client.py` | In-memory task scheduler for MVP -- `enqueue_reminder()` stores tasks in a module-level list; background asyncio executor loop (`start_task_executor()` / `stop_task_executor()`) polls and POSTs due tasks to the local worker endpoint; production: replace with `google-cloud-tasks` |
| `gcs_client.py` | GCS audio storage -- `upload_audio()` and `generate_signed_url()` using Application Default Credentials; object path convention: `{trial_id}/{participant_id}/{conversation_id}.wav` |
| `uber_client.py` | Mock Uber Health client -- `MockUberHealthClient` with `get_estimate()` and `book_ride()` returning deterministic fake data for MVP/demo |
| `safety_service.py` | Safety gate bridge -- `run_safety_gate()` wires `shared/safety_gate.py` evaluation to `db/postgres.py` handoff_queue writes via `build_safety_callback()`; triggers Twilio warm transfer on `HANDOFF_NOW` severity |

## Not Yet Implemented

| File | Status |
|------|--------|
| `calendar_client.py` | Deferred -- Google Calendar integration not yet built |
| `pubsub_client.py` | Deferred -- Pub/Sub CDC bridge not yet built |

## Architecture Rules

- Each file wraps exactly one external service.
- All external API calls must be mockable for tests (no real API calls in test suite).
- Services are stateless -- configuration comes from `src/config/settings.py`.
- Services may import from `shared/` and `db/`, but never from `agents/`.
