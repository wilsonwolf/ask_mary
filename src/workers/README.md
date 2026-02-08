# src/workers/ — Background Task Handlers

Cloud Tasks callback handlers and background job processors.

## Planned Files (Phase 4)

| File | Role |
|------|------|
| `reminders.py` | Cloud Tasks callbacks for confirmation checks, T-48h/T-24h reminders, retry cadence, slot expiry |
| `cdc.py` | App-level Pub/Sub → Databricks Delta Lake bridge (event replication + periodic sweep for stragglers) |

## Architecture Rules

- Workers receive Cloud Tasks HTTP callbacks or Pub/Sub push messages.
- Each handler uses an `idempotency_key` dedup guard before execution.
- Workers may import from `services/`, `db/`, and `shared/` but never from `agents/`.
