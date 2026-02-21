# Ask Mary — Architecture

> System design, data flow, and infrastructure for the AI Clinical Trial Scheduling Agent.

---

## System Overview

```
                                    Ask Mary System Architecture
                                    ===========================

  Participant's Phone                          GCP Cloud Run                              Cloud SQL
  ===================                    ========================                   ==================
                                         |                      |
  +----------+     PSTN      +---------+ | +------------------+ |   asyncpg/SSL    +----------------+
  |          | <-----------> | Twilio  | | |   FastAPI App     | | <--------------> |   Postgres     |
  | Phone    |   Voice/DTMF  | Voice   |-+-|   (port 8000)    | |                  |                |
  |          |               +---------+ | |                  | |                  | participants   |
  +----------+                    |      | |  /webhooks/      | |                  | part._trials   |
        |                    Caller ID   | |  /api/           | |                  | appointments   |
        |                    + Status    | |  /ws/events      | |                  | conversations  |
        v                    Callbacks   | |                  | |                  | events         |
  +----------+                           | +--------+---------+ |                  | handoff_queue  |
  | SMS /    |     Twilio                |          |           |                  | rides          |
  | WhatsApp | <--- Messaging            |          v           |                  | agent_reason.  |
  +----------+     Service               | +--------+---------+ |                  | trials         |
                                         | | ElevenLabs       | |                  +----------------+
                                         | | Conversational   | |
  Coordinator                            | | AI 2.0           | |                  Cloud Storage
  Dashboard                              | | (Voice Runtime)  | |                  ==================
  ===================                   | +------------------+ |
                                         |          |           |                  +----------------+
  +----------+    HTTPS     +---------+  |          v           |                  | ask-mary-audio |
  | Browser  | <----------> | React   |  | +--------+---------+ |    signed URLs   |   bucket       |
  |          |   REST API   | SPA     |--+-| Webhook Handlers | | <--------------> |  .wav files    |
  |          |   WebSocket  | (Vite)  |  | | (18 server tools)| |                  +----------------+
  +----------+              +---------+  | +------------------+ |
                                         |          |           |
                                         |          v           |                  External APIs
                                         | +------------------+ |                  ==================
                                         | | Agent Modules    | |
                                         | | identity.py      | |   HTTP/REST      +----------------+
                                         | | screening.py     |-+-+--------------> | ElevenLabs API |
                                         | | scheduling.py    | | |                | (voice + TTS)  |
                                         | | transport.py     | | |                +----------------+
                                         | | comms.py         | | |
                                         | | supervisor.py    | | |                +----------------+
                                         | | adversarial.py   |-+-+- - - - - - - > | OpenAI API     |
                                         | +------------------+ | | (background)   | (post-call)    |
                                         |                      | |                +----------------+
                                         ======================== |
                                                                  |                +----------------+
                                                                  +- - - - - - - > | Uber Health    |
                                                                    (mock MVP)     | (transport)    |
                                                                                   +----------------+
```

---

## Voice Call Data Flow

A single outbound call traverses this path:

```
                          Voice Call Flow (60 seconds)
                          ============================

  Dashboard                FastAPI              ElevenLabs          Twilio           Phone
  (Browser)                (Cloud Run)          (Voice AI)          (PSTN)           (Participant)
     |                        |                     |                  |                 |
     |  POST /demo/start-call |                     |                  |                 |
     |----------------------->|                     |                  |                 |
     |                        |  POST /outbound-call|                  |                 |
     |                        |-------------------->|                  |                 |
     |                        |                     |  Initiate call   |                 |
     |                        |                     |----------------->|                 |
     |                        |                     |                  |  Ring + connect  |
     |                        |                     |                  |---------------->|
     |                        |                     |                  |                 |
     |                        |                     |<====== Voice conversation =======>|
     |                        |                     |                  |                 |
     |                        |                     | "I'm Mary, an   |                 |
     |                        |                     |  AI assistant..."|                 |
     |                        |                     |                  |                 |
     |                        |  Server Tool Call   |                  |                 |
     |                        |  capture_consent    |                  |                 |
     |                        |<--------------------|                  |                 |
     |  WS: consent_captured  |                     |                  |                 |
     |<-----------------------|  {consent: true}    |                  |                 |
     |                        |-------------------->|                  |                 |
     |                        |                     | "Please enter    |                 |
     |                        |                     |  your birth year"|                 |
     |                        |                     |                  |                 |
     |                        |  Server Tool Call   |                  |                 |
     |                        |  verify_identity    |                  |                 |
     |                        |<--------------------|                  |                 |
     |  WS: identity_verified |                     |                  |                 |
     |<-----------------------|  {verified: true}   |                  |                 |
     |                        |-------------------->|                  |                 |
     |                        |                     |                  |                 |
     |                        |  ... screening, scheduling, transport ...               |
     |                        |                     |                  |                 |
     |                        |  call-complete      |                  |                 |
     |                        |<--------------------|                  |                 |
     |                        |                     |                  |                 |
     |                        |-- fetch audio ----->|                  |                 |
     |                        |-- upload to GCS     |                  |                 |
     |                        |-- supervisor audit  |                  |                 |
     |                        |-- adversarial check |                  |                 |
     |  WS: audit_completed   |                     |                  |                 |
     |<-----------------------|                     |                  |                 |
```

---

## Server Tool Routing

During a voice call, ElevenLabs calls our webhook for each tool invocation:

```
                     Server Tool Request Flow
                     ========================

  ElevenLabs Agent
       |
       |  POST /webhooks/elevenlabs/server-tool
       |  {"tool_name": "verify_identity", "parameters": {...}}
       v
  +----+-----------------------------------------------------+
  |  handle_server_tool()                                     |
  |                                                           |
  |  1. Parse tool_name + parameters                          |
  |  2. Look up handler in TOOL_HANDLERS dict                 |
  |  3. Execute handler                                       |
  |  4. Convert Pydantic model → dict (exclude_none=True)     |
  |  5. Return JSON to ElevenLabs                             |
  +---------+-------------------------------------------------+
            |
            v
  +--------------------------------------------+
  |  TOOL_HANDLERS (18 registered tools)       |
  |                                            |
  |  Real-time tools (called during voice):    |
  |    capture_consent                         |
  |    verify_identity                         |
  |    detect_duplicate                        |
  |    get_screening_criteria                  |
  |    record_screening_answer                 |
  |    check_eligibility                       |
  |    check_hard_excludes                     |
  |    check_availability                      |
  |    hold_slot                               |
  |    book_appointment                        |
  |    book_transport                          |
  |    check_geo_eligibility                   |
  |    verify_teach_back                       |
  |    mark_wrong_person                       |
  |    mark_call_outcome                       |
  |    safety_check          (reactive only)   |
  |    get_verification_prompts                |
  |                                            |
  |  Background tools (post-call only):        |
  |    supervisor audit      (OpenAI)          |
  |    adversarial recheck   (OpenAI)          |
  +--------------------------------------------+
            |
            v
  +--------------------------------------------+
  |  _log_and_broadcast()                      |
  |                                            |
  |  1. Sanitize payload (Pydantic → dict)     |
  |  2. Write to events table (idempotent)     |
  |  3. Broadcast via WebSocket to dashboard   |
  +--------------------------------------------+
```

### Tool Gating (Current State)

Tool-level pre-checks (DNC, disclosure, consent gates) have been **intentionally removed** from the real-time path to eliminate latency during voice calls. The previous implementation added ~50-100ms per tool call for database reads that the ElevenLabs agent already enforces via the system prompt conversation flow.

Safety is now enforced at three levels:

