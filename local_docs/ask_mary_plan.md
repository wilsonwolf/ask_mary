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
    that interacts with patients via voice and text (WhatsApp, SMS) to
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

  <workflow description="Patient recruitment and scheduling pipeline">

    <step id="S1" name="outreach">
      <description>
        System initiates contact with trial-eligible patients from EHR/Databricks data.
        Channels: outbound voice call (ElevenLabs + Twilio), SMS, WhatsApp.
        Must mention Uber transportation credit upfront to increase response rate.
      </description>
      <agents>outreach_agent, channel_router</agents>
      <apis>ElevenLabs Conversational AI, Twilio (SMS/WhatsApp/Voice)</apis>
    </step>

    <step id="S2" name="identity_verification">
      <description>
        Verify we are speaking to the correct patient. Methods: DOB check, text
        verification code, secret question from EHR data. Must pass before any
        PHI is discussed.
      </description>
      <agents>identity_agent</agents>
      <data_sources>patients table (Postgres — operational state)</data_sources>
    </step>

    <step id="S3" name="eligibility_screening">
      <description>
        Present trial metadata (inclusion/exclusion criteria) conversationally.
        Collect patient responses to screening questions. Vet responses against
        internal trial criteria. Flag contradictions with EHR data.
      </description>
      <agents>screening_agent, adversarial_checker_agent</agents>
      <data_sources>trials table (Databricks — reference data), patient_ehr table (Databricks), screening_results (Postgres — operational state)</data_sources>
    </step>

    <step id="S4" name="adversarial_recheck">
      <description>
        Two-week follow-up re-screening. An adversarial agent re-asks key
        eligibility questions in different phrasing to detect inconsistencies
        or deception. Cross-reference against data on file. Flag discrepancies
        for human review.
      </description>
      <agents>adversarial_checker_agent, deception_detector_agent</agents>
      <schedule>14 days after S3</schedule>
    </step>

    <step id="S5" name="appointment_scheduling">
      <description>
        Negotiate appointment time. Check provider-side availability via Google
        Calendar (nurse coordinator, PI). Collect patient preferences. Confirm
        details: clinic address, what to bring, fasting requirements, duration.
        Cannot rely solely on electronic calendar — must send robust reminders.
      </description>
      <agents>scheduling_agent</agents>
      <apis>Google Calendar API (via MCP server)</apis>
      <key_decision>
        What minimum details does the patient need to minimize no-shows?
        Answer: Date/time, clinic address, what to bring, fasting/prep
        instructions, estimated duration, transportation details, contact
        number for day-of issues.
      </key_decision>
    </step>

    <step id="S6" name="transportation">
      <description>
        Arrange Uber Health ride. Verify pickup location from EHR address,
        offer alternative pickup. Schedule ride for appointment day.
        Must verify location ahead of time (not day-of).
      </description>
      <agents>transport_agent</agents>
      <apis>Uber Health API (HIPAA-compliant)</apis>
      <flow>
        1. Pull address from EHR
        2. Confirm with patient: "We have [address] on file. Is this where
           you'd like to be picked up, or would you prefer a different location?"
        3. If different → collect and validate new address
        4. Schedule ride 30 days or less in advance
        5. Confirm ride details with patient
      </flow>
    </step>

    <step id="S7" name="reminder_loop">
      <description>
        Event-driven reminder system. Multi-channel (voice, SMS, WhatsApp).
        Escalating cadence: 7 days, 3 days, 1 day, 2 hours before appointment.
        Must handle reschedule requests. Must confirm Uber ride details in final reminder.
      </description>
      <agents>reminder_agent, scheduling_agent</agents>
      <apis>Twilio, ElevenLabs</apis>
      <cadence>
        <reminder offset="-7d" channels="sms,whatsapp">Appointment confirmation + prep details</reminder>
        <reminder offset="-3d" channels="sms,whatsapp">Reminder + Uber ride confirmation</reminder>
        <reminder offset="-1d" channels="voice,sms">Day-before call + final confirmation</reminder>
        <reminder offset="-2h" channels="sms">Uber pickup imminent + clinic contact</reminder>
      </cadence>
    </step>

  </workflow>

  <agents>
    <agent name="orchestrator" role="Central coordinator — routes conversations to specialized agents">
      <sdk>OpenAI Agents SDK (handoff pattern)</sdk>
    </agent>
    <agent name="outreach_agent" role="Initiates patient contact across channels">
      <sdk>OpenAI Agents SDK</sdk>
    </agent>
    <agent name="identity_agent" role="Verifies patient identity before PHI discussion">
      <sdk>OpenAI Agents SDK</sdk>
    </agent>
    <agent name="screening_agent" role="Conducts eligibility screening conversation">
      <sdk>OpenAI Agents SDK</sdk>
    </agent>
    <agent name="adversarial_checker_agent" role="Re-checks eligibility with different phrasing, detects inconsistencies">
      <sdk>OpenAI Agents SDK</sdk>
    </agent>
    <agent name="deception_detector_agent" role="Analyzes conversation transcripts for deception markers">
      <sdk>OpenAI Agents SDK</sdk>
    </agent>
    <agent name="scheduling_agent" role="Negotiates appointment times, manages calendar">
      <sdk>OpenAI Agents SDK</sdk>
      <tools>Google Calendar MCP</tools>
    </agent>
    <agent name="transport_agent" role="Arranges Uber Health rides, verifies pickup locations">
      <sdk>OpenAI Agents SDK</sdk>
      <tools>Uber Health API</tools>
    </agent>
    <agent name="reminder_agent" role="Manages reminder cadence and escalation">
      <sdk>OpenAI Agents SDK</sdk>
      <tools>Twilio</tools>
    </agent>
    <agent name="supervisor_agent" role="Post-call review — audits transcripts for safety, compliance, quality">
      <sdk>OpenAI Agents SDK</sdk>
    </agent>
  </agents>

  <tech_stack>
    <backend language="python" framework="FastAPI" agent_sdk="OpenAI Agents SDK"/>
    <voice platform="ElevenLabs Conversational AI 2.0" telephony="Twilio"/>
    <database_operational platform="Cloud SQL (Postgres)" connector="asyncpg + SQLAlchemy" purpose="Transactional state: patients, appointments, rides, reminders, conversations"/>
    <database_analytics platform="Databricks" format="Delta Lake" connector="databricks-sql-connector" purpose="Analytics: EHR data, trial metadata, transcripts, audit logs, ML models, reporting"/>
    <event_bridge from="Postgres" to="Databricks" method="Pub/Sub CDC or periodic sync"/>
    <frontend generator="Lovable" framework="React/TypeScript" host="Firebase Hosting or Cloud Run"/>
    <observability primary="Langfuse" secondary="Databricks MLflow"/>
    <deployment platform="Google Cloud Run" containerization="Docker" registry="Artifact Registry"/>
    <ci_cd git="worktrees" branching="main(prod)/dev/feature" rollback="gradual"/>
  </tech_stack>

  <safety>
    <requirement id="SAFE1">All agent responses checked by supervisor_agent post-call</requirement>
    <requirement id="SAFE2">Identity verification MUST pass before any PHI is shared</requirement>
    <requirement id="SAFE3">Deception detection runs on all screening transcripts</requirement>
    <requirement id="SAFE4">Immutable test suite — safety scenarios that cannot be deleted</requirement>
    <requirement id="SAFE5">All conversations logged with full audit trail in Databricks</requirement>
    <requirement id="SAFE6">Gradual deployment — canary pattern to catch regressions</requirement>
  </safety>

