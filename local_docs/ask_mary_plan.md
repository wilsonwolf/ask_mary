# Ask Mary: AI Clinical Trial Scheduling Agent

## Complete Architecture, PRD, and Implementation Plan

---

## Table of Contents

1. [Structured Prompt (XML)](#1-structured-prompt-xml)
2. [Product Requirements Document](#2-product-requirements-document)
3. [Architecture](#3-architecture)
4. [API & Service Verification](#4-api--service-verification)
5. [Agent SDK Recommendation](#5-agent-sdk-recommendation)
6. [Data Model](#6-data-model)
7. [Safety, Evaluation & Observability](#7-safety-evaluation--observability)
8. [DevOps & Deployment](#8-devops--deployment)
9. [12-Hour Implementation Plan](#9-12-hour-implementation-plan)
10. [Risk Register](#10-risk-register)
11. [Open Questions](#11-open-questions)

---

## 1. Structured Prompt (XML)

This is the master prompt that can be fed to any agent coding tool (Claude Code, Cursor, Codex) to bootstrap work on any part of the system. Each `<module>` is self-contained enough to be built independently.

```xml
<project name="ask_mary" type="hackathon-mvp" timeframe="12h">

  <goal>
    Build a scalable, working demo of an AI scheduling agent for clinical trials
    that interacts with participants via voice and text (WhatsApp, SMS) to
    recruit, vet, schedule, transport, and remind trial participants.
  </goal>

  <constraints>
    <constraint id="C1">12-hour hackathon window — prioritize working demo over polish</constraint>
    <constraint id="C2">Must be cloud-hosted from the start (not localhost-only)</constraint>
    <constraint id="C3">Multi-agent architecture for safety-critical checking</constraint>
    <constraint id="C4">Python preferred; other languages only if strictly superior</constraint>
    <constraint id="C5">Hybrid data layer: Cloud SQL (Postgres) for operational/transactional state; Databricks (Delta Lake) for analytics, EHR, trial metadata, ML, and reporting</constraint>
    <constraint id="C6">Must support autonomous maintenance by agent coding tools</constraint>
    <constraint id="C7">Git worktree usage, prod/dev separation, gradual deployment</constraint>
  </constraints>

  <available_credits>
    <service name="ElevenLabs" use="Voice agent — real-time conversational AI + Twilio phone integration"/>
    <service name="Databricks" use="Analytics DB (Delta Lake), EHR data, trial metadata, MLflow observability, transcript analysis"/>
    <service name="Google Cloud" use="Cloud Run (compute), Cloud SQL Postgres (operational DB), Cloud Tasks (job queue), Artifact Registry, Secret Manager"/>
    <service name="Lovable" use="Frontend dashboard generation (React/TypeScript)"/>
    <service name="Cursor" use="IDE for rapid development"/>
    <service name="Claude Code" use="Agent coding — implementation, planning, iteration"/>
    <service name="OpenAI" use="Agent SDK, backup LLM, Codex for code review"/>
  </available_credits>

  <workflow description="Participant recruitment and scheduling pipeline (v2)">

    <step id="S0" name="setup_configuration" phase="pre-demo">
      <description>
        Trial + site configuration. Visit templates (screening/baseline types,
        durations, buffers, hours). Comms templates stored as config files in repo
        (disclosure, prep, confirm, day-of, rescue, protocol-change broadcast).
      </description>
      <data_sources>trials table (Databricks — reference), comms_templates/ config dir (repo)</data_sources>
    </step>

    <step id="S1" name="outreach_and_consent">
      <description>
        Initiate contact with trial-eligible participants from roster/EHR data.
        Enforce DNC flags (DNC_ALL, DNC_SMS, DNC_VOICE) before any outbound.
        Mention transport support early to increase conversion.
        Retry cadence: Voice #1 → SMS nudge → Voice #2 (diff time) → Voice #3 + final SMS.
        Log each attempt + outcome in events table.
      </description>
      <agents>outreach_agent</agents>
      <apis>ElevenLabs Conversational AI, Twilio (SMS/WhatsApp/Voice)</apis>
      <gates>
        <gate id="G1" name="disclosure" required="true">
          Voice: "automated assistant" + "may be recorded" + "OK to continue?"
          SMS: org identity + purpose + "Reply STOP to opt out"
          Store: disclosed_automation, consent_to_continue, consent_sms, ok_to_leave_voicemail
        </gate>
      </gates>
      <contactability>
        primary_phone, secondary_phone, preferred_channel, best_time_to_reach,
        language, ok_to_leave_voicemail, permitted_voicemail_name
      </contactability>
    </step>

    <step id="S2" name="identity_verification">
      <description>
        Verify identity via DOB + ZIP (or equivalent) before any PHI or trial
        specifics are shared. Detect duplicates by phone + DOB. If wrong person:
        do not disclose anything, mark wrong_person, suppress further outreach.
      </description>
      <agents>identity_agent</agents>
      <data_sources>participants table (Postgres)</data_sources>
      <gates>
        <gate id="G2" name="identity" required="true">
          No trial details, no disease details until identity verified.
        </gate>
      </gates>
    </step>

    <step id="S3" name="screening_and_education">
      <description>
        High-level trial summary (non-promissory): time commitment, location,
        compensation/transport support. Pre-screen with hard excludes first.
        Collect responses to eligibility questions. Cross-reference vs EHR data.
        Correct by annotation (never overwrite source data).
        Output: ELIGIBLE | PROVISIONAL | INELIGIBLE | NEEDS_HUMAN with reasons + confidence.
        Answer only approved FAQs; medical advice → handoff.
        Caregiver/third-party: capture authorized contact, relationship, scope.
        Ineligible: neutral close, ask permission for future trials, apply DNC if requested.
      </description>
      <agents>screening_agent</agents>
      <data_sources>trials (Databricks), participant_ehr (Databricks), participants (Postgres)</data_sources>
      <provenance>patient_stated | ehr | coordinator | system</provenance>
    </step>

    <step id="S3.5" name="handoff_triggers" phase="realtime">
      <description>
        GLOBAL safety triggers checked on EVERY agent response (blocking pre-check).
        Triggers: medical advice request, severe symptoms, adverse event report,
        consent confusion/withdrawal, anger/threats, repeated misunderstanding,
        language mismatch.
        Output: HANDOFF_NOW | CALLBACK_TICKET | STOP_CONTACT.
        On trigger: write to handoff_queue (Postgres) with all coordinator fields.
        Latency budget: must complete in under 200ms. If too slow, move to
        parallel check with interrupt (post-MVP).
      </description>
      <agents>safety_gate (inline check on every agent response)</agents>
      <data_sources>handoff_queue (Postgres)</data_sources>
    </step>

    <step id="S4" name="cross_reference_and_recheck">
      <description>
        Compare participant-stated responses to data on file. Flag discrepancies
        for human review. Correct by annotation with provenance, never overwrite.
        Schedule re-check: set next_action_at = now + 2 weeks with
        action_type = reverify. Log in events table.
      </description>
      <agents>adversarial_checker_agent</agents>
      <schedule>Cloud Tasks: T+14 days after screening</schedule>
    </step>

    <step id="S5" name="geo_site_selection_and_scheduling">
      <description>
        Confirm address + ZIP + derive participant timezone.
        Geo/distance protocol gate: compute distance to site; if outside protocol
        max, offer alternate site or mark ineligible-distance and close.
        Collect availability windows + constraints (work/caregiver schedule).
        Book slot → status BOOKED with 12-hour confirmation window.
        T+11h: automated confirmation prompt ("Reply YES or RESCHEDULE").
        On confirmation → CONFIRMED. On 12h timeout → release slot, log
        expired_unconfirmed, create follow-up task.
        Teach-back: participant repeats date/time/location + key prep. If fails
        twice → handoff.
        All times stored UTC, rendered in participant/site timezone.
        Full status: BOOKED → CONFIRMED → COMPLETED | NO_SHOW | CANCELLED.
      </description>
      <agents>scheduling_agent</agents>
      <apis>Google Calendar API (MCP server)</apis>
    </step>

    <step id="S6" name="transportation_closed_loop">
      <description>
        Mention transport support early (step S1/S3) to increase conversion.
        Capture pickup address (confirm vs EHR), offer alternative pickup.
        T-24h and T-2h: reconfirm pickup location.
        Day-of exception handling: driver can't find participant, participant
        late → escalation/handoff. Return trip rules if applicable.
        Log transport_failure_reason when issues occur.
      </description>
      <agents>transport_agent</agents>
      <apis>Uber Health API (mock for MVP)</apis>
    </step>

    <step id="S7" name="comms_engine">
      <description>
        Event-driven comms beyond simple reminders. All outbound actions are
        idempotent (idempotency keys) and logged to events table.
        Cadence:
          T-48h: prep instructions (ID, fasting, parking, arrival time)
          T-24h: confirmation prompt (YES / RESCHEDULE)
          T-2h:  day-of check-in + transport ping + "running late?" path
          T+0 (no-show): rescue flow + reason capture
        Protocol change broadcast: send update + capture acknowledgement.
        Unreachable workflow: if comms bounce/fail repeatedly → mark
        contactability_risk → switch channel if allowed → create coordinator task.
      </description>
      <agents>comms_agent</agents>
      <apis>Twilio (SMS/WhatsApp/Voice), ElevenLabs</apis>
      <cadence>
        <reminder offset="-48h" channels="sms,whatsapp">Prep instructions</reminder>
        <reminder offset="-24h" channels="sms,whatsapp">Confirmation prompt (YES/RESCHEDULE)</reminder>
        <reminder offset="-2h" channels="sms">Day-of check-in + transport ETA</reminder>
        <reminder offset="+0h" channels="voice,sms">No-show rescue + reschedule</reminder>
      </cadence>
    </step>

    <step id="S8" name="handoff_queue">
      <description>
        Structured handoff tasks for human coordinators.
        Fields: participant_id, reason, severity, summary, recommended_next_action,
        created_at, due_at, coordinator_phone, callback_number, priority,
        language, preferred_callback_window.
        SLA: HANDOFF_NOW (safety) → immediate. CALLBACK_TICKET → 2 business hours.
        Handoff packet: identity status, consent+DNC flags, screening answers,
        conflicts, appointment/transport details, language.
        MVP: surface in dashboard. Post-MVP: trigger outbound alert to coordinator.
      </description>
      <data_sources>handoff_queue (Postgres)</data_sources>
    </step>

    <step id="S9" name="outcomes_and_analytics">
      <description>
        Capture: attended / cancelled / rescheduled / no_show + standardized reason codes.
        Feed insights back: top no-show reasons, distance failures, transport
        failures, best channel/time to reach.
        All events streamed to Databricks for reporting and ML model improvement.
      </description>
      <data_sources>events (Postgres → Pub/Sub → Databricks)</data_sources>
    </step>

  </workflow>

  <transcript_storage non_negotiable="true">
    Full conversation transcripts (voice + text) MUST be stored — required for
    clinical audit and physician review. Stored in conversations table (Postgres)
    with structured metadata. Async copy to Databricks for ML analysis.
    Audio recordings stored in GCS bucket with access controls.
    Retention: per-trial default = trial duration + regulatory hold period.
    Real-time and historical monitoring via dashboard + SQL query access.
  </transcript_storage>

  <agents>
    <agent name="orchestrator" role="Central coordinator — routes conversations, enforces gate sequence">
      <sdk>OpenAI Agents SDK (handoff pattern)</sdk>
    </agent>
    <agent name="outreach_agent" role="Initiates contact, enforces DNC, manages retry cadence">
      <sdk>OpenAI Agents SDK</sdk>
      <tools>Twilio, ElevenLabs</tools>
    </agent>
    <agent name="identity_agent" role="Verifies identity (DOB+ZIP), detects duplicates/wrong-person">
      <sdk>OpenAI Agents SDK</sdk>
    </agent>
    <agent name="screening_agent" role="Eligibility screening, FAQ, caregiver auth, annotate-don't-overwrite">
      <sdk>OpenAI Agents SDK</sdk>
    </agent>
    <agent name="adversarial_checker_agent" role="Re-checks eligibility (different phrasing), cross-references EHR">
      <sdk>OpenAI Agents SDK</sdk>
    </agent>
    <agent name="scheduling_agent" role="Geo gate, slot booking, 12h confirmation window, teach-back">
      <sdk>OpenAI Agents SDK</sdk>
      <tools>Google Calendar MCP</tools>
    </agent>
    <agent name="transport_agent" role="Uber ride booking, pickup verification, day-of exception handling">
      <sdk>OpenAI Agents SDK</sdk>
      <tools>Uber Health API (mock)</tools>
    </agent>
    <agent name="comms_agent" role="Reminder cadence, confirmation prompts, no-show rescue, unreachable workflow">
      <sdk>OpenAI Agents SDK</sdk>
      <tools>Twilio, Cloud Tasks</tools>
    </agent>
    <agent name="supervisor_agent" role="Post-call transcript audit, compliance check, deception detection">
      <sdk>OpenAI Agents SDK</sdk>
    </agent>
    <agent name="safety_gate" role="Inline blocking pre-check on every agent response for handoff triggers">
      <sdk>Inline function (not a full agent — runs in &lt;200ms)</sdk>
    </agent>
  </agents>

  <tech_stack>
    <backend language="python" framework="FastAPI" agent_sdk="OpenAI Agents SDK"/>
    <voice platform="ElevenLabs Conversational AI 2.0" telephony="Twilio"/>
    <database_operational platform="Cloud SQL (Postgres)" connector="asyncpg + SQLAlchemy"
      purpose="Transactional state: participants, appointments, rides, conversations, events, handoff_queue"/>
    <database_analytics platform="Databricks" format="Delta Lake" connector="databricks-sql-connector"
      purpose="Analytics: trials (ref), participant_ehr, conversation_transcripts, audit_log, ML models"/>
    <event_bridge from="Postgres" to="Databricks" method="Pub/Sub CDC"/>
    <audio_storage platform="Google Cloud Storage" bucket="ask-mary-audio" access="IAM + signed URLs"/>
    <comms_templates location="repo: comms_templates/*.yaml" format="YAML with Jinja2 variables"/>
    <frontend generator="Lovable" framework="React/TypeScript" host="Firebase Hosting"/>
    <observability primary="Langfuse" secondary="Databricks MLflow"/>
    <deployment platform="Google Cloud Run" containerization="Docker" registry="Artifact Registry"/>
    <job_queue platform="Cloud Tasks" purpose="Timed reminders, slot expiry, re-check scheduling"/>
    <ci_cd git="worktrees" branching="main(prod)/dev/feature" rollback="gradual"/>
  </tech_stack>

  <safety>
    <requirement id="SAFE1">Blocking pre-check on every agent response for handoff triggers (&lt;200ms)</requirement>
    <requirement id="SAFE2">Disclosure + consent-to-engage gate MUST pass before conversation proceeds</requirement>
    <requirement id="SAFE3">Identity verification (DOB+ZIP) MUST pass before any PHI/trial details shared</requirement>
    <requirement id="SAFE4">DNC flags enforced before any outbound; if channel blocked, switch or stop</requirement>
    <requirement id="SAFE5">All data corrections by annotation with provenance — never overwrite source</requirement>
    <requirement id="SAFE6">Deception/inconsistency detection on all screening transcripts</requirement>
    <requirement id="SAFE7">Full conversation transcripts stored (non-negotiable) for clinical audit</requirement>
    <requirement id="SAFE8">All outbound actions idempotent with idempotency keys logged to events</requirement>
    <requirement id="SAFE9">Immutable test suite — safety scenarios that cannot be deleted</requirement>
    <requirement id="SAFE10">Gradual deployment — canary pattern to catch regressions</requirement>
  </safety>

</project>
```

---

## 2. Product Requirements Document

### 2.1 Problem Statement

Clinical trial recruitment suffers from high participant dropout, scheduling friction, and transportation barriers. Current recruitment agency workflows are manual, phone-tag-heavy, and poorly instrumented. Participants forget appointments, face transportation challenges, and provide inconsistent information. Coordinators juggle spreadsheets and phone calls with no structured handoff process.

### 2.2 Solution

**Ask Mary** is an AI scheduling agent that automates the participant recruitment pipeline for clinical trials via voice and text. It handles outreach (with DNC enforcement), consent capture, identity verification, eligibility screening, appointment scheduling (with geo gates and confirmation windows), transportation arrangement, event-driven communications, and structured coordinator handoffs — with built-in safety gates, adversarial checking, and full audit trails.

### 2.3 Users

| User | Role | Interaction |
|------|------|-------------|
| **Participant** | Trial candidate | Voice calls, SMS, WhatsApp |
| **Nurse Coordinator** | Provider-side scheduler | Dashboard, calendar integration, handoff queue |
| **Principal Investigator (PI)** | Trial lead | Dashboard (read-only), alerts |
| **Recruiting Agency Admin** | System operator | Dashboard, configuration, reports |

### 2.4 MVP Feature Set (12-hour scope)

| Priority | Feature | Status |
|----------|---------|--------|
| P0 | Voice agent for participant screening call (ElevenLabs + Twilio) | Must have |
| P0 | DNC enforcement + disclosure/consent gate (S1) | Must have |
| P0 | Identity verification — DOB + ZIP, wrong-person handling (S2) | Must have |
| P0 | Eligibility screening with criteria matching + EHR cross-reference (S3) | Must have |
| P0 | Safety gate — blocking pre-check on every response with handoff triggers (S3.5) | Must have |
| P0 | Geo/distance gate + appointment scheduling with Google Calendar (S5) | Must have |
| P0 | 12-hour confirmation window (BOOKED → CONFIRMED flow) | Must have |
| P0 | Event-driven comms cadence — prep, confirm, day-of, no-show rescue (S7) | Must have |
| P0 | Append-only events log with provenance + idempotency keys | Must have |
| P0 | Handoff queue with severity routing + SLA tracking (S8) | Must have |
| P1 | Uber Health ride booking (mocked) with transport exception handling (S6) | Should have |
| P1 | Admin dashboard — pipeline view, handoff tickets, conversation logs (Lovable) | Should have |
| P1 | Post-call supervisor agent audit + deception detection | Should have |
| P1 | Teach-back confirmation before booking finalized | Should have |
| P2 | Adversarial re-screening — 2-week follow-up via Cloud Tasks (S4) | Nice to have |
| P2 | Unreachable workflow — channel switching + coordinator escalation | Nice to have |
| P2 | Full Langfuse observability integration | Nice to have |
| P2 | Audio recording storage in GCS with dashboard playback | Nice to have |

### 2.5 Non-Functional Requirements

- **Latency**: Voice response < 1 second; safety gate < 200ms (critical for natural conversation)
- **Availability**: Cloud-hosted, accessible via phone number for demo
- **Security**: No PHI shared before identity verification passes; DNC enforced before any outbound
- **Auditability**: Full conversation transcripts + append-only events log with provenance; audio recordings stored in GCS
- **Idempotency**: All outbound actions (SMS, voice, transport) use idempotency keys to prevent duplicates
- **Safety**: Blocking handoff triggers on every agent response; consent gates; geo/distance protocol enforcement
- **Maintainability**: Code structured for autonomous agent maintenance; comms templates as config files

---

## 3. Architecture

### 3.1 System Architecture (High-Level)

```mermaid
graph TB
    subgraph "Participant Channels"
        PHONE["Phone Call<br/>(Twilio)"]
        SMS["SMS<br/>(Twilio)"]
        WA["WhatsApp<br/>(Twilio)"]
    end

    subgraph "Voice Layer"
        EL["ElevenLabs<br/>Conversational AI 2.0"]
        TW_VOICE["Twilio Voice<br/>(SIP/WebSocket)"]
    end

    subgraph "Agent Orchestration Layer (OpenAI Agents SDK)"
        ORCH["Orchestrator Agent<br/>(Manager Pattern)"]
        OUTREACH_AGT["Outreach<br/>Agent"]
        ID_AGT["Identity<br/>Agent"]
        SCREEN_AGT["Screening<br/>Agent"]
        SCHED_AGT["Scheduling<br/>Agent"]
        TRANS_AGT["Transport<br/>Agent"]
        COMMS_AGT["Comms<br/>Agent"]
    end

    subgraph "Safety Layer"
        SAFETY_GATE["Safety Gate<br/>(inline pre-check<br/>&lt;200ms)"]
        SUPER["Supervisor<br/>Agent"]
        ADVERS["Adversarial<br/>Checker"]
    end

    subgraph "External Services"
        GCAL["Google Calendar<br/>(MCP Server)"]
        UBER["Uber Health<br/>API (mock)"]
    end

    subgraph "Operational DB (Cloud SQL Postgres)"
        PG_PARTS["participants"]
        PG_APPTS["appointments"]
        PG_CONVOS["conversations<br/>(+ full transcripts)"]
        PG_EVENTS["events<br/>(append-only log)"]
        PG_HANDOFF["handoff_queue"]
        PG_RIDES["rides"]
    end

    subgraph "Audio Storage"
        GCS["GCS Bucket<br/>(call recordings,<br/>IAM + signed URLs)"]
    end

    subgraph "Analytics DB (Databricks Delta Lake)"
        DB_TRIALS["trials<br/>(reference)"]
        DB_EHR["participant_ehr<br/>(source data)"]
        DB_ARCHIVE["conversations_archive<br/>(ML analysis)"]
        DB_AUDIT["audit_log"]
        DB_ANALYTICS["reporting &<br/>ML models"]
    end

    subgraph "Job Queue"
        CT["Cloud Tasks<br/>(confirmation checks,<br/>reminders, retries,<br/>slot expiry, re-check)"]
    end

    subgraph "Event Bridge"
        PS["Pub/Sub<br/>(Postgres → Databricks<br/>CDC stream)"]
    end

    subgraph "Observability"
        LF["Langfuse<br/>Tracing"]
        MLF["MLflow<br/>Metrics"]
    end

    subgraph "Frontend"
        DASH["Admin Dashboard<br/>(Lovable → React)"]
    end

    PHONE --> TW_VOICE --> EL
    EL --> ORCH
    SMS --> ORCH
    WA --> ORCH

    ORCH -->|handoff| OUTREACH_AGT
    ORCH -->|handoff| ID_AGT
    ORCH -->|handoff| SCREEN_AGT
    ORCH -->|handoff| SCHED_AGT
    ORCH -->|handoff| TRANS_AGT
    ORCH -->|handoff| COMMS_AGT

    ORCH -.->|every response| SAFETY_GATE
    SAFETY_GATE -->|trigger| PG_HANDOFF

    SCREEN_AGT --> ADVERS
    ORCH --> SUPER

    SCHED_AGT --> GCAL
    TRANS_AGT --> UBER

    OUTREACH_AGT --> PG_PARTS
    ID_AGT --> PG_PARTS
    SCREEN_AGT --> PG_PARTS
    SCREEN_AGT --> DB_TRIALS
    SCREEN_AGT --> DB_EHR
    SCHED_AGT --> PG_APPTS
    TRANS_AGT --> PG_RIDES
    COMMS_AGT --> CT
    CT --> COMMS_AGT
    ORCH --> PG_CONVOS
    ORCH --> PG_EVENTS
    PG_CONVOS --> GCS
    SUPER --> DB_AUDIT

    PG_EVENTS -->|stream| PS
    PG_CONVOS -->|stream| PS
    PG_APPTS -->|stream| PS
    PS --> DB_ARCHIVE
    PS --> DB_ANALYTICS

    ORCH --> LF
    LF --> MLF

    DASH --> PG_PARTS
    DASH --> PG_APPTS
    DASH --> PG_HANDOFF
    DASH --> PG_CONVOS
    DASH --> DB_ANALYTICS
```

### 3.2 Agent Orchestration Flow (v2)

```mermaid
sequenceDiagram
    participant P as Participant
    participant TW as Twilio
    participant EL as ElevenLabs
    participant O as Orchestrator
    participant OUT as Outreach Agent
    participant SG as Safety Gate
    participant ID as Identity Agent
    participant SC as Screening Agent
    participant SH as Scheduling Agent
    participant TR as Transport Agent
    participant CM as Comms Agent
    participant SV as Supervisor Agent
    participant PG as Postgres
    participant DB as Databricks
    participant CT as Cloud Tasks

    Note over OUT,PG: S1 — Outreach & Consent
    OUT->>PG: Check DNC flags
    alt DNC flag set
        OUT->>PG: Log event (outreach_blocked)
        Note over OUT: STOP — do not contact
    else No DNC
        OUT->>TW: Initiate call / SMS
        TW->>EL: Audio stream (voice)
        EL->>O: Transcribed intent

        O->>P: Disclosure: "automated assistant, may be recorded"
        P->>O: Consents to continue
        O->>PG: Store consent flags + log event
    end

    Note over O,SG: S3.5 — Safety gate runs on EVERY agent response
    O->>SG: Pre-check (blocking, <200ms)
    alt Handoff trigger detected
        SG->>PG: Write to handoff_queue
        SG->>PG: Log event (handoff_created)
        Note over SG: Transfer to coordinator
    end

    Note over ID,PG: S2 — Identity Verification
    O->>ID: Handoff → verify identity
    ID->>PG: Fetch participant (sub-ms)
    ID->>P: "Confirm DOB and ZIP?"
    P->>ID: Provides DOB + ZIP
    ID->>PG: Validate (detect duplicate/wrong person)
    alt Wrong person
        ID->>PG: Mark wrong_person, suppress outreach
    else Verified
        ID->>PG: Set identity_status=verified, log event
        ID-->>O: Identity verified ✓
    end

    Note over SC,DB: S3 — Screening & Education
    O->>SC: Handoff → eligibility screening
    SC->>P: Trial summary (non-promissory) + transport mention
    SC->>DB: Fetch trial criteria + EHR data
    SC->>P: Hard exclude questions first, then eligibility Qs
    P->>SC: Answers
    SC->>PG: Annotate screening_responses (provenance: patient_stated)
    SC->>DB: Cross-reference EHR — flag discrepancies
    SC->>PG: Set eligibility_status + log event
    SC-->>O: ELIGIBLE | PROVISIONAL | INELIGIBLE | NEEDS_HUMAN

    alt Eligible
        Note over SH,PG: S5 — Geo Gate + Scheduling
        O->>SH: Handoff → schedule
        SH->>PG: Get participant address + ZIP → derive timezone
        SH->>DB: Get trial max_distance_km
        alt Distance exceeds protocol max
            SH->>PG: Mark ineligible-distance, log event
            SH-->>O: Geo gate failed
        else Within range
            SH->>P: Collect availability windows
            SH->>PG: Hold slot (SELECT FOR UPDATE)
            SH->>P: Confirm date/time/location
            SH->>P: Teach-back: "repeat back date, time, location, key prep"
            SH->>PG: Book appointment (status=BOOKED, confirmation_due=+12h)
            SH->>CT: Schedule confirmation check at T+11h
            SH->>PG: Log event (slot_booked)
        end

        Note over TR,PG: S6 — Transportation
        O->>TR: Handoff → arrange transport
        TR->>P: "Confirm pickup at [address on file]?"
        P->>TR: Confirms or provides alternative
        TR->>PG: Create ride + log event
        TR->>CT: Schedule T-24h and T-2h reconfirmation

        Note over CM,CT: S7 — Comms Engine (async)
        CM->>CT: Schedule T-48h prep, T-24h confirm, T-2h check-in
    end

    O->>PG: Save conversation + full transcript
    O->>PG: Log event (conversation.ended)
    PG-->>DB: Pub/Sub → conversations_archive + events

    Note over SV,DB: Post-call audit
    O->>SV: Audit transcript
    SV->>DB: Compliance check + deception analysis
    SV->>DB: Write audit_log
```

### 3.3 Appointment Confirmation & Comms Lifecycle

```mermaid
stateDiagram-v2
    [*] --> SlotBooked: Appointment created (S5)

    state "BOOKED" as SlotBooked
    state "12h Confirmation Window" as ConfWindow {
        SlotBooked --> PrepSent: T-48h
        PrepSent --> ConfirmPrompt: T-24h (or T+11h if recent)
        ConfirmPrompt --> WaitForReply: SMS/WhatsApp "YES or RESCHEDULE"

        WaitForReply --> Confirmed: Participant replies YES
        WaitForReply --> RescheduleFlow: Participant replies RESCHEDULE
        WaitForReply --> SlotExpired: 12h timeout (no reply)
    }

    state "CONFIRMED" as Confirmed
    state "Comms Cadence" as CommsCadence {
        Confirmed --> TransportReconfirm24: T-24h reconfirm pickup
        TransportReconfirm24 --> DayOfCheckin: T-2h check-in + transport ETA
        DayOfCheckin --> RunningLate: "Running late?" path
        RunningLate --> DayOfCheckin: Updated ETA
    }

    state "Outcomes" as Outcomes {
        DayOfCheckin --> Completed: Participant arrives
        DayOfCheckin --> NoShow: Participant doesn't arrive
        NoShow --> RescueFlow: T+0 voice/SMS rescue
        RescueFlow --> Rescheduled: Agrees to reschedule
        RescueFlow --> ReasonCaptured: Captures no-show reason
    }

    SlotExpired --> FollowUpTask: Release slot, log expired_unconfirmed
    FollowUpTask --> [*]: Coordinator follow-up

    RescheduleFlow --> SlotBooked: New slot booked

    Rescheduled --> SlotBooked: New appointment

    state "Transport Exception" as TransportEx {
        TransportReconfirm24 --> TransportFailed: Driver issue / participant late
        TransportFailed --> HandoffQueue: Escalate to coordinator
    }

    state "Unreachable Workflow" as Unreachable {
        ConfirmPrompt --> ChannelSwitch: Comms bounce/fail
        ChannelSwitch --> CoordinatorTask: Still unreachable
        CoordinatorTask --> HandoffQueue: contactability_risk=high
    }

    Completed --> [*]: Log outcome + reason code
    ReasonCaptured --> [*]: Log standardized reason
    HandoffQueue --> [*]: Coordinator resolves
```

### 3.4 Deployment Architecture

```mermaid
graph LR
    subgraph "Development"
        DEV_BRANCH["dev branch<br/>(git worktree)"]
        CC["Claude Code<br/>(implement)"]
        CODEX["OpenAI Codex<br/>(review)"]
    end

    subgraph "CI/CD"
        GH["GitHub Actions"]
        TESTS["Immutable<br/>Test Suite"]
        SAFETY["Safety<br/>Eval Suite"]
    end

    subgraph "Google Cloud Platform"
        AR["Artifact Registry<br/>(Docker images)"]
        subgraph "Staging"
            STG_API["Cloud Run<br/>API (staging)"]
            STG_WORKER["Cloud Run<br/>Worker (staging)"]
        end
        subgraph "Production"
            PROD_API["Cloud Run<br/>API (prod)"]
            PROD_WORKER["Cloud Run<br/>Worker (prod)"]
        end
        FB["Firebase Hosting<br/>(Dashboard)"]
        DB_CLOUD["Databricks<br/>(Cloud)"]
    end

    CC --> DEV_BRANCH
    DEV_BRANCH --> GH
    CODEX -->|review| GH
    GH --> TESTS
    GH --> SAFETY
    TESTS -->|pass| AR
    AR -->|deploy| STG_API
    AR -->|deploy| STG_WORKER
    STG_API -->|canary promote| PROD_API
    STG_WORKER -->|canary promote| PROD_WORKER
    PROD_API --> DB_CLOUD
    FB --> PROD_API
```

### 3.5 Voice Pipeline (Latency-Optimized)

```mermaid
graph LR
    A["Participant speaks<br/>(phone)"] -->|PSTN| B["Twilio<br/>(SIP trunk)"]
    B -->|WebSocket<br/>audio stream| C["ElevenLabs<br/>Conv AI 2.0"]
    C -->|STT + LLM<br/>reasoning| D["Agent Response<br/>(text)"]
    D -->|TTS<br/>sub-second| E["ElevenLabs<br/>Voice Synthesis"]
    E -->|WebSocket<br/>audio| B
    B -->|PSTN| A

    style C fill:#f9f,stroke:#333
    style D fill:#ff9,stroke:#333

    note1["End-to-end target: < 1.5s"]
```

**Key latency decision**: ElevenLabs Conversational AI 2.0 handles STT + LLM reasoning + TTS in a single pipeline with sub-second turnaround. The LLM backing the voice agent can be Claude or GPT — configured in the ElevenLabs dashboard. Our specialized agents run as tool calls within that LLM context, keeping everything in-stream rather than adding network hops.

---

## 4. API & Service Verification

### 4.1 Verified APIs and MCP Servers

| Service | API Available | MCP Server | Python SDK | Auth | HIPAA Ready | Notes |
|---------|:---:|:---:|:---:|------|:---:|-------|
| **ElevenLabs** | Yes | N/A (native integration) | `elevenlabs` | API key | **Yes** (Enterprise tier) | Conv AI 2.0 with native Twilio integration. Sub-second latency. BAA available on Enterprise plan. Zero-retention mode + TLS encryption + PHI recognition. |
| **Twilio** | Yes | Yes (official Alpha) | `twilio` | Account SID + Auth Token | **Yes** (Security/Enterprise Edition) | SMS, WhatsApp, Voice all HIPAA-eligible. BAA requires Security or Enterprise Edition. Programmable Voice, SIP, SMS all covered. |
| **Uber Health** | Yes | No (build custom or REST) | REST API | OAuth2 (Uber for Business) | **Yes** (native) | Built specifically for healthcare. HIPAA-compliant endpoint. ePHI controls built-in. Patients don't need Uber account. **Requires partnership/account.** |
| **Google Calendar** | Yes | Yes (multiple community) | `google-api-python-client` | OAuth2 (service account) | **Partial** (with BAA) | Covered under Google Workspace BAA as of Sep 2025. **Caveat**: Third-party API access (our MCP server) is NOT covered by Google's BAA — we must treat calendar data carefully. |
| **Databricks** | Yes | Yes (managed + community) | `databricks-sql-connector` | Token/OAuth | **Yes** (Compliance Security Profile) | BAA available. Compliance Security Profile enables HIPAA. Encryption at rest + in transit. SQL Serverless is HIPAA certified on AWS and Azure. |
| **OpenAI API** | Yes | Built-in MCP support | `openai-agents` | API key | **Yes** (with BAA + zero retention) | BAA available (email baa@openai.com). Requires zero-retention API endpoints. Not limited to Enterprise plan. |
| **Langfuse** | Yes | N/A | `langfuse` | API key | **Yes** (Cloud or self-hosted) | HIPAA-compliant cloud region available. BAA offered. Self-hosted option for full control. PHI safeguards documented. |
| **Cloud SQL (Postgres)** | Yes | N/A | `asyncpg` + `SQLAlchemy` | IAM/password | **Yes** (with BAA) | GCP HIPAA-eligible. Encryption at rest + in transit. Row-level security, ACID transactions, sub-ms latency. |
| **Google Cloud Run** | Yes | N/A | `google-cloud-run` | IAM/Service Account | **Yes** (with BAA) | GCP is HIPAA-eligible. Cloud Run covered under GCP BAA. Encryption at rest + in transit. IAM + VPC Service Controls available. |


### 4.2 Uber Health: Hackathon Mitigation

Uber Health requires an enterprise partnership. For the hackathon MVP:
- **Option A**: Apply for Uber Health sandbox/test account (may not be instant)
- **Option B**: Mock the Uber Health API with a stub service that simulates ride booking, and flag this as a TODO for production integration
- **Option C**: Use standard Uber API (less HIPAA-focused) if available

**Recommendation**: Option B for hackathon speed, with a well-defined interface so the real API is a drop-in replacement.

---

## 5. Agent SDK Recommendation

### 5.1 Decision: OpenAI Agents SDK (primary) + ElevenLabs Conversational AI (voice)

| Framework | Pros | Cons | Verdict |
|-----------|------|------|---------|
| **OpenAI Agents SDK** | Multi-agent handoffs built-in; built-in tracing; MCP support; lightweight; Python-native; released Feb 2026 | Newer (less battle-tested); tied to OpenAI API by default | **Primary choice** |
| **Claude Agent SDK** | Same tooling as Claude Code; powerful; Python + TS | Alpha status (v0.1.31); heavier (bundles Claude Code CLI); designed more for coding agents than conversational agents | Use for agent-coded maintenance, not runtime |
| **LangGraph** | Mature; great observability via LangSmith; complex workflow support | Heavier dependency; steeper learning curve; overkill for hackathon | Skip for MVP |
| **CrewAI** | Easy role-based setup | Less control over handoff patterns; less tracing | Skip |

### 5.2 Why OpenAI Agents SDK

1. **Handoff pattern** maps perfectly to our workflow (Orchestrator → Identity → Screening → Scheduling → Transport)
2. **Built-in tracing** gives us observability without extra setup
3. **MCP server support** lets us plug in Google Calendar and Databricks MCP servers directly
4. **Function tools** with Pydantic validation means rapid, type-safe tool development
5. **100+ LLM support** — we can swap in Claude models if needed
6. **Lightweight** — minimal overhead for hackathon speed

### 5.3 Claude Agent SDK Role

Use the Claude Agent SDK (and Claude Code) for the **development workflow** — not the runtime agent architecture:
- Claude Code for implementation and planning
- Codex (OpenAI) for reviewing implementation
- Claude Agent SDK for any automated code maintenance tasks

### 5.4 ElevenLabs Conversational AI Role

ElevenLabs handles the **voice layer**:
- Real-time STT → LLM → TTS pipeline
- Native Twilio phone number integration (both inbound and outbound)
- The backing LLM (Claude or GPT) runs our agent logic via server-side tool integration
- Handles conversational cues ("um", "ah") for natural turn-taking

---

## 6. Data Model

### 6.0 Hybrid Data Architecture

```mermaid
graph LR
    subgraph "Cloud SQL Postgres (OLTP)"
        direction TB
        PG["Operational State<br/>• participants<br/>• appointments<br/>• conversations<br/>• events (append-only)<br/>• handoff_queue<br/>• rides"]
    end

    subgraph "Pub/Sub Event Bridge"
        PS["CDC Events<br/>• events.* (all types)<br/>• conversation.ended<br/>• appointment.status_changed<br/>• handoff.created"]
    end

    subgraph "Databricks Delta Lake (OLAP)"
        direction TB
        DB["Analytics & Reference<br/>• trials (reference)<br/>• participant_ehr (source)<br/>• conversations_archive<br/>• audit_log<br/>• reporting views<br/>• ML models"]
    end

    subgraph "GCS Audio Storage"
        GCS["Audio Recordings<br/>• call recordings<br/>• voicemails<br/>• IAM + signed URLs"]
    end

    PG -->|"event stream"| PS
    PS -->|"ingest"| DB
    DB -->|"read reference<br/>data (trials, EHR)"| PG
    PG -->|"audio_url refs"| GCS
```

**Why this split:**

| Concern | Postgres (OLTP) | Databricks (OLAP) |
|---------|-----------------|-------------------|
| **Latency** | Sub-millisecond single-row reads | Seconds (warehouse cold start) |
| **Transactions** | Row-level locking, SERIALIZABLE | Optimistic concurrency (batch) |
| **Constraints** | UNIQUE, FK, CHECK — enforced by DB | No native enforcement |
| **Slot reservation** | `SELECT ... FOR UPDATE` holds slot | Not possible |
| **Double-booking prevention** | UNIQUE constraint on (trial, time, slot) | Must implement in application |
| **Event logging** | Append-only events table, indexed | Purpose-built for batch analytics |
| **Transcript storage** | Full text + metadata (live access) | Archived copy for ML analysis |
| **EHR data joins** | Too large, wrong format | Columnar, optimized |
| **Reporting dashboards** | Slow for aggregations | Fast, purpose-built |

### 6.1 Operational Tables (Cloud SQL Postgres)

These tables require transactional guarantees, low-latency access, and strong consistency.

```mermaid
erDiagram
    PARTICIPANTS ||--o{ CONVERSATIONS : has
    PARTICIPANTS ||--o{ APPOINTMENTS : has
    PARTICIPANTS ||--o{ RIDES : has
    PARTICIPANTS ||--o{ EVENTS : generates
    PARTICIPANTS ||--o{ HANDOFF_QUEUE : triggers
    APPOINTMENTS ||--o{ RIDES : has
    APPOINTMENTS ||--o{ EVENTS : generates

    PARTICIPANTS {
        uuid participant_id PK
        string trial_id FK
        string agency_id
        string first_name
        string last_name
        date date_of_birth
        string phone UK
        string secondary_phone
        string address_street
        string address_city
        string address_state
        string address_zip
        string timezone
        float distance_to_site_km
        string preferred_channel
        string best_time_to_reach
        string language
        string identity_status "unverified|verified|wrong_person"
        string eligibility_status "pending|eligible|provisional|ineligible|needs_human"
        float eligibility_confidence
        string pipeline_status "new|outreach|screening|scheduling|booked|confirmed|completed|no_show|cancelled|unreachable|dnc"
        jsonb screening_responses "annotated answers with provenance"
        jsonb ehr_discrepancies "flagged mismatches vs EHR"
        jsonb dnc_flags "DNC_ALL, DNC_SMS, DNC_VOICE per channel"
        jsonb contactability "ok_to_leave_voicemail, permitted_voicemail_name, etc."
        jsonb consent "disclosed_automation, consent_to_continue, consent_sms, consent_future_trials"
        jsonb caregiver "authorized_contact, relationship, scope, phone"
        string contactability_risk "none|low|high"
        integer outreach_attempt_count
        timestamptz next_action_at
        string next_action_type "outreach_retry|reverify|confirmation_check|follow_up"
        timestamptz recheck_scheduled_at
        boolean adversarial_recheck_done
        jsonb adversarial_results
        timestamp created_at
        timestamp updated_at
    }

    APPOINTMENTS {
        uuid appointment_id PK
        uuid participant_id FK
        string trial_id FK
        string visit_type "screening|baseline|follow_up"
        timestamptz scheduled_at
        string google_event_id UK
        string status "booked|confirmed|completed|no_show|cancelled|expired_unconfirmed"
        string site_address
        string site_name
        string prep_instructions
        integer estimated_duration_min
        timestamptz slot_held_until
        timestamptz confirmation_due_at "booked_at + 12h"
        boolean teach_back_passed
        integer teach_back_attempts
        string cancellation_reason
        string no_show_reason
        string outcome_reason_code "standardized codes"
        timestamptz slot_released_at
        timestamp created_at
        timestamp updated_at
    }

    CONVERSATIONS {
        uuid conversation_id PK
        uuid participant_id FK
        string trial_id
        string channel "voice|sms|whatsapp"
        string direction "inbound|outbound"
        string agent_name
        string call_sid UK
        string audio_url "GCS signed URL for voice recordings"
        float duration_seconds
        string status "active|completed|failed|transferred"
        jsonb full_transcript "ordered array of turns with speaker, text, timestamp"
        jsonb agent_reasoning "agent decisions + tool calls during conversation"
        jsonb summary "structured summary: outcome, next_steps, flags"
        string handoff_reason "null if no handoff occurred"
        timestamp started_at
        timestamp ended_at
    }

    EVENTS {
        uuid event_id PK
        uuid participant_id FK
        uuid appointment_id "nullable"
        uuid conversation_id "nullable"
        string trial_id
        string event_type "outreach_attempt|consent_captured|identity_verified|screening_completed|slot_booked|confirmation_sent|confirmation_received|slot_expired|reminder_sent|transport_booked|transport_failed|no_show|completed|cancelled|rescheduled|handoff_created|dnc_set|channel_switched|protocol_change_ack|teach_back_passed|teach_back_failed|unreachable_flagged"
        jsonb payload "event-specific data"
        string provenance "patient_stated|ehr|coordinator|system"
        string idempotency_key UK "prevents duplicate outbound actions"
        string channel "voice|sms|whatsapp|system"
        timestamp created_at
    }

    HANDOFF_QUEUE {
        uuid handoff_id PK
        uuid participant_id FK
        uuid conversation_id "nullable"
        string trial_id
        string reason "medical_advice|severe_symptoms|adverse_event|consent_withdrawal|anger_threats|repeated_misunderstanding|language_mismatch|geo_ineligible|unreachable|teach_back_failure"
        string severity "HANDOFF_NOW|CALLBACK_TICKET|STOP_CONTACT"
        string priority "critical|high|medium|low"
        string status "open|assigned|resolved|escalated"
        text summary "AI-generated summary of situation"
        string recommended_next_action
        string coordinator_phone
        string callback_number
        string language
        string preferred_callback_window
        jsonb handoff_packet "identity_status, consent+DNC, screening, conflicts, transport, etc."
        timestamptz due_at "SLA: HANDOFF_NOW=immediate, CALLBACK_TICKET=2 business hours"
        string assigned_to "nullable — coordinator name/id"
        timestamp created_at
        timestamp resolved_at
    }

    RIDES {
        uuid ride_id PK
        uuid appointment_id FK
        uuid participant_id FK
        string pickup_address
        string dropoff_address
        timestamptz scheduled_pickup_at
        string uber_ride_id
        string status "pending|confirmed|dispatched|completed|failed|cancelled"
        string failure_reason "nullable"
        boolean return_trip
        timestamp created_at
        timestamp updated_at
    }
```

**Key Postgres features used:**
- `uuid` primary keys (no sequential leaks)
- `UK` = UNIQUE constraints (prevent duplicate phone, double-booking, duplicate events via idempotency_key)
- `jsonb` for flexible data: screening responses (with provenance annotations), DNC flags, contactability, consent, caregiver info, handoff packets
- `timestamptz` for timezone-aware scheduling; all times stored UTC, rendered in participant/site timezone
- `slot_held_until` on appointments enables `SELECT ... FOR UPDATE` reservation pattern
- `confirmation_due_at` on appointments drives the 12-hour confirmation window (Cloud Tasks checks at T+11h and T+12h)
- `events` table is **append-only** — no UPDATE/DELETE, indexed on `(participant_id, event_type, created_at)` for fast lookups
- `handoff_queue` tracks SLA with `due_at` and status progression
- `pipeline_status` on participants tracks current workflow state across the full lifecycle
- `provenance` field on events distinguishes data source (patient_stated vs ehr vs coordinator vs system)
- `idempotency_key` on events prevents duplicate outbound actions (SMS, voice, transport bookings)
- Single `participants` table consolidates identity, screening, contactability, and consent — avoids JOINs on the hot path

### 6.2 Analytics Tables (Databricks Delta Lake)

These tables hold reference data, large-scale analysis, and reporting.

```mermaid
erDiagram
    TRIALS ||--o{ PARTICIPANT_EHR : enrolls
    CONVERSATIONS_ARCHIVE ||--o{ AUDIT_LOG : audited_by

    TRIALS {
        string trial_id PK
        string trial_name
        string description
        json inclusion_criteria
        json exclusion_criteria
        json visit_templates "screening, baseline, follow-up types + durations + buffers"
        string pi_name
        string coordinator_name
        string coordinator_phone
        string site_address
        string site_name
        string calendar_id
        float max_distance_km "protocol max distance for geo gate"
        json operating_hours "per-day availability windows"
        boolean active
        timestamp created_at
    }

    PARTICIPANT_EHR {
        string ehr_record_id PK
        string participant_id FK
        string trial_id FK
        json demographics
        json medical_history
        json medications
        json lab_results
        string source_system
        timestamp imported_at
    }

    CONVERSATIONS_ARCHIVE {
        string conversation_id PK
        string participant_id
        string trial_id
        string channel
        string direction
        string agent_name
        json full_transcript
        json agent_reasoning
        float duration_seconds
        string sentiment_score
        json topic_tags
        json handoff_triggers_fired
        string outcome
        timestamp started_at
        timestamp ended_at
        timestamp archived_at
    }

    AUDIT_LOG {
        string audit_id PK
        string conversation_id FK
        string agent_name
        string audit_type
        json findings
        string risk_level
        boolean human_review_required
        timestamp audited_at
    }
```

**What flows from Postgres → Databricks via Pub/Sub:**
- **Events** (all types) → append to events Delta table for analytics (outreach patterns, conversion funnels, no-show reasons)
- **Conversations** (after call ends) → `conversations_archive` with full transcript + agent reasoning for ML analysis
- **Appointment status changes** → reporting dashboards (confirmation rates, no-show rates, scheduling patterns)
- **Handoff events** → coordinator workload analysis, SLA compliance tracking

**What lives only in Databricks:**
- `trials` — reference data (criteria, visit templates, geo limits), loaded once, read by agents at call start
- `participant_ehr` — imported from EHR systems, too large/complex for OLTP, used for cross-reference in screening
- `audit_log` — write-heavy, append-only, analyzed in batch by supervisor agent
- ML models and feature tables (no-show prediction, best contact time/channel, eligibility scoring)

### 6.3 Audio Storage (GCS)

Voice recordings are stored in a dedicated GCS bucket, not in Postgres or Databricks.

```
gs://ask-mary-audio/
├── {trial_id}/
│   ├── {participant_id}/
│   │   ├── {conversation_id}.wav    # Full call recording
│   │   ├── {conversation_id}.json   # Recording metadata (duration, codec, etc.)
│   │   └── voicemail_{timestamp}.wav # Voicemail recordings
```

**Access controls:**
- IAM-based access (no public URLs)
- Signed URLs with expiration for dashboard playback
- Retention policy: per-trial default = trial duration + regulatory hold period
- `conversations.audio_url` in Postgres stores the GCS path (not a signed URL — URLs are generated on demand)

### 6.4 Comms Templates (Repo Config)

Communication templates live as YAML config files in the repository, not in the database.

```
comms_templates/
├── disclosure.yaml          # S1: automated assistant + recording disclosure
├── consent_sms.yaml         # S1: SMS opt-in/STOP message
├── prep_instructions.yaml   # S7: T-48h visit prep (ID, fasting, parking)
├── confirmation_prompt.yaml # S7: T-24h / T+11h "Reply YES or RESCHEDULE"
├── day_of_checkin.yaml      # S7: T-2h check-in + transport ETA
├── no_show_rescue.yaml      # S7: T+0 rescue flow + reason capture
├── protocol_change.yaml     # Broadcast: trial update + acknowledgement
├── ineligible_close.yaml    # S3: neutral close + future trial opt-in
└── unreachable.yaml         # S7: channel switch / coordinator escalation
```

Each template uses Jinja2 variables (`{{ participant.first_name }}`, `{{ appointment.scheduled_at | tz(participant.timezone) }}`) and specifies allowed channels + fallback logic.

---

## 7. Safety, Evaluation & Observability

### 7.1 Safety Architecture

```mermaid
graph TD
    subgraph "Real-time Safety (Every Agent Response)"
        A["Agent generates response"] --> SG{"Safety Gate<br/>(blocking pre-check<br/>&lt;200ms)"}
        SG -->|"medical advice,<br/>symptoms, AE,<br/>consent confusion,<br/>anger/threats,<br/>language mismatch"| HQ["Write to<br/>handoff_queue"]
        HQ --> HQ_NOW{"Severity?"}
        HQ_NOW -->|HANDOFF_NOW| XFER["Immediate transfer<br/>to coordinator"]
        HQ_NOW -->|CALLBACK_TICKET| TICKET["Queue callback<br/>(2h SLA)"]
        HQ_NOW -->|STOP_CONTACT| STOP["End conversation<br/>+ suppress outreach"]

        SG -->|No trigger| GATES{"Gate Checks"}
        GATES --> G1{"DNC<br/>Check"}
        G1 -->|DNC flag| BLOCK["Block outbound"]
        G1 -->|Clear| G2{"Identity<br/>Verified?"}
        G2 -->|No| PHI_BLOCK["Block PHI +<br/>trial details"]
        G2 -->|Yes| G3{"Consent<br/>Captured?"}
        G3 -->|No| DISC["Require disclosure<br/>+ consent first"]
        G3 -->|Yes| DELIVER["Deliver response<br/>to participant"]
    end

    subgraph "Post-Call Safety (Supervisor Agent)"
        H["Conversation<br/>Transcript"] --> I["Supervisor Agent"]
        I --> J["Compliance Check"]
        I --> K["PHI Leak Detection"]
        I --> L["Deception Analysis"]
        I --> M2["Provenance Audit"]
        J --> M["Audit Log<br/>(Databricks)"]
        K --> M
        L --> M
        M2 --> M
        M --> N{"Risk Level"}
        N -->|High| O["Alert Coordinator +<br/>handoff_queue"]
        N -->|Low| P["Auto-approve"]
    end
```

### 7.2 Immutable Test Suite

Tests that **must always pass** and **cannot be deleted or modified without explicit approval**:

```
tests/
  safety/                              # IMMUTABLE — locked in CI
    test_no_phi_before_identity.py       # PHI never shared pre-verification (G2)
    test_disclosure_before_proceed.py    # Disclosure gate enforced before conversation (G1)
    test_dnc_enforcement.py              # DNC flags block outbound on correct channels
    test_identity_verification.py        # DOB + ZIP flow, duplicate detection, wrong_person handling
    test_eligibility_boundaries.py       # Edge cases in inclusion/exclusion criteria
    test_deception_detection.py          # Known deception patterns caught by adversarial checker
    test_handoff_triggers.py             # All 7 handoff trigger types fire correctly
    test_handoff_latency.py              # Safety gate completes in <200ms
    test_consent_withdrawal_stops.py     # Consent withdrawal → STOP_CONTACT, suppress outreach
    test_provenance_annotation.py        # Corrections annotate, never overwrite source data
    test_idempotency_keys.py             # Duplicate outbound actions blocked by idempotency_key
    test_confirmation_window.py          # 12h timeout releases slot, logs expired_unconfirmed
    test_geo_gate.py                     # Distance > protocol max → ineligible-distance
    test_teach_back.py                   # Failed teach-back (2x) → handoff
    test_appointment_confirmation.py     # All required details communicated before booking
    test_uber_pickup_verification.py     # Address verified before transport booking
  integration/
    test_twilio_webhook.py               # Webhook handling works
    test_elevenlabs_connection.py        # Voice pipeline connects
    test_postgres_connection.py          # Operational DB read/write works
    test_databricks_connection.py        # Analytics DB read works
    test_google_calendar.py              # Calendar CRUD works
    test_gcs_audio_storage.py            # Audio upload/signed URL generation works
    test_cloud_tasks_scheduling.py       # Job scheduling + callback works
    test_events_append_only.py           # Events table rejects UPDATE/DELETE
  evaluation/
    scenarios/                           # Baseline safety scenarios (YAML)
      happy_path.yaml                    # Full pipeline: outreach → screening → book → confirm → complete
      angry_participant.yaml             # Participant becomes hostile → HANDOFF_NOW
      wrong_person.yaml                  # Caller fails identity → suppress outreach
      lying_participant.yaml             # Inconsistent screening answers → adversarial flag
      reschedule_request.yaml            # Participant reschedules via confirmation prompt
      no_show_rescue.yaml                # No-show → rescue flow → reason capture
      consent_withdrawal.yaml            # Mid-call consent withdrawal → STOP_CONTACT
      unreachable_workflow.yaml          # Comms bounce → channel switch → coordinator task
      caregiver_authorization.yaml       # Third-party/caregiver handles call
      geo_gate_failure.yaml              # Participant outside protocol distance
      medical_advice_handoff.yaml        # Participant asks medical question → immediate handoff
```

### 7.3 Observability Stack

| Layer | Tool | Purpose |
|-------|------|---------|
| **Agent Tracing** | Langfuse | Trace every agent handoff, tool call, LLM invocation |
| **Metrics** | Databricks MLflow | Track screening accuracy, no-show rates, call duration |
| **Logs** | Structured JSON → Databricks | All events, searchable via SQL |
| **Alerts** | Langfuse + webhook → Slack | High-risk audit findings, pipeline failures |
| **Dashboard** | Lovable-generated React UI | Real-time participant pipeline view |

### 7.4 Agent Evaluation Framework

```
eval/
  run_eval.py                # Runner script
  metrics.py                 # Scoring functions
  scenarios/                 # YAML test conversations
  baselines/                 # Expected outputs for comparison
  reports/                   # Auto-generated evaluation reports
```

Each scenario defines:
- **Input**: Simulated participant messages
- **Expected behavior**: What the agent should do
- **Failure criteria**: What must NOT happen
- **Scoring**: Pass/fail + continuous metrics (empathy score, accuracy, latency)

---

## 8. DevOps & Deployment

### 8.1 Git Strategy

```
ask_mary/
├── main                    # Production — protected branch
├── dev                     # Development — PRs merge here first
├── feature/voice-agent     # Feature branches (git worktree)
├── feature/screening       #
└── feature/dashboard       #
```

**Worktree usage**: Each major feature gets its own git worktree so Claude Code and Codex can work on different features in parallel without branch conflicts.

### 8.2 CI/CD Pipeline

```
on push to dev:
  1. Run immutable safety tests
  2. Run integration tests (mocked external services)
  3. Run evaluation scenarios
  4. If all pass → build Docker image → push to Artifact Registry → deploy to Cloud Run (staging)

on PR to main:
  1. Codex reviews PR
  2. Full test suite + eval
  3. If approved → canary deploy to production (10% traffic)
  4. Monitor Langfuse metrics for 15 min
  5. If no regressions → full rollout
  6. If regressions → auto-rollback
```

### 8.3 Google Cloud Run Service Configuration

| Service | Type | Port | GCP Resource | Notes |
|---------|------|------|-------------|-------|
| `ask-mary-api` | Web (Cloud Run) | 8000 | `us-central1` | FastAPI — handles webhooks, REST endpoints. Min instances: 1 (avoid cold start for Twilio webhooks). |
| `ask-mary-worker` | Worker (Cloud Run) | — | `us-central1` | Background tasks: reminders, Uber booking, audits. Triggered by Cloud Tasks or Pub/Sub. Min instances: 0. |
| `ask-mary-dashboard` | Static (Firebase Hosting) | 443 | Global CDN | React app from Lovable. Alternatively, serve as Cloud Run service. |

**GCP Services Used**:
| Service | Purpose |
|---------|---------|
| Cloud Run | API + Worker containers |
| Cloud SQL (Postgres) | Operational database — transactional state |
| Artifact Registry | Docker image storage |
| Secret Manager | API keys, tokens (HIPAA-safe) |
| Cloud Build | CI/CD Docker builds |
| Cloud Tasks | Scheduled reminders, retries, timed slot releases |
| Pub/Sub | Event bridge: Postgres → Databricks CDC stream |
| Firebase Hosting | Static frontend (dashboard) |
| Cloud Logging | Centralized logs |
| IAM | Service accounts, least-privilege access |

### 8.4 Environment Separation

| Env | Cloud SQL (Postgres) | Databricks | Twilio | ElevenLabs | Uber | Calendar |
|-----|---------------------|-----------|--------|------------|------|----------|
| **dev** | `ask_mary_dev` DB | Dev catalog/schema | Test numbers | Test agent | Mock API | Test calendar |
| **staging** | `ask_mary_staging` DB | Staging catalog/schema | Test numbers | Test agent | Mock API | Test calendar |
| **prod** | `ask_mary_prod` DB | Prod catalog/schema | Real numbers | Real agent | Real API | Real calendar |

---

## 9. 12-Hour Implementation Plan

### Phase 1: Foundation (Hours 0-3)

| Task | Owner | Duration | Details |
|------|-------|----------|---------|
| 1.1 Project scaffolding | Claude Code | 30 min | FastAPI project structure, pyproject.toml, Dockerfile, Cloud Run config, `comms_templates/` dir with YAML stubs |
| 1.2 Cloud SQL Postgres setup | Claude Code | 20 min | Alembic migrations for operational tables: participants, appointments, conversations, events, handoff_queue, rides |
| 1.3 Operational DB module | Claude Code | 40 min | `db/postgres.py` — SQLAlchemy models + asyncpg CRUD. Events table append-only (no UPDATE/DELETE). Idempotency key enforcement. |
| 1.4 Databricks analytics tables | Claude Code | 20 min | Create Delta Lake tables (trials, participant_ehr, conversations_archive, audit_log), seed with test trial/EHR data |
| 1.5 Analytics DB module | Claude Code | 15 min | `db/databricks.py` — read-only connector for trial criteria, EHR lookups, geo distance limits |
| 1.6 GCS audio bucket setup | Claude Code | 10 min | Create `ask-mary-audio` bucket, IAM policies, signed URL helper function |
| 1.7 ElevenLabs + Twilio setup | Human | 45 min | Buy Twilio number, create ElevenLabs agent, configure native integration |
| 1.8 OpenAI Agents SDK skeleton | Claude Code | 45 min | Orchestrator + all agent stubs with handoff pattern + safety_gate inline function |

### Phase 2: Core Agents (Hours 3-7)

| Task | Owner | Duration | Details |
|------|-------|----------|---------|
| 2.1 Outreach Agent | Claude Code | 30 min | DNC enforcement, retry cadence logic (3 voice + SMS), consent capture, events logging |
| 2.2 Identity Agent | Claude Code | 30 min | DOB+ZIP verification, duplicate/wrong-person detection, identity_status update |
| 2.3 Screening Agent | Claude Code | 60 min | Trial criteria matching, hard excludes first, EHR cross-reference, provenance annotation, caregiver auth, eligibility_status output |
| 2.4 Safety Gate | Claude Code | 30 min | Inline blocking pre-check (<200ms), 7 trigger types, handoff_queue writes, severity routing |
| 2.5 Scheduling Agent | Claude Code | 60 min | Geo/distance gate, Google Calendar MCP, slot reservation (SELECT FOR UPDATE), 12h confirmation window, teach-back, Cloud Tasks scheduling |
| 2.6 Transport Agent | Claude Code | 30 min | Uber Health mock + interface, pickup address verification, T-24h/T-2h reconfirmation scheduling |
| 2.7 Comms Agent | Claude Code | 45 min | Event-driven cadence (T-48h prep, T-24h confirm, T-2h check-in, T+0 rescue), idempotency keys, unreachable workflow, channel switching |
| 2.8 ElevenLabs voice integration | Claude Code | 30 min | Connect agent SDK to ElevenLabs server-side tools, audio recording → GCS |
| 2.9 Comms templates | Claude Code | 15 min | Write all `comms_templates/*.yaml` files with Jinja2 variables |

### Phase 3: Safety & Testing (Hours 7-9)

| Task | Owner | Duration | Details |
|------|-------|----------|---------|
| 3.1 Immutable safety tests | Claude Code | 60 min | All 16 safety tests: DNC, disclosure gate, identity gate, handoff triggers/latency, consent withdrawal, provenance, idempotency, geo gate, teach-back, confirmation window |
| 3.2 Supervisor Agent | Claude Code | 30 min | Post-call transcript audit, compliance check, deception detection, provenance audit |
| 3.3 Adversarial Checker | Claude Code | 20 min | Re-screen with different phrasing, EHR cross-reference, Cloud Tasks T+14d scheduling |
| 3.4 Evaluation scenarios | Claude Code | 30 min | 11 YAML scenarios + runner (happy path through medical advice handoff) |
| 3.5 Integration tests | Claude Code | 20 min | Webhook, DB, calendar, GCS, Cloud Tasks, events append-only tests |

### Phase 4: Frontend & Polish (Hours 9-11)

| Task | Owner | Duration | Details |
|------|-------|----------|---------|
| 4.1 Dashboard (Lovable) | Human + Lovable | 60 min | React dashboard: participant pipeline, appointments, handoff_queue (open tickets), conversation logs with audio playback, events timeline |
| 4.2 Dashboard API endpoints | Claude Code | 30 min | REST endpoints: participants list/detail, appointments, handoff_queue, conversations, events, analytics summary |
| 4.3 Pub/Sub event bridge | Claude Code | 20 min | CDC from Postgres events/conversations/appointments → Databricks via Pub/Sub |
| 4.4 Deploy to GCP Cloud Run | Claude Code | 30 min | Docker build, push to Artifact Registry, deploy Cloud Run services, set env vars via Secret Manager |
| 4.5 End-to-end test call | Human | 30 min | Call the Twilio number, run through full flow: outreach → screening → booking → confirmation |

### Phase 5: Demo Prep (Hours 11-12)

| Task | Owner | Duration | Details |
|------|-------|----------|---------|
| 5.1 Fix blockers from E2E test | Claude Code | 30 min | Whatever broke |
| 5.2 Demo script | Human | 15 min | Write talking points: show happy path, handoff trigger, no-show rescue |
| 5.3 Seed compelling demo data | Claude Code | 15 min | Realistic participants/trials, pre-populated events timeline, sample handoff tickets |

### Critical Path

```mermaid
gantt
    title 12-Hour Hackathon Critical Path
    dateFormat HH:mm
    axisFormat %H:%M

    section Foundation
    Project scaffolding           :f1, 00:00, 30m
    Cloud SQL Postgres setup      :f2, 00:00, 20m
    Operational DB module         :f3, after f2, 40m
    Databricks analytics tables   :f4a, 00:00, 20m
    Analytics DB module           :f4b, after f4a, 15m
    GCS audio bucket              :f4c, 00:00, 10m
    ElevenLabs + Twilio setup     :f5, 00:00, 45m
    Agent SDK skeleton            :f6, after f1, 45m

    section Core Agents
    Outreach Agent                :a0, after f6, 30m
    Identity Agent                :a1, after a0, 30m
    Screening Agent               :a2, after a1, 60m
    Safety Gate                   :a2b, after f6, 30m
    Scheduling Agent              :a3, after a2, 60m
    Transport Agent               :a4, after a3, 30m
    Comms Agent                   :a5, after a4, 45m
    Voice integration             :a6, after f5, 30m
    Comms templates               :a7, after f1, 15m

    section Safety & Testing
    Safety tests                  :s1, after a5, 60m
    Supervisor Agent              :s2, after a2, 30m
    Adversarial Checker           :s2b, after s2, 20m
    Eval scenarios                :s3, after s1, 30m
    Integration tests             :s4, after s1, 20m

    section Frontend & Integration
    Dashboard (Lovable)           :d1, after a5, 60m
    Dashboard API                 :d2, after a5, 30m
    Pub/Sub event bridge          :d2b, after d2, 20m
    Deploy to Cloud Run           :d3, after d2b, 30m
    E2E test call                 :d4, after d3, 30m

    section Demo
    Fix blockers                  :e1, after d4, 30m
    Demo prep                     :e2, after e1, 30m
```

---

## 10. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Uber Health API requires enterprise account | High | Medium | Mock API with well-defined interface; swap later |
| ElevenLabs voice latency spikes | Medium | High | Pre-test during setup phase; have SMS fallback |
| Safety gate exceeds 200ms latency budget | Medium | High | Keep safety gate as simple keyword/pattern check (not full LLM call); benchmark in Phase 2; fall back to parallel check with interrupt if needed |
| Databricks SQL warehouse cold start (analytics queries) | Medium | Low | Only used for reference data + batch analytics, not in hot path. Keep warehouse warm for demo. |
| Twilio number not provisioned in time | Low | Critical | Buy number immediately in Phase 1 |
| Participant data privacy in demo | Medium | High | Use synthetic data only; never use real PHI |
| Agent hallucinations during screening | Medium | High | Structured output with Pydantic; supervisor agent review; provenance annotations |
| Cloud Run cold start on webhook | Medium | Medium | Set min instances = 1 for API service; use always-on revision |
| Google Calendar OAuth complexity | Medium | Medium | Use service account (no user consent flow) |
| HIPAA BAA not in place for demo | Medium | High | Use synthetic data only during hackathon; BAA process is separate from technical setup |
| Google Calendar MCP not covered by Google BAA | Medium | Medium | Don't store PHI in calendar event titles/descriptions; use opaque reference IDs only |
| Confirmation window complexity (12h timeout + slot release) | Medium | Medium | Cloud Tasks handles timing; slot_held_until enforced by DB constraint; test thoroughly with time simulation |
| Events table grows large quickly | Low | Medium | Append-only by design; partition by month; Pub/Sub streams to Databricks for long-term storage; Postgres only needs recent events |
| Handoff queue SLA missed (HANDOFF_NOW not immediate) | Low | High | Dashboard polling initially; post-MVP: push notification to coordinator device |
| Comms template rendering errors | Low | Medium | Validate all templates at startup; unit test every template with sample data; Jinja2 strict mode |
| GCS audio storage costs | Low | Low | Lifecycle policy: move to Coldline after 90 days; retention per-trial policy |
| DNC flag race condition (outbound in flight when DNC set) | Low | Medium | Idempotency keys + events log prevent duplicate delivery; check DNC at send-time, not just schedule-time |

---

## 11. Resolved Questions

### Q1: Iteration Process (Claude Code + Codex Loop)

**Status**: RESOLVED — Full plan created in separate document.

The iteration workflow is:
1. Claude Code creates plan → commits to branch
2. Codex reviews plan → posts comments/concerns
3. Claude Code validates comments (rejecting invalid ones) → addresses valid comments → updates plan
4. Loop continues until no concerns or only low-priority items remain
5. Claude Code implements the approved plan
6. Pushes PR
7. Codex reviews PR by comparing plan.md vs implementation → posts comments
8. Claude Code addresses valid comments
9. Claude approves PR with detailed fix summary

**Infrastructure required**: Docker containers on GCP Cloud Run with Claude Code (headless) + Serena MCP + Ralph Wiggum, and Codex (headless) + review scripts.

> **See full infrastructure plan**: [`local_docs/agent_dev_workflow_plan.md`](agent_dev_workflow_plan.md)
> Contains: architecture diagrams, Docker configs, GCP setup, GitHub Actions workflows, Serena MCP + Ralph Wiggum configuration.

### Q2: ElevenLabs LLM Configuration

**Status**: RESOLVED — Dual approach.

**Phase 1 (Hackathon)**: Configure backing LLM in ElevenLabs dashboard (fastest setup).

**Phase 2 (Post-hackathon)**: Build a Custom LLM server endpoint that routes to our OpenAI Agents SDK backend. ElevenLabs supports this natively — the custom LLM endpoint must follow the **OpenAI Chat Completion request/response format**. Our FastAPI server can expose an `/v1/chat/completions` endpoint that internally routes to our agent orchestrator.

**Key finding**: ElevenLabs also supports **Server Tools** (webhooks called during conversation) and **MCP server connections**, so even in Phase 1 we can have the ElevenLabs-hosted LLM call back into our agent tools without a full custom LLM integration.

**Architecture**:
- Phase 1: `ElevenLabs (hosted LLM) → Server Tools (webhook) → Our FastAPI → Agent SDK`
- Phase 2: `ElevenLabs (custom LLM) → Our FastAPI /v1/chat/completions → Agent SDK`

### Q3: Uber Health Access

**Status**: RESOLVED — Mock for MVP.

No Uber Health account available. Plan:
- Build a `UberHealthClient` interface with well-defined methods
- Implement `MockUberHealthClient` for hackathon demo
- Real `UberHealthClient` is a drop-in replacement when access is obtained
- The mock simulates: ride scheduling, pickup confirmation, status updates

### Q4: Database Setup

**Status**: RESOLVED — Hybrid architecture (see Section 6.0). Needs human setup for both layers.

**Cloud SQL Postgres Checklist** (operational DB — must be done before Phase 1):
- [ ] Create Cloud SQL Postgres instance in GCP console (`ask-mary-db`, `db-f1-micro` for hackathon)
- [ ] Note the connection string (Cloud SQL proxy or public IP)
- [ ] Provide to Claude Code as environment variable:
  - `DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/ask_mary_dev`

**Databricks Checklist** (analytics DB — can be set up slightly later):
- [ ] Create/access Databricks workspace
- [ ] Create a SQL warehouse (serverless recommended)
- [ ] Generate a personal access token
- [ ] Provide to Claude Code as environment variables:
  - `DATABRICKS_SERVER_HOSTNAME`
  - `DATABRICKS_HTTP_PATH`
  - `DATABRICKS_TOKEN`

### Q5: Twilio Number

**Status**: RESOLVED — Needs human setup.

**Human Setup Checklist** (must be done before Phase 1 starts):
- [ ] Create Twilio account at twilio.com
- [ ] Buy a phone number with Voice + SMS capabilities
- [ ] Note Account SID, Auth Token, and phone number
- [ ] (Optional) Set up WhatsApp sandbox for testing
- [ ] Provide these to Claude Code as environment variables:
  - `TWILIO_ACCOUNT_SID`
  - `TWILIO_AUTH_TOKEN`
  - `TWILIO_PHONE_NUMBER`

### Q6: RaySurfer

**Status**: RESOLVED — Useful but not critical for MVP.

**What it is**: RaySurfer is a **semantic code caching SDK** — not an agent framework. It caches LLM-generated code snippets and retrieves proven snippets for reuse instead of regenerating them. Claims 30x faster agent execution for repetitive workflows.

**Assessment for Ask Mary**:
- **Not a replacement** for OpenAI Agents SDK (complementary infrastructure)
- **Best for**: Repetitive code generation patterns (report generation, data processing)
- **Less useful for**: Our use case, which is conversational agents with unique interactions
- **Recommendation**: Skip for hackathon. Revisit post-MVP if we find repetitive code generation patterns in our agent maintenance workflow. Could pair well with the Claude Code + Codex iteration loop for caching common code patterns.

### Q7: Multi-Tenant

**Status**: RESOLVED — Multi-trial from day one, single-agency for now.

**Feasibility assessment**: Multi-trial support is feasible within the 12-hour timeline because our data model **already supports it** — every table has a `trial_id` foreign key. The cost of multi-trial support is minimal at the data layer.

**What "multi-trial" costs us**:
- Data model: **0 extra time** (already designed with `trial_id` on all relevant tables)
- Agent logic: **~30 min extra** (agents must accept `trial_id` context, load correct criteria)
- Calendar: **~15 min extra** (different calendars per trial)
- Dashboard: **~15 min extra** (trial selector dropdown)
- **Total extra cost: ~1 hour**

**What we defer (single-agency)**:
- Multi-agency auth/permissions (adds ~2-3 hours — not worth it for MVP)
- Agency-level billing and reporting
- Cross-agency data isolation

**Strategy to avoid technical debt**:
1. Use `trial_id` everywhere from day one (already in the data model)
2. Use `agency_id` as a column but hardcode to a single value for MVP
3. Never hardcode trial-specific logic — always load from the `trials` table
4. This means upgrading to multi-agency later is just adding auth middleware + agency selector, not restructuring data

---

## 12. Human Pre-Setup Checklist

These items require manual human action before the hackathon clock starts:

| Item | Priority | Time | Details |
|------|----------|------|---------|
| GCP project + enable APIs | P0 | 10 min | Enable Cloud Run, Cloud SQL, Artifact Registry, Secret Manager, Cloud Tasks, Pub/Sub, Cloud Storage |
| Cloud SQL Postgres instance | P0 | 5 min | Create instance (`ask-mary-db`), note connection string. Claude Code handles schema migration. |
| GCS audio bucket | P0 | 5 min | Create `ask-mary-audio` bucket in same region, set IAM policies for service account. |
| Databricks workspace + SQL warehouse | P0 | 15 min | For analytics layer. See Q4 above. |
| Twilio account + phone number | P0 | 10 min | See Q5 above. Ensure Voice + SMS capabilities. |
| ElevenLabs account + agent creation | P0 | 15 min | Create Conversational AI agent in dashboard. Enable call recording if available. |
| Google Calendar service account | P1 | 10 min | OAuth credentials for calendar access |
| OpenAI API key | P0 | 5 min | For Agents SDK |
| Anthropic API key | P0 | 5 min | For Claude Code dev workflow |
| GitHub repo access tokens | P1 | 5 min | Fine-grained PAT for CI/CD |

---

## Sources

- [ElevenLabs Conversational AI Platform](https://elevenlabs.io/conversational-ai)
- [ElevenLabs Agents Platform Documentation](https://elevenlabs.io/docs/agents-platform/overview)
- [ElevenLabs + Twilio Native Integration](https://elevenlabs.io/docs/agents-platform/phone-numbers/twilio-integration/native-integration)
- [Twilio + ElevenLabs Voice Integration Tutorial](https://www.twilio.com/en-us/blog/developers/tutorials/integrations/build-twilio-voice-elevenlabs-agents-integration)
- [Twilio Alpha MCP Server](https://www.twilio.com/en-us/blog/introducing-twilio-alpha-mcp-server)
- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)
- [OpenAI Agents SDK — Multi-Agent Orchestration](https://openai.github.io/openai-agents-python/multi_agent/)
- [Claude Agent SDK — Python](https://github.com/anthropics/claude-agent-sdk-python)
- [Claude Agent SDK Overview](https://platform.claude.com/docs/en/agent-sdk/overview)
- [Uber Health API Introduction](https://developer.uber.com/docs/health/introduction)
- [Uber Health — Clinical Trials Transportation](https://www.outsourcing-pharma.com/Article/2018/03/05/Uber-Health-partners-with-Bracket-for-clinical-trials-transportation)
- [Google Calendar MCP Server](https://github.com/nspady/google-calendar-mcp)
- [Databricks SQL Connector for Python](https://docs.databricks.com/aws/en/dev-tools/python-sql-connector)
- [Databricks Managed MCP Servers](https://docs.databricks.com/aws/en/generative-ai/mcp/managed-mcp)
- [Langfuse — AI Agent Observability](https://langfuse.com/blog/2024-07-ai-agent-observability-with-langfuse)
- [Langfuse — OpenAI Agents SDK Integration](https://langfuse.com/guides/cookbook/example_evaluating_openai_agents)
- [ElevenLabs — Custom LLM Integration](https://elevenlabs.io/docs/agents-platform/customization/llm/custom-llm)
- [ElevenLabs — Server Tools](https://elevenlabs.io/docs/agents-platform/customization/tools/server-tools)
- [ElevenLabs — Integrating External Agents](https://elevenlabs.io/blog/integrating-complex-external-agents)
- [ElevenLabs — MCP Support](https://elevenlabs.io/docs/agents-platform/customization/tools/mcp)
- [RaySurfer — Semantic Code Caching SDK](https://www.raysurfer.com/)
- [Serena MCP Server](https://github.com/oraios/serena)
- [Ralph Wiggum Plugin — Claude Code Autonomous Loops](https://github.com/anthropics/claude-code/tree/main/plugins/ralph-wiggum)
- [Claude Code Headless Mode](https://code.claude.com/docs/en/headless)
- [OpenAI Codex CLI](https://developers.openai.com/codex/cli/)
- [Codex Code Review with SDK](https://cookbook.openai.com/examples/codex/build_code_review_with_codex_sdk)
