# Ask Mary — Human Setup Checklist

> Everything **you** need to do before and during the build.
> Claude Code handles all code — this list is accounts, credentials, and manual configuration only.
>
> **Approach**: Build-and-deploy simultaneously. All services run in GCP from hour zero — no local Postgres, no mocks. Your local machine runs Claude Code; everything else is cloud.
>
> **Estimated total time**: ~4.5 hours (P0: ~30 min, P1: ~1.5h, P2: ~1h, P3: ~1.5h)

---

## How to Use This Checklist

1. Work through **P0 items first** — Claude Code is blocked until these are done
2. P1 items block voice integration — start these while Claude Code builds Phase 1
3. P2 items block specific later phases — do when Claude Code reaches that phase
4. P3 items are post-hackathon dev workflow infrastructure
5. After completing each item, note the credential/value in the **Secrets Collected** section at the bottom

---

## P0 — Blocks All Development

> **Claude Code cannot start coding without these.**
> Estimated: ~30 min (parallelizable)

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

### 2. Create Cloud SQL Postgres Instance (~10 min)

> Requires: GCP project (#1)
> We build against Cloud SQL from the start — no local Postgres.

- [ ] Go to Cloud SQL in GCP Console
- [ ] Create PostgreSQL instance
  - Instance name: `ask-mary-db`
  - Database version: PostgreSQL 15+
  - Size: `db-f1-micro` (sufficient for hackathon)
  - Same region as project
  - Set a root password
- [ ] Create a database named `ask_mary_dev`
- [ ] Install the Cloud SQL Auth Proxy locally:
  ```
  # macOS
  brew install cloud-sql-proxy
  # Then run (keep this terminal open):
  cloud-sql-proxy PROJECT_ID:REGION:ask-mary-db
  ```
  This lets your local machine connect to Cloud SQL via `localhost:5432`
- [ ] Note **Instance connection name** (PROJECT:REGION:ask-mary-db): `___________________________`
- [ ] Note **Root password**: `___________________________`

### 3. Get OpenAI API Key (~5 min)

> Can run in parallel with #1 and #2

- [ ] Go to [platform.openai.com](https://platform.openai.com)
- [ ] Create account or sign in
- [ ] Generate API key (this is the application runtime — agents use OpenAI for reasoning)
- [ ] Add billing / credits
- [ ] Note **OPENAI_API_KEY**: `___________________________`

**After #1, #2, #3 are done**: Hand credentials to Claude Code. Development starts immediately.

---

## P1 — Voice Integration

> **Blocks voice agent testing. Start these while Claude Code builds Phase 1 (scaffolding, DB, agent stubs).**
> Estimated: ~1h 30m

### 4. Create Twilio Account + Buy Phone Number (~10 min)

- [ ] Go to [twilio.com](https://www.twilio.com)
- [ ] Create account (or sign in)
- [ ] Buy a phone number with **Voice + SMS** capabilities
- [ ] Enable Advanced Opt-Out (for DNC STOP handling)
- [ ] (Optional) Set up WhatsApp Sandbox for WhatsApp channel
- [ ] Note **TWILIO_ACCOUNT_SID**: `___________________________`
- [ ] Note **TWILIO_AUTH_TOKEN**: `___________________________`
- [ ] Note **TWILIO_PHONE_NUMBER**: `___________________________`

### 5. Create ElevenLabs Account (~15 min)

- [ ] Go to [elevenlabs.io](https://elevenlabs.io)
- [ ] Create account (or sign in)
- [ ] Navigate to **Conversational AI** section
- [ ] Create a new Conversational AI 2.0 agent
  - Select backing LLM (Claude or GPT)
  - Enable call recording if available
- [ ] **Enable Overrides** in agent → Security settings tab (required for per-call prompt injection)
- [ ] **Enable Authentication** in agent settings (required for passing custom parameters)
- [ ] Set up agent prompt template with dynamic variable placeholders:
  - `{{participant_name}}` — filled per-call with participant name
  - `{{trial_name}}` — filled per-call with trial name
  - `{{site_name}}` — filled per-call with trial site name
  - `{{coordinator_phone}}` — filled per-call for handoff
  - Note: Inclusion/exclusion criteria are injected via `conversation_config_override` (system prompt override), not as individual variables
- [ ] Note **ELEVENLABS_API_KEY**: `___________________________`
- [ ] Note **ELEVENLABS_AGENT_ID**: `___________________________`

### 6. Configure ElevenLabs + Twilio Integration (~45 min)

> Requires: Twilio (#4) + ElevenLabs (#5) accounts created
> This is **Task 1.7** from the implementation plan

- [ ] In ElevenLabs dashboard → Telephony → Phone Numbers:
  - Click **Import number** → select **From Twilio**
  - Enter Twilio Account SID, Auth Token, and phone number
  - ElevenLabs auto-configures the Twilio webhook (no manual SIP trunk needed)
- [ ] Link the imported number to your ElevenLabs agent (select agent from dropdown)
- [ ] In Twilio console → Phone Numbers → your number → Voice & Fax:
  - Verify "A call comes in" shows a webhook URL set by ElevenLabs
  - Note: SIP trunk field will be blank — this is expected (native integration uses webhooks, not SIP)
- [ ] **Test**: Call your Twilio number from a real phone
  - [ ] Verify the call connects to ElevenLabs agent
  - [ ] Verify audio quality is acceptable
  - [ ] Verify round-trip latency is reasonable (<2s response)
- [ ] If issues: check Twilio debugger logs, ElevenLabs conversation logs, try alternative voice

### 7. Create GCS Audio Bucket (~5 min)

> Needed once voice recording is wired up

- [ ] Go to Cloud Storage in GCP Console
- [ ] Create bucket
  - Name: `ask-mary-audio`
  - Same region as compute
  - Standard storage class
- [ ] Grant the Cloud Run service account `roles/storage.objectAdmin` on this bucket
- [ ] Note **Bucket name**: `ask-mary-audio`

---

## P2 — Phase-Specific Tasks

> **These block specific later phases. Do them when Claude Code reaches that phase.**
> Estimated: ~1h

### 8. Set Up Databricks Workspace (~15 min)

> Needed by: Phase 1 (analytics tables, trial/EHR reference data)
> Can start in parallel with P1 items

- [ ] Go to [databricks.com](https://www.databricks.com) or deploy via GCP Marketplace
- [ ] Create workspace
- [ ] Create SQL warehouse (serverless recommended for hackathon)
- [ ] Generate personal access token
- [ ] Note **DATABRICKS_SERVER_HOSTNAME**: `___________________________`
- [ ] Note **DATABRICKS_HTTP_PATH**: `___________________________`
- [ ] Note **DATABRICKS_TOKEN**: `___________________________`

### 9. Create Google Calendar Service Account (~10 min)

> Needed by: Phase 2 (scheduling agent)

- [ ] Go to GCP Console → APIs & Services → Credentials
- [ ] Create service account (name: `ask-mary-calendar`)
- [ ] Download JSON key file
- [ ] Enable Google Calendar API
- [ ] Share the target calendar with the service account email
- [ ] Note **GOOGLE_CALENDAR_CREDENTIALS** (JSON key file path): `___________________________`
- [ ] Note **GOOGLE_CALENDAR_ID**: `___________________________`

### 10. Create GitHub Fine-Grained PAT (~5 min)

> Needed by: Phase 4 (CI/CD) + dev workflow

- [ ] Go to GitHub → Settings → Developer Settings → Fine-grained tokens
- [ ] Create token with `repo` scope only (for `wilsonwolf/ask_mary`)
- [ ] Set expiration (90 days recommended)
- [ ] Note **GITHUB_TOKEN**: `___________________________`

### 11. Run Demo per `local_docs/demo_script.md` (~30 min)

> Needed by: Phase 5 (demo validation)
> Requires: Full system deployed to Cloud Run
> This is the **success gate** — see `local_docs/demo_script.md` for the full script

- [ ] Click "Start Demo Call" on dashboard
- [ ] Answer on speaker, walk through the 60-second demo flow:
  - [ ] 1. Disclosure + consent (press 1)
  - [ ] 2. Identity verification (enter DOB year + ZIP via DTMF)
  - [ ] 3. Screening questions (press 1/2 for yes/no)
  - [ ] 4. Calendar availability shown, select slot
  - [ ] 5. Teach-back confirmation
  - [ ] 6. Transport booking
- [ ] Verify dashboard updates in real-time:
  - [ ] Call & Safety Gates panel shows flags flipping
  - [ ] Eligibility panel shows answers + status
  - [ ] Scheduling panel shows HELD → BOOKED
  - [ ] Transport panel shows REQUESTED → CONFIRMED
  - [ ] Events feed scrolls with every action
- [ ] (Optional) Safety escalation: say "chest pain" → verify handoff_queue entry
- [ ] Note any issues for Claude Code to fix: `___________________________`

### 12. Demo Prep (~30 min)

> Last step before the demo

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

## P3 — Dev Workflow Infrastructure (Post-Hackathon)

> **Sets up the Claude Code + Codex autonomous iteration loop.**
> Not needed during the hackathon — you are the review layer while at the keyboard.
> Estimated: ~1h 30m

### 14. Get Anthropic API Key (~5 min)

> For remote Codex review containers only — you already have Claude Code running locally

- [ ] Go to [console.anthropic.com](https://console.anthropic.com)
- [ ] Create account or sign in
- [ ] Generate API key
- [ ] Note **ANTHROPIC_API_KEY**: `___________________________`

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
  - [ ] `MARY_ID_PEPPER` (generated by Claude Code — random 32-byte hex string for HMAC participant ID hashing)
- [ ] Grant Cloud Run service account `roles/secretmanager.secretAccessor`

### 16. Build Docker Images (~45 min)

> Requires: GCP project + secrets stored (#15)
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

> Requires: GitHub PAT (#10)

- [ ] Add repository secrets in GitHub (Settings → Secrets → Actions):
  - [ ] `GCP_PROJECT_ID`
  - [ ] `GCP_REGION`
  - [ ] `ANTHROPIC_API_KEY`
  - [ ] `OPENAI_API_KEY`
- [ ] Set up GCP Workload Identity Federation (or service account key) for GitHub Actions
- [ ] Claude Code will create the workflow YAML files — just verify they appear in `.github/workflows/`

---

## Secrets Collected

> Fill in as you complete each task. **Do not commit this file with real values.**
> Transfer to GCP Secret Manager (#15), then delete the values from this file.

| Secret Name | Value | Source Task |
|-------------|-------|-------------|
| `GCP_PROJECT_ID` | | #1 |
| `GCP_REGION` | | #1 |
| `CLOUD_SQL_INSTANCE_CONNECTION` | | #2 |
| `CLOUD_SQL_PASSWORD` | | #2 |
| `OPENAI_API_KEY` | | #3 |
| `TWILIO_ACCOUNT_SID` | | #4 |
| `TWILIO_AUTH_TOKEN` | | #4 |
| `TWILIO_PHONE_NUMBER` | | #4 |
| `ELEVENLABS_API_KEY` | | #5 |
| `ELEVENLABS_AGENT_ID` | | #5 |
| `DATABRICKS_SERVER_HOSTNAME` | | #8 |
| `DATABRICKS_HTTP_PATH` | | #8 |
| `DATABRICKS_TOKEN` | | #8 |
| `GOOGLE_CALENDAR_CREDENTIALS` | (JSON file) | #9 |
| `GOOGLE_CALENDAR_ID` | | #9 |
| `GITHUB_TOKEN` | | #10 |
| `ANTHROPIC_API_KEY` | | #14 |

---

## Dependency Graph

```
#1 GCP Project ──┐
#2 Cloud SQL ────┤ (P0 — blocks all coding)
#3 OpenAI Key ───┘
        │
        ▼
  Claude Code starts building
        │
        ├── Meanwhile you do P1:
        │   #4 Twilio ─────────┐
        │   #5 ElevenLabs ─────┤
        │                      ▼
        │                 #6 Integration
        │                 #7 GCS Bucket
        │
        ├── P2 (as phases need them):
        │   #8 Databricks (Phase 1 analytics)
        │   #9 Google Calendar SA (Phase 2)
        │   #10 GitHub PAT (Phase 4)
        │   #11 Demo dry run (Phase 5)
        │   #12 Demo Prep (Phase 5)
        │
        └── P3 (post-hackathon):
            #14 Anthropic Key
            #15 Secret Manager
            #16 Docker Images
            #17 GitHub Actions
```

---

## Quick Start

**Right now (3 items in parallel, ~15 min):**

| You do | Time |
|--------|------|
| #1 Create GCP project + enable 7 APIs | 10 min |
| #2 Create Cloud SQL instance + install Auth Proxy | 10 min |
| #3 Get OpenAI API key | 5 min |

**Then hand credentials to Claude Code. Coding starts.**

**While Claude Code builds Phase 1 (~2 hours), you do:**

| You do | Time |
|--------|------|
| #4 + #5 Twilio + ElevenLabs (parallel) | 15 min |
| #6 Wire them together + test call | 45 min |
| #7 GCS bucket | 5 min |
| #8 Databricks workspace | 15 min |

**When Claude Code reaches Phase 2:**
`#9 Google Calendar SA`

**When Claude Code reaches Phase 4:**
`#10 GitHub PAT`

**After deployment:**
`#11 Demo dry run (per local_docs/demo_script.md) → #12 Demo Prep`
