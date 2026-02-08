# src/agents/ — Agent Implementations

One file per agent, using the OpenAI Agents SDK (`from agents import Agent`).

## Architecture

- **No agent imports another agent.** Agents communicate only via orchestrator handoffs.
- `pipeline.py` is the assembly module that wires the orchestrator to all agents.
- Each agent defines its `instructions` (system prompt) and will later define `tools` (function tools with Pydantic validation).

## Files

| File | Agent | Role |
|------|-------|------|
| `orchestrator.py` | orchestrator | Central coordinator — routes conversations, enforces gate sequence |
| `outreach.py` | outreach | Initiates contact, enforces DNC, manages retry cadence |
| `identity.py` | identity | Verifies identity (DOB year + ZIP via DTMF), detects duplicates |
| `screening.py` | screening | Eligibility screening, FAQ, caregiver auth, provenance annotation |
| `scheduling.py` | scheduling | Geo gate, Google Calendar slot booking, 12h confirmation window |
| `transport.py` | transport | Uber Health ride booking (mock), pickup verification |
| `comms.py` | comms | Event-driven communications cadence (T-48h through T+0) |
| `supervisor.py` | supervisor | Post-call transcript audit, compliance check, deception detection |
| `adversarial.py` | adversarial | Re-screens eligibility with different phrasing, EHR cross-reference |
| `pipeline.py` | — | Assembly module: wires orchestrator handoffs to all agents |

## Key Decision

The `from agents import Agent` import refers to the **OpenAI Agents SDK** third-party package (`openai-agents`), not to files within this directory.
