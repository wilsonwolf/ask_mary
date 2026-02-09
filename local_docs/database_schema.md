# Ask Mary — Database Schema Reference

This document is the authoritative reference for all database tables.
Source of truth: `src/db/models.py` (implementation) + Section 6 of `ask_mary_plan.md` (design).

---

## Architecture Overview

| Layer | Engine | Purpose |
|-------|--------|---------|
| **OLTP** | Cloud SQL Postgres | Operational state: participants, appointments, events, handoffs |
| **OLAP** | Databricks Delta Lake | Analytics: trials (future), EHR, conversation archive, audit log |
| **Audio** | GCS (`ask-mary-audio`) | Voice recordings with IAM + signed URLs |

**MVP Note**: Databricks is fully stubbed (`src/db/databricks.py`). All data lives in Postgres.

---

## Operational Tables (Cloud SQL Postgres)

### `participants`

Core participant record. Phone is NOT unique (caregivers/family share).

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `participant_id` | UUID | PK | Auto-generated |
| `mary_id` | String(64) | UNIQUE, INDEX | HMAC-SHA256(first+last+dob+phone, pepper) |
| `agency_id` | String(100) | nullable | External agency reference |
| `first_name` | String(100) | NOT NULL | |
| `last_name` | String(100) | NOT NULL | |
| `date_of_birth` | Date | NOT NULL | Used for identity verification (year) |
| `phone` | String(20) | INDEX | NOT unique — caregivers share |
| `secondary_phone` | String(20) | nullable | |
| `address_street` | String(200) | nullable | Transport agent uses full address |
| `address_city` | String(100) | nullable | |
| `address_state` | String(50) | nullable | |
| `address_zip` | String(10) | nullable | Used for identity verification |
| `timezone` | String(50) | nullable | e.g. "America/Los_Angeles" |
| `distance_to_site_km` | Float | nullable | Geo gate check |
| `preferred_channel` | String(20) | nullable | voice, sms, whatsapp |
| `best_time_to_reach` | String(50) | nullable | |
| `language` | String(10) | default "en" | |
| `identity_status` | String(20) | default "unverified" | unverified / verified / wrong_person |
| `dnc_flags` | JSONB | default {} | `{"voice": true, "sms": false}` per channel |
| `contactability` | JSONB | default {} | `{"identity_attempts": N}` |
| `consent` | JSONB | default {} | `{"disclosed_automation": bool, "consent_to_continue": bool}` |
| `caregiver` | JSONB | nullable | `{"name": str, "relationship": str, "scope": str}` |
| `contactability_risk` | String(10) | default "none" | none / low / high |
| `outreach_attempt_count` | Integer | default 0 | |
| `next_action_at` | TimestampTZ | nullable | |
| `next_action_type` | String(30) | nullable | outreach_retry, reverify, etc. |
| `recheck_scheduled_at` | TimestampTZ | nullable | |
| `created_at` | TimestampTZ | NOT NULL | |
| `updated_at` | TimestampTZ | NOT NULL | Auto-updates |

**Relationships**: trials (ParticipantTrial), appointments, conversations, events, rides, handoffs

---

### `participant_trials`

Junction table for multi-trial enrollment. Per-trial screening state.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `participant_trial_id` | UUID | PK | |
| `participant_id` | UUID | FK → participants, INDEX | |
| `trial_id` | String(100) | FK → trials, INDEX | |
| `pipeline_status` | String(20) | default "new" | new / outreach / screening / scheduling / booked / confirmed / completed / no_show / cancelled / unreachable / dnc |
| `enrollment_status` | String(20) | default "screening" | screening / eligible / enrolled / completed / withdrawn / ineligible |
| `eligibility_status` | String(20) | default "pending" | pending / eligible / provisional / ineligible / needs_human |
| `eligibility_confidence` | Float | nullable | |
| `screening_responses` | JSONB | default {} | `{"question_key": {"answer": val, "provenance": str}}` |
| `ehr_discrepancies` | JSONB | nullable | Flagged mismatches vs EHR |
| `adversarial_recheck_done` | Boolean | default false | |
| `adversarial_results` | JSONB | nullable | |
| `enrolled_at` | TimestampTZ | nullable | |
| `created_at` | TimestampTZ | NOT NULL | |
| `updated_at` | TimestampTZ | NOT NULL | Auto-updates |

