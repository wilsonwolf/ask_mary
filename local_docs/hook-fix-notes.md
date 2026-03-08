# Architecture Hook Fix Notes

## Current Configuration (`.claude/settings.json`)

The PreToolUse hook includes an LLM-based architecture guard with these rules:

```
1. Files in src/agents/ must NOT import from other agent files in src/agents/.
2. Files in src/services/ must NOT import from src/agents/.
3. Allowed imports: api/ and workers/ CAN import from agents/, services/, db/, shared/.
   agents/ CAN import from services/, db/, shared/.
   services/ CAN import from db/, shared/.
   db/ CAN import from shared/ only.
   shared/ must NOT import from any other layer.
4. New Python files must be in a valid src/ subdirectory.
5. Files in tests/ are exempt from all rules.
```

## Known Issues

### KI-2: Hook blocks valid `agents/ -> services/` imports
The architecture guard prompt correctly states agents CAN import from services, but the LLM-based evaluation sometimes incorrectly flags these as violations. This is a prompt interpretation issue, not a rule issue.

### KI-7: Hook blocks valid `agents/ -> db/` imports
Same pattern — the rules allow `agents/ -> db/` imports but the LLM guard occasionally flags them.

## Root Cause

The architecture guard is an LLM prompt, not a deterministic regex check. This means:
- It can misinterpret compliant edits as violations
- Results are non-deterministic (same edit may pass or fail)
- The `CRITICAL` instruction to respond `{"ok": true}` for compliant edits helps but doesn't eliminate false positives

## Recommended Fix

### Option A: Add explicit examples to the prompt (Minimal change)
Add to the architecture guard prompt:
```
EXAMPLES OF VALID IMPORTS (DO NOT BLOCK):
- src/agents/identity.py importing from src/services/twilio_client.py ✓
- src/agents/scheduling.py importing from src/db/postgres.py ✓
- src/agents/outreach.py importing from src/shared/types.py ✓
```

### Option B: Replace LLM guard with deterministic script (Recommended)
Create `.claude/hooks/architecture-guard.sh` that uses grep/ast to check import rules:
- Parse the file being edited for import statements
- Check against a whitelist of allowed import directions
- Deterministic, fast, no false positives

### Option C: Reduce guard scope
Only apply the guard to `src/shared/` files (the only layer with strict "must NOT import from" rules). All other layers have permissive import rules that rarely need guarding.

## Action Required
Choose one option and implement. Option B is recommended for reliability.