</project>
```

---

## 2. Product Requirements Document

### 2.1 Problem Statement

Clinical trial recruitment suffers from high patient dropout, scheduling friction, and transportation barriers. Current recruitment agency workflows are manual, phone-tag-heavy, and poorly instrumented. Patients lie, forget appointments, and lack transportation. Coordinators juggle spreadsheets and phone calls.

### 2.2 Solution

**Ask Mary** is an AI scheduling agent that automates the patient recruitment pipeline for clinical trials via voice and text. It handles outreach, identity verification, eligibility screening, appointment scheduling, transportation arrangement, and reminder management — with built-in adversarial checking for safety.

### 2.3 Users

| User | Role | Interaction |
|------|------|-------------|
| **Patient** | Trial candidate | Voice calls, SMS, WhatsApp |
| **Nurse Coordinator** | Provider-side scheduler | Dashboard, calendar integration |
| **Principal Investigator (PI)** | Trial lead | Dashboard (read-only), alerts |
| **Recruiting Agency Admin** | System operator | Dashboard, configuration, reports |

### 2.4 MVP Feature Set (12-hour scope)

| Priority | Feature | Status |
|----------|---------|--------|
| P0 | Voice agent for patient screening call (ElevenLabs + Twilio) | Must have |
| P0 | Identity verification (DOB + secret question) | Must have |
| P0 | Eligibility screening with criteria matching | Must have |
| P0 | Appointment scheduling with Google Calendar | Must have |
| P0 | SMS/WhatsApp reminders via Twilio | Must have |
| P1 | Uber Health ride booking | Should have |
| P1 | Admin dashboard (Lovable-generated) | Should have |
| P1 | Post-call supervisor agent audit | Should have |
| P2 | Adversarial re-screening (2-week follow-up) | Nice to have |
| P2 | Deception detection analysis | Nice to have |
| P2 | Full Langfuse observability integration | Nice to have |

### 2.5 Non-Functional Requirements

- **Latency**: Voice response < 1 second (critical for natural conversation)
- **Availability**: Cloud-hosted, accessible via phone number for demo
- **Security**: No PHI shared before identity verification passes
- **Auditability**: All conversations logged with timestamps
- **Maintainability**: Code structured for autonomous agent maintenance

---

## 3. Architecture

### 3.1 System Architecture (High-Level)

```mermaid
graph TB
    subgraph "Patient Channels"
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
        ID_AGT["Identity<br/>Agent"]
        SCREEN_AGT["Screening<br/>Agent"]
        SCHED_AGT["Scheduling<br/>Agent"]
        TRANS_AGT["Transport<br/>Agent"]
        REMIND_AGT["Reminder<br/>Agent"]
        OUTREACH_AGT["Outreach<br/>Agent"]
    end

    subgraph "Safety Layer"
        SUPER["Supervisor<br/>Agent"]
        ADVERS["Adversarial<br/>Checker"]
        DECEPT["Deception<br/>Detector"]
    end

    subgraph "External Services"
        GCAL["Google Calendar<br/>(MCP Server)"]
        UBER["Uber Health<br/>API"]
    end

    subgraph "Operational DB (Cloud SQL Postgres)"
        PG_PATIENTS["patients"]
        PG_APPTS["appointments"]
        PG_RIDES["rides"]
        PG_CONVOS["conversations"]
        PG_REMINDERS["reminders"]
        PG_SCREENING["screening_results"]
    end

    subgraph "Analytics DB (Databricks Delta Lake)"
        DB_TRIALS["trials<br/>(reference)"]
        DB_EHR["patient_ehr<br/>(source data)"]
        DB_TRANSCRIPTS["conversation_transcripts<br/>(full text + analysis)"]
        DB_AUDIT["audit_log"]
        DB_ANALYTICS["reporting &<br/>ML models"]
    end

    subgraph "Job Queue"
        CT["Cloud Tasks<br/>(scheduled reminders,<br/>retries, Uber booking)"]
    end

    subgraph "Event Bridge"
        PS["Pub/Sub<br/>(Postgres → Databricks<br/>event stream)"]
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

    ORCH -->|handoff| ID_AGT
    ORCH -->|handoff| SCREEN_AGT
    ORCH -->|handoff| SCHED_AGT
    ORCH -->|handoff| TRANS_AGT
    ORCH -->|handoff| REMIND_AGT
    ORCH -->|handoff| OUTREACH_AGT

    SCREEN_AGT --> ADVERS
    ADVERS --> DECEPT

    SCHED_AGT --> GCAL
    TRANS_AGT --> UBER

    ORCH --> SUPER

    ID_AGT --> PG_PATIENTS
    SCREEN_AGT --> DB_TRIALS
    SCREEN_AGT --> DB_EHR
    SCREEN_AGT --> PG_SCREENING
    SCHED_AGT --> PG_APPTS
    TRANS_AGT --> PG_RIDES
    REMIND_AGT --> PG_REMINDERS
    ORCH --> PG_CONVOS
    SUPER --> DB_AUDIT

    REMIND_AGT --> CT
    CT --> REMIND_AGT

    PG_CONVOS -->|events| PS
    PG_APPTS -->|events| PS
    PG_SCREENING -->|events| PS
    PS --> DB_TRANSCRIPTS
    PS --> DB_ANALYTICS

    ORCH --> LF
    LF --> MLF

    DASH --> PG_PATIENTS
    DASH --> PG_APPTS
    DASH --> PG_CONVOS
    DASH --> DB_ANALYTICS