**Unique Constraint**: `(participant_id, trial_id)` — one enrollment per trial

---

### `trials`

Clinical trial definitions (interim in Postgres, future migration to Databricks).

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `trial_id` | String(100) | PK | e.g. "diabetes-study-a" |
| `trial_name` | String(200) | NOT NULL | Human-readable name |
| `inclusion_criteria` | JSONB | default {} | `{"min_age": 18, "max_age": 75, "diagnosis": "type_2_diabetes"}` |
| `exclusion_criteria` | JSONB | default {} | `{"pregnant_or_nursing": true}` — boolean flags |
| `visit_templates` | JSONB | default {} | `{"screening": {"duration_min": 90, "fasting": true}}` |
| `pi_name` | String(200) | nullable | Principal investigator |
| `coordinator_name` | String(200) | nullable | |
| `coordinator_phone` | String(20) | nullable | For handoff warm transfer |
| `site_address` | String(300) | nullable | Used for transport dropoff |
| `site_name` | String(200) | nullable | For teach-back verification |
| `calendar_id` | String(200) | nullable | Google Calendar ID |
| `max_distance_km` | Float | default 80.0 | Geo gate threshold |
| `operating_hours` | JSONB | default {} | `{"monday": {"open": "08:00", "close": "17:00"}}` |
| `active` | Boolean | default true | |
| `created_at` | TimestampTZ | NOT NULL | |

---

### `appointments`

Scheduled trial visits with confirmation workflow.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `appointment_id` | UUID | PK | |
| `participant_id` | UUID | FK → participants, INDEX | |
| `trial_id` | String(100) | FK → trials | |
| `visit_type` | String(20) | NOT NULL | screening / baseline / follow_up |
| `scheduled_at` | TimestampTZ | NOT NULL | UTC, rendered in participant/site TZ |
| `google_event_id` | String(200) | UNIQUE | Google Calendar event ref |
| `status` | String(30) | default "booked" | held / booked / confirmed / completed / no_show / cancelled / expired_unconfirmed |
| `site_address` | String(300) | nullable | |
| `site_name` | String(200) | nullable | |
| `prep_instructions` | Text | nullable | |
| `estimated_duration_min` | Integer | nullable | |
| `slot_held_until` | TimestampTZ | nullable | SELECT FOR UPDATE reservation |
| `confirmation_due_at` | TimestampTZ | nullable | booked_at + 12h |
| `teach_back_passed` | Boolean | nullable | |
| `teach_back_attempts` | Integer | default 0 | Max 2 before handoff |
| `cancellation_reason` | String(200) | nullable | |
| `no_show_reason` | String(200) | nullable | |
| `outcome_reason_code` | String(50) | nullable | Standardized codes |
| `slot_released_at` | TimestampTZ | nullable | |
| `created_at` | TimestampTZ | NOT NULL | |
| `updated_at` | TimestampTZ | NOT NULL | Auto-updates |

**Status Lifecycle**: HELD → BOOKED → CONFIRMED → COMPLETED | NO_SHOW | CANCELLED

---

### `conversations`