1. **System Prompt** — strict conversation ordering (disclose → consent → verify → screen → schedule)
2. **Reactive Safety Check** — `safety_check` tool called only on medically concerning input
3. **Post-Call Audit** — supervisor and adversarial agents review the full transcript after the call

This is a deliberate trade-off: latency reduction at the cost of defense-in-depth. The gating can be re-enabled when the disclosure flow is fully wired (the system prompt needs to instruct the agent to pass `disclosed_automation=true` to `capture_consent`).

---

## Infrastructure

```
                          GCP Infrastructure
                          ==================

  +----------------------------------------------------------+
  |                     GCP Project                          |
  |                   (ask-mary-486802)                      |
  |                                                          |
  |  +-------------------+     +-------------------------+  |
  |  |  Cloud Build      |     |  Secret Manager         |  |
  |  |  (CI/CD pipeline) |     |                         |  |
  |  |                   |     |  CLOUD_SQL_PASSWORD      |  |
  |  |  cloudbuild.yaml  |     |  ELEVENLABS_API_KEY      |  |
  |  |  Dockerfile       |     |  ELEVENLABS_AGENT_ID     |  |
  |  +--------+----------+     |  ELEVENLABS_PHONE_ID     |  |
  |           |                +-------------------------+  |
  |           v                                              |
  |  +-------------------+     +-------------------------+  |
  |  | Artifact Registry |     |  Cloud Storage          |  |
  |  | (Docker images)   |     |                         |  |
  |  | us-west2          |     |  gs://ask-mary-audio    |  |
  |  +--------+----------+     |  .wav call recordings   |  |
  |           |                |  signed URLs (15 min)   |  |
  |           v                +-------------------------+  |
  |  +-------------------+                                   |
  |  |  Cloud Run        |     +-------------------------+  |
  |  |  (ask-mary)       |     |  Cloud SQL              |  |
  |  |                   +---->|  (ask-mary-db)           |  |
  |  |  Region: us-west2 |     |                         |  |
  |  |  Min instances: 1  | SSL |  PostgreSQL 15          |  |
  |  |  Port: 8000       |<----+  db-f1-micro            |  |
  |  |                   |     |  Instance: us-west2     |  |
  |  |  FastAPI + React  |     +-------------------------+  |
  |  |  (single container)|                                  |
  |  +-------------------+                                   |
  |                                                          |
  +----------------------------------------------------------+
```

### Container Architecture

The application runs as a single Docker container on Cloud Run:

```
  Docker Container (python:3.12-slim)
  ====================================

  +------------------------------------------------------+
  |                                                      |
  |  uvicorn (ASGI server)                               |
  |    |                                                 |
  |    +-- FastAPI App                                   |
  |         |                                            |
  |         +-- /webhooks/*     (ElevenLabs + Twilio)    |
  |         +-- /api/*          (Dashboard REST)         |
  |         +-- /ws/events      (WebSocket streaming)    |
  |         +-- /health         (Health check)           |
  |         +-- /*              (React SPA - static)     |
  |                                                      |
  |  Built from:                                         |
  |    Stage 1: node:20 → npm run build → dist/          |
  |    Stage 2: python:3.12 → uv sync → app + dist/     |
  |                                                      |
  +------------------------------------------------------+
```

---

## Database Schema