```

### 3.2 Agent Orchestration Flow

```mermaid
sequenceDiagram
    participant P as Patient
    participant TW as Twilio
    participant EL as ElevenLabs
    participant O as Orchestrator
    participant ID as Identity Agent
    participant SC as Screening Agent
    participant SH as Scheduling Agent
    participant TR as Transport Agent
    participant SV as Supervisor Agent
    participant PG as Postgres (OLTP)
    participant DB as Databricks (Analytics)

    P->>TW: Answers call / Sends SMS
    TW->>EL: Audio stream (voice)
    EL->>O: Transcribed intent + audio context

    O->>ID: Handoff → verify identity
    ID->>PG: Fetch patient record (sub-ms)
    ID->>P: "Can you confirm your date of birth?"
    P->>ID: Provides DOB
    ID->>PG: Validate DOB
    ID-->>O: Identity verified ✓

    O->>SC: Handoff → eligibility screening
    SC->>DB: Fetch trial criteria (reference data)
    SC->>P: Screening questions
    P->>SC: Answers
    SC->>DB: Cross-reference EHR data
    SC->>PG: Log screening results (transactional)
    SC-->>O: Eligible ✓ / Ineligible ✗

    alt Patient is eligible
        O->>SH: Handoff → schedule appointment
        SH->>PG: Check slot availability (row lock)
        SH->>P: "When would you like to come in?"
        P->>SH: Preferred time
        SH->>PG: Hold slot (10-min reservation)
        SH->>P: Confirm appointment details
        SH->>PG: Commit appointment (ACID)

        O->>TR: Handoff → arrange transport
        TR->>PG: Fetch patient address
        TR->>P: "We'll arrange an Uber. Pick up at [address]?"
        P->>TR: Confirms / provides alternative
        TR->>PG: Store verified pickup + create ride
        TR-->>O: Transport arranged ✓
    end

    O->>PG: Save conversation record
    PG-->>DB: Event stream (Pub/Sub) → transcript + analytics

    O->>SV: Post-call audit
    SV->>DB: Analyze conversation transcript
    SV->>DB: Log audit results
    SV-->>O: Audit complete