Voice/SMS conversation records with full transcript.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `conversation_id` | UUID | PK | |
| `participant_id` | UUID | FK → participants, INDEX | |
| `trial_id` | String(100) | FK → trials, nullable | |
| `channel` | String(20) | NOT NULL | voice / sms / whatsapp |
| `direction` | String(20) | NOT NULL | inbound / outbound |
| `agent_name` | String(50) | nullable | Agent handling the call |
| `call_sid` | String(100) | UNIQUE | ElevenLabs conversation ID / Twilio SID |
| `audio_gcs_path` | String(500) | nullable | GCS object path (signed URLs on demand) |
| `duration_seconds` | Float | nullable | |
| `status` | String(20) | default "active" | active / completed / failed / transferred |
| `full_transcript` | JSONB | nullable | Ordered turns with speaker, text, timestamp |
| `summary` | JSONB | nullable | Structured summary (NO internal reasoning) |
| `handoff_reason` | String(100) | nullable | |
| `started_at` | TimestampTZ | NOT NULL | |
| `ended_at` | TimestampTZ | nullable | |

---

### `events`

**Append-only** event log with provenance and idempotency. No UPDATE/DELETE.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `event_id` | UUID | PK | |
| `participant_id` | UUID | FK → participants, INDEX | |
| `appointment_id` | UUID | FK → appointments, nullable | |
| `conversation_id` | UUID | nullable | Not FK (flexibility) |
| `trial_id` | String(100) | FK → trials, nullable | |
| `event_type` | String(50) | INDEX | See event types below |
| `payload` | JSONB | default {} | Event-specific data |
| `provenance` | String(20) | nullable | patient_stated / ehr / coordinator / system |
| `idempotency_key` | String(200) | UNIQUE | Prevents duplicate outbound actions |
| `channel` | String(20) | nullable | voice / sms / whatsapp / system |
| `created_at` | TimestampTZ | NOT NULL | |

**Composite Index**: `(participant_id, event_type, created_at)`

**Event Types**: outreach_attempt, consent_captured, identity_verified, identity_failed, screening_completed, slot_booked, appointment_booked, confirmation_sent, confirmation_received, slot_expired, reminder_sent, transport_booked, transport_failed, no_show, completed, cancelled, rescheduled, handoff_created, dnc_applied, dnc_set, channel_switched, teach_back_passed, teach_back_failed, unreachable_flagged, caregiver_recorded, duplicate_detected, wrong_person_marked, outbound_call_initiated

---

### `handoff_queue`

Human coordinator handoff tasks with severity and SLA tracking.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `handoff_id` | UUID | PK | |
| `participant_id` | UUID | FK → participants, INDEX | |
| `conversation_id` | UUID | nullable | |
| `trial_id` | String(100) | FK → trials, nullable | |
| `reason` | String(50) | NOT NULL | medical_advice, severe_symptoms, adverse_event, consent_withdrawal, anger_threats, repeated_misunderstanding, language_mismatch, geo_ineligible, unreachable, teach_back_failure |
| `severity` | String(20) | NOT NULL | HANDOFF_NOW / CALLBACK_TICKET / STOP_CONTACT |
| `priority` | String(10) | default "medium" | critical / high / medium / low |
| `status` | String(20) | default "open" | open / assigned / resolved / escalated |
| `summary` | Text | nullable | AI-generated situation summary |
| `recommended_next_action` | String(200) | nullable | |
| `coordinator_phone` | String(20) | nullable | For warm transfer |
| `callback_number` | String(20) | nullable | Participant callback number |
| `language` | String(10) | nullable | |
| `preferred_callback_window` | String(50) | nullable | |
| `handoff_packet` | JSONB | nullable | Full context bundle |
| `due_at` | TimestampTZ | nullable | SLA: HANDOFF_NOW=immediate, CALLBACK=2h |
| `assigned_to` | String(100) | nullable | Coordinator name/id |
| `created_at` | TimestampTZ | NOT NULL | |
| `resolved_at` | TimestampTZ | nullable | |

---

### `rides`