```
                         Entity Relationship Diagram
                         ===========================

  +------------------+       +---------------------+       +------------------+
  |  participants    |       |  participant_trials  |       |  trials          |
  |------------------|       |---------------------|       |------------------|
  |* participant_id  |<------| participant_id (FK)  |       |* trial_id        |
  |  mary_id         |   1:N | trial_id (FK)       |------>|  trial_name      |
  |  first_name      |       | pipeline_status     |   N:1 |  inclusion_crit. |
  |  last_name       |       | eligibility_status  |       |  exclusion_crit. |
  |  phone           |       | screening_responses |       |  operating_hours |
  |  date_of_birth   |       | adversarial_results |       |  site_name       |
  |  address_zip     |       +---------------------+       |  coordinator_ph  |
  |  identity_status |                                     |  max_distance_km |
  |  consent (JSONB) |                                     +------------------+
  |  dnc_flags       |
  |  contactability  |       +---------------------+       +------------------+
  +------------------+       |  appointments       |       |  conversations   |
          |                  |---------------------|       |------------------|
          |                  |* appointment_id     |       |* conversation_id |
          |             1:N  | participant_id (FK) |  1:N  | participant_id   |
          +----------------->| trial_id            |<------| trial_id         |
          |                  | scheduled_at        |       | channel          |
          |                  | visit_type          |       | direction        |
          |                  | status              |       | call_sid         |
          |                  | confirmed_at        |       | status           |
          |                  +---------------------+       | full_transcript  |
          |                                                | audio_gcs_path   |
          |                  +---------------------+       +------------------+
          |                  |  events             |
          |             1:N  |---------------------|       +------------------+
          +----------------->|* event_id           |       |  handoff_queue   |
          |                  | participant_id (FK) |       |------------------|
          |                  | event_type          |  1:N  |* handoff_id      |
          |                  | payload (JSONB)     |<------| participant_id   |
          |                  | provenance          |       | reason           |
          |                  | idempotency_key     |       | severity         |
          |                  | channel             |       | status           |
          |                  | created_at          |       | summary          |
          |                  +---------------------+       | coordinator_ph   |
          |                                                +------------------+
          |                  +---------------------+
          |             1:N  |  rides              |       +------------------+
          +----------------->|---------------------|       |  agent_reasoning |
          |                  |* ride_id            |       |------------------|
          |                  | participant_id (FK) |  1:N  |* reasoning_id    |
          |                  | appointment_id      |<------| conversation_id  |
                             | pickup_address      |       | participant_id   |
                             | dropoff_address     |       | agent_name       |
                             | status              |       | reasoning_trace  |
                             +---------------------+       +------------------+
```

---

## Safety Architecture

```
                        Safety Gate Model
                        =================

  Voice Input from Participant
            |
            v
  +---------------------------+
  |  System Prompt Ordering   |  Layer 1: Conversation Flow
  |                           |
  |  Step 1: Disclose AI      |  Must complete before proceeding
  |  Step 2: Get consent      |  Must hear verbal "yes"
  |  Step 3: Verify identity  |  Must match DOB + ZIP
  |  Step 4: Screen           |  One question at a time
  |  ...                      |
  +---------------------------+
            |
            v
  +---------------------------+
  |  Reactive Safety Check    |  Layer 2: Triggered by Concern
  |                           |
  |  7 Safety Triggers:       |  Called ONLY when participant
  |   - Medical advice req.   |  says something concerning
  |   - Consent withdrawal    |
  |   - Anger/threats         |  NOT called on routine
  |   - Adverse events        |  conversation (saves ~200ms
  |   - Emergency symptoms    |  per response)
  |   - Distress signals      |
  |   - Context-based         |
  +---------------------------+
            |
            | (if triggered)
            v
  +---------------------------+
  |  Handoff Queue            |  Layer 3: Human Escalation
  |                           |
  |  HANDOFF_NOW:             |  Twilio warm transfer +
  |    chest pain, breathing  |  dashboard alert
  |    difficulty, suicidal   |
  |                           |
  |  CALLBACK_TICKET:         |  Dashboard queue for
  |    stuck participant,     |  coordinator follow-up
  |    repeated confusion     |
  +---------------------------+
            |
            v (post-call)
  +---------------------------+
  |  Background Analysis      |  Layer 4: Post-Call Review
  |                           |
  |  Supervisor audit         |  OpenAI: compliance check
  |  PHI leak check           |  OpenAI: transcript scan
  |  Adversarial recheck      |  OpenAI: deception detection
  +---------------------------+
```