```

### 3.3 Reminder Event Loop

```mermaid
stateDiagram-v2
    [*] --> AppointmentCreated

    AppointmentCreated --> Reminder7Day: T-7 days
    Reminder7Day --> WaitForAck7: Send SMS + WhatsApp

    WaitForAck7 --> Reminder3Day: Acknowledged or timeout
    WaitForAck7 --> EscalateToCoord: No response after 24h

    Reminder3Day --> WaitForAck3: Send SMS + WhatsApp
    WaitForAck3 --> Reminder1Day: Acknowledged or timeout

    Reminder1Day --> WaitForAck1: Voice call + SMS
    WaitForAck1 --> Reminder2Hour: Confirmed
    WaitForAck1 --> RescheduleFlow: Requests reschedule
    WaitForAck1 --> EscalateToCoord: No response

    RescheduleFlow --> AppointmentCreated: New appointment

    Reminder2Hour --> UberDispatched: Send SMS with ride ETA
    UberDispatched --> AppointmentDay: Ride confirmed

    AppointmentDay --> Completed: Patient arrives
    AppointmentDay --> NoShow: Patient doesn't arrive
    NoShow --> EscalateToCoord: Flag for follow-up

    EscalateToCoord --> [*]
    Completed --> [*]
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
    A["Patient speaks<br/>(phone)"] -->|PSTN| B["Twilio<br/>(SIP trunk)"]
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
        PG["Operational State<br/>• patients<br/>• appointments<br/>• rides<br/>• reminders<br/>• conversations<br/>• screening_results"]
    end

    subgraph "Pub/Sub Event Bridge"
        PS["CDC Events<br/>• appointment.created<br/>• screening.completed<br/>• conversation.ended<br/>• ride.booked"]
    end

    subgraph "Databricks Delta Lake (OLAP)"
        direction TB
        DB["Analytics & Reference<br/>• trials (reference)<br/>• patient_ehr (source)<br/>• conversation_transcripts<br/>• audit_log<br/>• reporting views<br/>• ML models"]
    end

    PG -->|"event stream"| PS
    PS -->|"ingest"| DB
    DB -->|"read reference<br/>data (trials, EHR)"| PG
