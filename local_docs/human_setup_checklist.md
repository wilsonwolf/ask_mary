# Ask Mary — Human Setup Checklist

> Everything **you** need to do before and during the build.
> Claude Code handles all code — this list is accounts, credentials, and manual configuration only.
>
> **Estimated total time**: ~5 hours (P0 blocking: ~2h, P1: ~1.5h, P2: ~1.5h)
> Many items can run in parallel.

---

## How to Use This Checklist

1. Work through **P0 items first** — they block all development
2. P1 items block specific phases but can wait until those phases start
3. P2 items are dev workflow infrastructure — can be done in parallel
4. After completing each item, note the credential/value in the **Secrets Collected** section at the bottom
5. Hand the completed secrets list to Claude Code to store in GCP Secret Manager

---

## P0 — Blocking Prerequisites

> **Must complete before Claude Code can start coding.**
> Estimated: ~1h 45m (some items parallelizable)

### 1. Create GCP Project (~10 min)

- [ ] Go to [console.cloud.google.com](https://console.cloud.google.com)
- [ ] Create new project (suggested name: `ask-mary`)
- [ ] Enable the following APIs:
  - [ ] Cloud Run
  - [ ] Cloud SQL Admin
  - [ ] Cloud Storage
  - [ ] Artifact Registry
  - [ ] Secret Manager
  - [ ] Cloud Tasks
  - [ ] Pub/Sub
- [ ] Note your **Project ID**: `___________________________`
- [ ] Note the **Region** you chose (e.g. `us-central1`): `___________________________`

### 2. Create Cloud SQL Postgres Instance (~5 min)

> Requires: GCP project (#1)

- [ ] Go to Cloud SQL in GCP Console
- [ ] Create PostgreSQL instance
  - Instance name: `ask-mary-db`
  - Size: `db-f1-micro` (sufficient for hackathon)
  - Same region as project
  - Set a root password
- [ ] Note **Connection string**: `___________________________`
- [ ] Note **Root password**: `___________________________`

### 3. Create GCS Audio Bucket (~5 min)

> Requires: GCP project (#1)

- [ ] Go to Cloud Storage in GCP Console
- [ ] Create bucket
  - Name: `ask-mary-audio`
  - Same region as compute
  - Standard storage class
- [ ] Grant the Cloud Run service account `roles/storage.objectAdmin` on this bucket
- [ ] Note **Bucket name**: `ask-mary-audio`

### 4. Get OpenAI API Key (~5 min)

- [ ] Go to [platform.openai.com](https://platform.openai.com)
- [ ] Create account or sign in
- [ ] Generate API key (for Agents SDK runtime)
- [ ] Add billing / credits
- [ ] Note **OPENAI_API_KEY**: `___________________________`

### 5. Get Anthropic API Key (~5 min)

- [ ] Go to [console.anthropic.com](https://console.anthropic.com)
- [ ] Create account or sign in
- [ ] Generate API key (for Claude Code dev workflow + Codex review)
- [ ] Add billing / credits
- [ ] Note **ANTHROPIC_API_KEY**: `___________________________`

### 6. Create Twilio Account + Buy Phone Number (~10 min)

- [ ] Go to [twilio.com](https://www.twilio.com)
- [ ] Create account (or sign in)
- [ ] Buy a phone number with **Voice + SMS** capabilities
- [ ] (Optional) Set up WhatsApp Sandbox for WhatsApp channel
- [ ] Note **TWILIO_ACCOUNT_SID**: `___________________________`
- [ ] Note **TWILIO_AUTH_TOKEN**: `___________________________`
- [ ] Note **TWILIO_PHONE_NUMBER**: `___________________________`

### 7. Create ElevenLabs Account (~15 min)

- [ ] Go to [elevenlabs.io](https://elevenlabs.io)
- [ ] Create account (or sign in)
- [ ] Navigate to **Conversational AI** section
- [ ] Create a new Conversational AI 2.0 agent
  - Select backing LLM (Claude or GPT)
  - Enable call recording if available
- [ ] Note **ELEVENLABS_API_KEY**: `___________________________`
- [ ] Note **ELEVENLABS_AGENT_ID**: `___________________________`

### 8. Set Up Databricks Workspace (~15 min)

> Can run in parallel with items 4-7

- [ ] Go to [databricks.com](https://www.databricks.com) or deploy via GCP Marketplace
- [ ] Create workspace
- [ ] Create SQL warehouse (serverless recommended for hackathon)
- [ ] Generate personal access token
- [ ] Note **DATABRICKS_SERVER_HOSTNAME**: `___________________________`
- [ ] Note **DATABRICKS_HTTP_PATH**: `___________________________`
- [ ] Note **DATABRICKS_TOKEN**: `___________________________`

### 9. Configure ElevenLabs + Twilio Integration (~45 min)

> Requires: Twilio (#6) + ElevenLabs (#7) accounts created
> This is **Task 1.7** from the implementation plan

- [ ] In ElevenLabs dashboard, configure the native Twilio integration
  - Enter Twilio Account SID and Auth Token
  - Link your Twilio phone number to the ElevenLabs agent
- [ ] In Twilio console, verify the webhook/SIP trunk is pointing to ElevenLabs
- [ ] **Test**: Call your Twilio number from a real phone
  - [ ] Verify the call connects to ElevenLabs agent
  - [ ] Verify audio quality is acceptable
  - [ ] Verify round-trip latency is reasonable (<2s response)
- [ ] If issues: check Twilio logs, ElevenLabs logs, try alternative voice

---

## P1 — Phase-Specific Tasks

> **These block specific phases but not the initial build.**
> Estimated: ~1h 45m

### 10. Create Google Calendar Service Account (~10 min)

> Needed by: Phase 2 (scheduling agent)

- [ ] Go to GCP Console → APIs & Services → Credentials
- [ ] Create service account (name: `ask-mary-calendar`)
- [ ] Download JSON key file
- [ ] Enable Google Calendar API
- [ ] Share the target calendar with the service account email
- [ ] Note **GOOGLE_CALENDAR_CREDENTIALS** (JSON key file path): `___________________________`
- [ ] Note **GOOGLE_CALENDAR_ID**: `___________________________`

### 11. Create GitHub Fine-Grained PAT (~5 min)

> Needed by: Phase 4 (CI/CD) + dev workflow

- [ ] Go to GitHub → Settings → Developer Settings → Fine-grained tokens
- [ ] Create token with `repo` scope only (for `wilsonwolf/ask_mary`)
- [ ] Set expiration (90 days recommended for hackathon)
- [ ] Note **GITHUB_TOKEN**: `___________________________`

### 12. Create Dashboard with Lovable (~60 min)

> Needed by: Phase 4 (frontend)
> Can start once Phase 2 API endpoints exist

- [ ] Go to [lovable.dev](https://lovable.dev)
- [ ] Generate React/TypeScript dashboard with these screens:
  - [ ] **Participant pipeline** — status view (new → outreach → screening → scheduling → confirmed → completed/no-show)
  - [ ] **Appointments list** — filterable by date range, status, trial
  - [ ] **Handoff queue** — open coordinator tickets with severity + SLA due time
  - [ ] **Conversation logs** — searchable by participant, date, outcome; audio playback controls
  - [ ] **Events timeline** — append-only log visualization
  - [ ] **Analytics summary** — conversion rates, no-show rates, scheduling patterns
- [ ] Export generated code
- [ ] Hand code to Claude Code for API integration

### 13. Run End-to-End Test Call (~30 min)

> Needed by: Phase 5 (demo validation)
> Requires: Full system deployed to Cloud Run

- [ ] Call the Twilio phone number from a real phone
- [ ] Walk through the full participant flow:
  - [ ] 1. Receive disclosure, give verbal consent
  - [ ] 2. Verify identity (DOB + ZIP)
  - [ ] 3. Answer screening questions
  - [ ] 4. Select appointment time
  - [ ] 5. Confirm appointment details
- [ ] Verify in dashboard:
  - [ ] Participant record created with correct data
  - [ ] Appointment booked with correct time
  - [ ] Conversation logged with transcript
  - [ ] Events logged in timeline
  - [ ] Audio recording saved to GCS
- [ ] Note any issues for Claude Code to fix: `___________________________`

---

## P2 — Dev Workflow Infrastructure

> **Parallel track — sets up the Claude Code + Codex iteration loop.**
> Can be done alongside P0/P1.
> Estimated: ~1h 30m

### 14. Create Dev Workflow GCP Resources (~15 min)

> Can reuse the same GCP project from #1 or create a separate one

- [ ] Enable Cloud Run API (if separate project)
- [ ] Enable Artifact Registry API
- [ ] Create Artifact Registry repository for Docker images

### 15. Store All Secrets in GCP Secret Manager (~10 min)

> Requires: GCP project + all API keys collected

- [ ] Store each secret (use the names below exactly):
  - [ ] `TWILIO_ACCOUNT_SID`
  - [ ] `TWILIO_AUTH_TOKEN`
  - [ ] `TWILIO_PHONE_NUMBER`
  - [ ] `ELEVENLABS_API_KEY`
  - [ ] `ELEVENLABS_AGENT_ID`
  - [ ] `DATABRICKS_SERVER_HOSTNAME`
  - [ ] `DATABRICKS_HTTP_PATH`
  - [ ] `DATABRICKS_TOKEN`
  - [ ] `OPENAI_API_KEY`
  - [ ] `ANTHROPIC_API_KEY`
  - [ ] `GITHUB_TOKEN`
  - [ ] `GOOGLE_CALENDAR_CREDENTIALS` (JSON)
  - [ ] `CLOUD_SQL_CONNECTION_STRING`
  - [ ] `CLOUD_SQL_PASSWORD`
- [ ] Grant Cloud Run service account `roles/secretmanager.secretAccessor`

### 16. Build Docker Images (~45 min)

> Requires: GCP project (#14) + secrets stored (#15)
> Claude Code will write the Dockerfiles — you just build and push

- [ ] Build `claude-code-dev` image (see `agent_dev_workflow_plan.md` Section 5.1)
  ```
  docker build -t claude-code-dev -f Dockerfile.claude .
  docker tag claude-code-dev [REGION]-docker.pkg.dev/[PROJECT]/ask-mary/claude-code-dev
  docker push [REGION]-docker.pkg.dev/[PROJECT]/ask-mary/claude-code-dev
  ```
- [ ] Build `codex-review` image (see `agent_dev_workflow_plan.md` Section 5.2)
  ```
  docker build -t codex-review -f Dockerfile.codex .
  docker tag codex-review [REGION]-docker.pkg.dev/[PROJECT]/ask-mary/codex-review
  docker push [REGION]-docker.pkg.dev/[PROJECT]/ask-mary/codex-review
  ```

### 17. Set Up GitHub Actions Workflows (~20 min)

> Requires: GitHub PAT (#11)

- [ ] Add repository secrets in GitHub (Settings → Secrets → Actions):
  - [ ] `GCP_PROJECT_ID`
  - [ ] `GCP_REGION`
  - [ ] `ANTHROPIC_API_KEY`
  - [ ] `OPENAI_API_KEY`
- [ ] Set up GCP Workload Identity Federation (or service account key) for GitHub Actions
- [ ] Claude Code will create the workflow YAML files — just verify they appear in `.github/workflows/`

### 18. Demo Prep (~30 min)

> Last step before the hackathon demo

- [ ] Write demo talking points script:
  - [ ] Happy path: outreach → screening → booking → confirmation
  - [ ] Handoff trigger scenario (safety keyword detected)
  - [ ] No-show rescue flow
  - [ ] Dashboard tour
- [ ] Seed demo data (Claude Code can help):
  - [ ] 5-10 realistic participants
  - [ ] 2-3 clinical trials with visit templates
  - [ ] Pre-populated events timeline
  - [ ] Sample handoff tickets in queue

---

## Secrets Collected

> Fill in as you complete each task. **Do not commit this file with real values.**
> Transfer to GCP Secret Manager (#15), then delete the values from this file.

| Secret Name | Value | Source Task |
|-------------|-------|-------------|
| `GCP_PROJECT_ID` | | #1 |
| `GCP_REGION` | | #1 |
| `CLOUD_SQL_CONNECTION_STRING` | | #2 |
| `CLOUD_SQL_PASSWORD` | | #2 |
| `OPENAI_API_KEY` | | #4 |
| `ANTHROPIC_API_KEY` | | #5 |
| `TWILIO_ACCOUNT_SID` | | #6 |
| `TWILIO_AUTH_TOKEN` | | #6 |
| `TWILIO_PHONE_NUMBER` | | #6 |
| `ELEVENLABS_API_KEY` | | #7 |
| `ELEVENLABS_AGENT_ID` | | #7 |
| `DATABRICKS_SERVER_HOSTNAME` | | #8 |
| `DATABRICKS_HTTP_PATH` | | #8 |
| `DATABRICKS_TOKEN` | | #8 |
| `GOOGLE_CALENDAR_CREDENTIALS` | (JSON file) | #10 |
| `GOOGLE_CALENDAR_ID` | | #10 |
| `GITHUB_TOKEN` | | #11 |

---

## Dependency Graph

```
#1 GCP Project
├── #2 Cloud SQL ──────────────────┐
├── #3 GCS Bucket                  │
├── #10 Google Calendar SA         │
├── #14 Dev Workflow GCP           │
│   └── #15 Store Secrets ─────── │ ──→ #16 Build Docker Images
│                                  │         └── #17 GitHub Actions
#4 OpenAI Key ─────────────────────┤
#5 Anthropic Key ──────────────────┤
#6 Twilio ─────────┐               │
#7 ElevenLabs ─────┤               │
                   ▼               │
              #9 Integration ──────┤
                                   ▼
                         Claude Code Phase 1-3
                                   │
                                   ▼
                         #12 Dashboard (Lovable)
                                   │
                                   ▼
                         #13 E2E Test Call
                                   │
                                   ▼
                         #18 Demo Prep
```

---

## Quick Start (Optimal Order)

If you want to minimize wall-clock time, do these in parallel tracks:

**Track A** (cloud infra — ~30 min):
`#1 → #2 + #3 (parallel) → #14 → #15`

**Track B** (API keys — ~15 min, parallel with Track A):
`#4 + #5 (parallel)`

**Track C** (voice — ~70 min, parallel with Track A):
`#6 + #7 (parallel) → #9`

**Track D** (data platform — ~15 min, parallel with all):
`#8`

**After Tracks A-D complete**: Hand secrets to Claude Code → development begins

**Later** (during/after coding):
`#10 → #11 → #12 → #13 → #16 + #17 → #18`
