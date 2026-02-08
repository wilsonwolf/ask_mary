#!/bin/bash
# Guideline 6: Block any modification to tests/safety/
# This is the most critical hook — safety tests are NEVER modifiable by agents.
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Block any modification to tests/safety/
if echo "$FILE_PATH" | grep -q "tests/safety/"; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: "BLOCKED: tests/safety/ is immutable. If a safety test fails, fix the IMPLEMENTATION — not the test."
    }
  }'
else
  exit 0
fi