---

## WebSocket Event Streaming

The dashboard receives real-time updates via a persistent WebSocket connection:

```
  Backend                                      Frontend
  ============                                 ============

  Tool Handler executes
       |
       v
  _log_and_broadcast()
       |
       +-- 1. Sanitize payload (_make_json_safe)
       +-- 2. Write to events table
       +-- 3. broadcast_event() to all WS clients
       |
       v
  event_bus.py
       |                    WebSocket
       +-- send_json() ------------------> useWebSocket hook
                                                |
                                                v
                                           onMessage callback
                                                |
                                                v
                                           useDemoState reducer
                                                |
                                                +-- Dedup by event_id
                                                +-- Apply to state
                                                +-- Update UI panels
                                                |
                                                v
                                           Dashboard renders:
                                             - CallPanel
                                             - EligibilityPanel
                                             - SchedulingPanel
                                             - TransportPanel
                                             - EventsFeed

  On reconnect:
       Frontend fetches GET /api/events
       Replays all historical events through reducer
       Deduplicates with any live events received
```

---

## Comms Cadence

After an appointment is booked, three reminders are scheduled:

```
  Appointment Booked
       |
       +-- T-48h: Prep instructions (SMS)
       |     "Your appointment is in 2 days. Here's what to bring..."
       |
       +-- T-24h: Confirmation prompt (SMS)
       |     "Your appointment is tomorrow. Reply CONFIRM or RESCHEDULE"
       |
       +-- T-2h: Day-of check-in (SMS)
             "Your appointment is in 2 hours. Reply if you need help"

  Scheduling is non-blocking (asyncio.create_task) so it
  doesn't add latency to the booking response.
```

---

## Deployment Pipeline

```
  Developer                 Cloud Build              Cloud Run
  =========                 ===========              =========

  git push
     |
     v
  gcloud builds submit
     |
     v
  +---------------------+
  |  1. Docker build     |   Multi-stage:
  |     (node + python)  |   frontend → static files
  |                      |   backend → Python app
  +---------------------+
     |
     v
  +---------------------+
  |  2. Push to          |   us-west2-docker.pkg.dev/
  |     Artifact Registry|   ask-mary-486802/ask-mary/
  +---------------------+
     |
     v
  +---------------------+
  |  3. Deploy to        |   --min-instances=1
  |     Cloud Run        |   --allow-unauthenticated
  |                      |   --add-cloudsql-instances
  |                      |   Secrets injected from
  |                      |   Secret Manager
  +---------------------+
     |
     v
  https://ask-mary-*.run.app
  /health → {"status": "ok"}
```

---

## Cost Model

| Service | Running | Stopped | Notes |
|---------|---------|---------|-------|
| **Cloud SQL** (db-f1-micro) | **$7-12/day** | $0 | `--activation-policy=NEVER` to stop |
| Cloud Run (1 instance) | $0.50-1.00/day | $0 | `--min-instances=0` to stop |
| Cloud Storage | $0.02/GB/month | Same | Audio recordings, negligible |
| Artifact Registry | $0.10/GB/month | Same | Docker images, negligible |
| ElevenLabs | Per-minute voice | $0 | ~$0.08/min for conversations |
| Twilio | Per-call/SMS | $1/month (number) | ~$0.01/min + $0.0079/SMS |
| OpenAI | Per-token (background) | $0 | Post-call analysis only |

### Pause After Every Session

```bash
# Stop Cloud SQL (biggest cost saver — saves $7-12/day)
gcloud sql instances patch ask-mary-db \
  --activation-policy=NEVER \
  --project=ask-mary-486802

# Scale Cloud Run to zero (saves $0.50-1.00/day)
gcloud run services update ask-mary \
  --region=us-west2 \
  --min-instances=0 \
  --project=ask-mary-486802
```

See the full [Operations Runbook](local_docs/runbook.md) for resume and teardown commands.