Transport/ride bookings linked to appointments.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `ride_id` | UUID | PK | |
| `appointment_id` | UUID | FK → appointments, INDEX | |
| `participant_id` | UUID | FK → participants, INDEX | |
| `pickup_address` | String(300) | NOT NULL | |
| `dropoff_address` | String(300) | NOT NULL | Usually trial site_address |
| `scheduled_pickup_at` | TimestampTZ | NOT NULL | appointment_time - 1 hour |
| `uber_ride_id` | String(100) | nullable | External ride service ID |
| `status` | String(20) | default "pending" | pending / confirmed / dispatched / completed / failed / cancelled |
| `failure_reason` | String(200) | nullable | |
| `return_trip` | Boolean | default false | |
| `created_at` | TimestampTZ | NOT NULL | |
| `updated_at` | TimestampTZ | NOT NULL | Auto-updates |

---

### `agent_reasoning`

Internal agent reasoning traces. **Never commingled with conversation data.**

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `reasoning_id` | UUID | PK | |
| `conversation_id` | UUID | FK → conversations, INDEX | |
| `participant_id` | UUID | FK → participants, INDEX | |
| `agent_name` | String(50) | NOT NULL | |
| `reasoning_trace` | JSONB | nullable | Agent decisions, internal prompts |
| `tool_calls` | JSONB | nullable | Ordered tool invocations + results |
| `safety_gate_log` | JSONB | nullable | Safety gate evaluation trace |
| `created_at` | TimestampTZ | NOT NULL | |

---

## Analytics Tables (Databricks Delta Lake) — DEFERRED

These tables are stubbed for MVP. See `src/db/databricks.py`.

### `trials` (future migration from Postgres)
Same schema as Postgres `trials` table above.

### `participant_ehr`
| Column | Type | Notes |
|--------|------|-------|
| `ehr_record_id` | String | PK |
| `participant_id` | String | FK |
| `trial_id` | String | FK |
| `demographics` | JSON | |
| `medical_history` | JSON | |
| `medications` | JSON | |
| `lab_results` | JSON | |
| `source_system` | String | |
| `imported_at` | Timestamp | |

### `conversations_archive`
| Column | Type | Notes |
|--------|------|-------|
| `conversation_id` | String | PK |
| `participant_id` | String | |
| `trial_id` | String | |
| `channel` | String | |
| `direction` | String | |
| `agent_name` | String | |
| `full_transcript` | JSON | |
| `duration_seconds` | Float | |
| `sentiment_score` | String | ML-derived |
| `topic_tags` | JSON | ML-derived |
| `handoff_triggers_fired` | JSON | |
| `outcome` | String | |
| `started_at` | Timestamp | |
| `ended_at` | Timestamp | |
| `archived_at` | Timestamp | |

### `audit_log`
| Column | Type | Notes |
|--------|------|-------|
| `audit_id` | String | PK |
| `conversation_id` | String | FK |
| `agent_name` | String | |
| `audit_type` | String | |
| `findings` | JSON | |
| `risk_level` | String | |
| `human_review_required` | Boolean | |
| `audited_at` | Timestamp | |

---

## Audio Storage (GCS)

**Bucket**: `gs://ask-mary-audio/`

```
gs://ask-mary-audio/
├── {trial_id}/
│   └── {participant_id}/
│       └── {conversation_id}.wav
```

- **Access**: IAM for service accounts, signed URLs (1h TTL) for dashboard playback
- **Path stored in**: `conversations.audio_gcs_path`
- **Signed URL generation**: `src/services/gcs_client.py`

---

## Key Design Decisions

1. **`mary_id`** = HMAC-SHA256(canonical(first+last+dob+phone), pepper) — deterministic dedup while preventing rainbow table attacks
2. **`phone` NOT UNIQUE** — caregivers/family share phones; identity resolved via `mary_id`
3. **`events` append-only** — no UPDATE/DELETE; idempotency keys prevent duplicates
4. **`agent_reasoning` separate from `conversations`** — PHI/audit isolation
5. **`participant_trials` junction** — multi-trial enrollment with per-trial screening state
6. **`provenance` tracking** — every data point tagged with source (patient_stated | ehr | coordinator | system)
7. **Annotate-don't-overwrite** — screening responses keep history via `{key}_history` arrays