```

**Why this split:**

| Concern | Postgres (OLTP) | Databricks (OLAP) |
|---------|-----------------|-------------------|
| **Latency** | Sub-millisecond single-row reads | Seconds (warehouse cold start) |
| **Transactions** | Row-level locking, SERIALIZABLE | Optimistic concurrency (batch) |
| **Constraints** | UNIQUE, FK, CHECK — enforced by DB | No native enforcement |
| **Slot reservation** | `SELECT ... FOR UPDATE` holds slot | Not possible |
| **Double-booking prevention** | UNIQUE constraint on (trial, time, slot) | Must implement in application |
| **Reminder scheduling** | Native with Cloud Tasks trigger | No sub-minute scheduling |
| **Transcript analysis** | Not suited for ML workloads | Purpose-built for this |
| **EHR data joins** | Too large, wrong format | Columnar, optimized |
| **Reporting dashboards** | Slow for aggregations | Fast, purpose-built |

### 6.1 Operational Tables (Cloud SQL Postgres)

These tables require transactional guarantees, low-latency access, and strong consistency.

```mermaid
erDiagram
    PATIENTS ||--o{ CONVERSATIONS : has
    PATIENTS ||--o{ APPOINTMENTS : has
    PATIENTS ||--o{ SCREENING_RESULTS : has
    PATIENTS ||--o{ RIDES : has
    APPOINTMENTS ||--o{ REMINDERS : triggers
    APPOINTMENTS ||--o{ RIDES : has

    PATIENTS {
        uuid patient_id PK
        string first_name
        string last_name
        date date_of_birth
        string phone UK
        string address_street
        string address_city
        string address_state
        string address_zip
        string secret_question
        string secret_answer_hash
        boolean identity_verified
        string agency_id
        string pipeline_status
        timestamp created_at
        timestamp updated_at
    }

    SCREENING_RESULTS {
        uuid screening_id PK
        uuid patient_id FK
        string trial_id FK
        uuid conversation_id FK
        jsonb responses
        string eligibility_status
        float confidence_score
        jsonb ehr_discrepancies
        boolean adversarial_recheck_done
        jsonb adversarial_results
        timestamp screened_at
        timestamp recheck_scheduled_at
    }

    APPOINTMENTS {
        uuid appointment_id PK
        uuid patient_id FK
        string trial_id FK
        timestamptz scheduled_at
        string google_event_id UK
        string status
        string clinic_address
        string prep_instructions
        integer estimated_duration_min
        timestamptz slot_held_until
        timestamp created_at
        timestamp updated_at
    }

    RIDES {
        uuid ride_id PK
        uuid appointment_id FK
        uuid patient_id FK
        string pickup_address
        string dropoff_address
        timestamptz scheduled_pickup_at
        string uber_ride_id
        string status
        timestamp created_at
    }

    CONVERSATIONS {
        uuid conversation_id PK
        uuid patient_id FK
        string channel
        string agent_name
        string call_sid UK
        float duration_seconds
        string status
        jsonb summary
        timestamp started_at
        timestamp ended_at
    }

    REMINDERS {
        uuid reminder_id PK
        uuid appointment_id FK
        string channel
        string message_template
        timestamptz scheduled_at
        timestamptz sent_at
        string status
        string twilio_message_sid
        string response
        integer retry_count
    }
```

**Key Postgres features used:**
- `uuid` primary keys (no sequential leaks)
- `UK` = UNIQUE constraints (prevent duplicate phone, double-booking)
- `jsonb` for flexible data (screening responses, summaries)
- `timestamptz` for timezone-aware scheduling
- `slot_held_until` on appointments enables `SELECT ... FOR UPDATE` reservation pattern
- `retry_count` on reminders for idempotent delivery
- `pipeline_status` on patients tracks their current workflow state

### 6.2 Analytics Tables (Databricks Delta Lake)

These tables hold reference data, large-scale analysis, and reporting.

```mermaid
erDiagram
    TRIALS ||--o{ PATIENT_EHR : enrolls
    CONVERSATIONS_ARCHIVE ||--o{ AUDIT_LOG : audited_by

    TRIALS {
        string trial_id PK
        string trial_name
        string description
        json inclusion_criteria
        json exclusion_criteria
        string pi_name
        string coordinator_name
        string clinic_address
        string calendar_id
        boolean active
        timestamp created_at
    }

    PATIENT_EHR {
        string ehr_record_id PK
        string patient_id FK
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
        string patient_id
        string channel
        string agent_name
        json full_transcript
        json agent_reasoning
        float duration_seconds
        string sentiment_score
        json topic_tags
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
- Conversation records (after call ends) → `conversations_archive` with full transcript for ML analysis
- Screening results → joined with EHR data for eligibility model training
- Appointment events → reporting dashboards (no-show rates, scheduling patterns)
- Ride events → transportation analytics

**What lives only in Databricks:**
- `trials` — reference data, loaded once, read by agents at call start
- `patient_ehr` — imported from EHR systems, too large/complex for OLTP
- `audit_log` — write-heavy, append-only, analyzed in batch by supervisor agent
- ML models and feature tables

---

## 7. Safety, Evaluation & Observability

### 7.1 Safety Architecture

```mermaid
graph TD
    subgraph "Real-time Safety (During Call)"
        A["Agent Response"] --> B{"Identity<br/>Verified?"}
        B -->|No| C["Block PHI disclosure"]
        B -->|Yes| D["Allow conversation"]
        D --> E{"Response<br/>Guardrail Check"}
        E -->|Flagged| F["Fallback to<br/>safe response"]
        E -->|Clean| G["Deliver to patient"]
    end

    subgraph "Post-Call Safety (Supervisor Agent)"
        H["Conversation<br/>Transcript"] --> I["Supervisor Agent"]
        I --> J["Compliance Check"]
        I --> K["PHI Leak Detection"]
        I --> L["Deception Analysis"]
        J --> M["Audit Log"]
        K --> M
        L --> M
        M --> N{"Risk Level"}
        N -->|High| O["Alert Coordinator"]
        N -->|Low| P["Auto-approve"]
    end
```

### 7.2 Immutable Test Suite

Tests that **must always pass** and **cannot be deleted or modified without explicit approval**:

```
tests/
  safety/                          # IMMUTABLE — locked in CI
    test_no_phi_before_identity.py   # PHI never shared pre-verification
    test_identity_verification.py    # DOB + secret question flow works
    test_eligibility_boundaries.py   # Edge cases in inclusion/exclusion
    test_deception_detection.py      # Known deception patterns caught
    test_appointment_confirmation.py # All required details communicated
    test_uber_pickup_verification.py # Address verified before booking
  integration/
    test_twilio_webhook.py           # Webhook handling works
    test_elevenlabs_connection.py    # Voice pipeline connects
    test_postgres_connection.py      # Operational DB read/write works
    test_databricks_connection.py    # Analytics DB read works
    test_google_calendar.py          # Calendar CRUD works
  evaluation/
    scenarios/                       # Baseline safety scenarios (YAML)
      happy_path.yaml                # Normal successful recruitment
      angry_patient.yaml             # Patient becomes hostile
      wrong_person.yaml              # Caller fails identity check
      lying_patient.yaml             # Inconsistent screening answers
      reschedule_request.yaml        # Patient wants different time
      no_show_history.yaml           # Patient with prior no-shows
```

### 7.3 Observability Stack

| Layer | Tool | Purpose |
|-------|------|---------|
| **Agent Tracing** | Langfuse | Trace every agent handoff, tool call, LLM invocation |
| **Metrics** | Databricks MLflow | Track screening accuracy, no-show rates, call duration |
| **Logs** | Structured JSON → Databricks | All events, searchable via SQL |
| **Alerts** | Langfuse + webhook → Slack | High-risk audit findings, pipeline failures |
| **Dashboard** | Lovable-generated React UI | Real-time patient pipeline view |

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
- **Input**: Simulated patient messages
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
| 1.1 Project scaffolding | Claude Code | 30 min | FastAPI project structure, pyproject.toml, Dockerfile, Cloud Run config |
| 1.2 Cloud SQL Postgres setup | Claude Code | 20 min | Create Cloud SQL instance, run Alembic migrations for operational tables (patients, appointments, rides, reminders, conversations, screening_results) |
| 1.3 Operational DB module | Claude Code | 30 min | `db/postgres.py` — SQLAlchemy models + asyncpg CRUD for all operational tables |
| 1.4 Databricks analytics tables | Claude Code | 20 min | Create Delta Lake tables (trials, patient_ehr, conversations_archive, audit_log), seed with test trial/EHR data |
| 1.5 Analytics DB module | Claude Code | 15 min | `db/databricks.py` — read-only connector for trial criteria + EHR lookups |
| 1.6 ElevenLabs + Twilio setup | Human | 45 min | Buy Twilio number, create ElevenLabs agent, configure native integration |
| 1.7 OpenAI Agents SDK skeleton | Claude Code | 45 min | Orchestrator + agent stubs with handoff pattern |

### Phase 2: Core Agents (Hours 3-7)

| Task | Owner | Duration | Details |
|------|-------|----------|---------|
| 2.1 Identity Agent | Claude Code | 45 min | DOB verification, secret question flow, DB lookups |
| 2.2 Screening Agent | Claude Code | 60 min | Trial criteria matching, conversational screening, EHR cross-reference |
| 2.3 Scheduling Agent | Claude Code | 60 min | Google Calendar MCP integration, availability checking, appointment creation |
| 2.4 Transport Agent | Claude Code | 45 min | Uber Health mock + interface, address verification flow |
| 2.5 Reminder Agent | Claude Code | 30 min | Twilio SMS/WhatsApp sending, cadence scheduler |
| 2.6 ElevenLabs voice integration | Claude Code | 30 min | Connect agent SDK to ElevenLabs server-side tools |

### Phase 3: Safety & Testing (Hours 7-9)

| Task | Owner | Duration | Details |
|------|-------|----------|---------|
| 3.1 Immutable safety tests | Claude Code | 45 min | Write all safety/ tests |
| 3.2 Supervisor Agent | Claude Code | 30 min | Post-call transcript audit |
| 3.3 Evaluation scenarios | Claude Code | 30 min | YAML scenarios + runner |
| 3.4 Integration tests | Claude Code | 15 min | Webhook, DB, calendar tests |

### Phase 4: Frontend & Polish (Hours 9-11)

| Task | Owner | Duration | Details |
|------|-------|----------|---------|
| 4.1 Dashboard (Lovable) | Human + Lovable | 60 min | Generate React dashboard: patient pipeline view, appointment list, conversation logs |
| 4.2 Dashboard API endpoints | Claude Code | 30 min | REST endpoints for dashboard data |
| 4.3 Deploy to GCP Cloud Run | Claude Code | 30 min | Docker build, push to Artifact Registry, deploy Cloud Run services, set env vars via Secret Manager |
| 4.4 End-to-end test call | Human | 30 min | Call the Twilio number, run through full flow |

### Phase 5: Demo Prep (Hours 11-12)

| Task | Owner | Duration | Details |
|------|-------|----------|---------|
| 5.1 Fix blockers from E2E test | Claude Code | 30 min | Whatever broke |
| 5.2 Demo script | Human | 15 min | Write talking points for demo |
| 5.3 Seed compelling demo data | Claude Code | 15 min | Realistic patient/trial data |

### Critical Path

```mermaid
gantt
    title 12-Hour Hackathon Critical Path
    dateFormat HH:mm
    axisFormat %H:%M

    section Foundation
    Project scaffolding           :f1, 00:00, 30m
    Cloud SQL Postgres setup      :f2, 00:00, 20m
    Operational DB module         :f3, after f2, 30m
    Databricks analytics tables   :f4a, 00:00, 20m
    Analytics DB module           :f4b, after f4a, 15m
    ElevenLabs + Twilio setup     :f4, 00:00, 45m
    Agent SDK skeleton            :f5, after f1, 45m

    section Core Agents
    Identity Agent                :a1, after f5, 45m
    Screening Agent               :a2, after a1, 60m
    Scheduling Agent              :a3, after f5, 60m
    Transport Agent               :a4, after a3, 45m
    Reminder Agent                :a5, after a4, 30m
    Voice integration             :a6, after f4, 30m

    section Safety
    Safety tests                  :s1, after a2, 45m
    Supervisor Agent              :s2, after s1, 30m
    Eval scenarios                :s3, after s2, 30m

    section Frontend
    Dashboard (Lovable)           :d1, after a5, 60m
    Dashboard API                 :d2, after a5, 30m
    Deploy to Cloud Run           :d3, after d2, 30m
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
| Databricks SQL warehouse cold start (analytics queries) | Medium | Low | Only used for reference data + batch analytics, not in hot path. Keep warehouse warm for demo. |
| Twilio number not provisioned in time | Low | Critical | Buy number immediately in Phase 1 |
| Patient data privacy in demo | Medium | High | Use synthetic data only; never use real PHI |
| Agent hallucinations during screening | Medium | High | Structured output with Pydantic; supervisor agent review |
| Cloud Run cold start on webhook | Medium | Medium | Set min instances = 1 for API service; use always-on revision |
| Google Calendar OAuth complexity | Medium | Medium | Use service account (no user consent flow) |
| HIPAA BAA not in place for demo | Medium | High | Use synthetic data only during hackathon; BAA process is separate from technical setup |
| Google Calendar MCP not covered by Google BAA | Medium | Medium | Don't store PHI in calendar event titles/descriptions; use opaque reference IDs only |

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
| GCP project + enable APIs | P0 | 10 min | Enable Cloud Run, Cloud SQL, Artifact Registry, Secret Manager, Cloud Tasks, Pub/Sub |
| Cloud SQL Postgres instance | P0 | 5 min | Create instance (`ask-mary-db`), note connection string. Claude Code handles schema migration. |
| Databricks workspace + SQL warehouse | P0 | 15 min | For analytics layer. See Q4 above. |
| Twilio account + phone number | P0 | 10 min | See Q5 above |
| ElevenLabs account + agent creation | P0 | 15 min | Create Conversational AI agent in dashboard |
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
