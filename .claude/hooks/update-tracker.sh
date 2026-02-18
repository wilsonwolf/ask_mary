#!/usr/bin/env bash
# Hook: Checks if the implementation tracker is stale.
# Runs on Stop — reminds Claude to update the tracker.
# Remove this hook once implementation is complete.

TRACKER="$CLAUDE_PROJECT_DIR/local_docs/implementation_tracker.md"

if [ ! -f "$TRACKER" ]; then
    echo '{"ok": false, "reason": "Implementation tracker missing at local_docs/implementation_tracker.md. Create or restore it."}'
    exit 0
fi

# Check if tracker was modified in the last 30 minutes
if [ "$(uname)" = "Darwin" ]; then
    # macOS: stat -f %m gives epoch seconds
    LAST_MOD=$(stat -f %m "$TRACKER" 2>/dev/null || echo 0)
else
    LAST_MOD=$(stat -c %Y "$TRACKER" 2>/dev/null || echo 0)
fi

NOW=$(date +%s)
AGE=$(( NOW - LAST_MOD ))

# If tracker is older than 30 minutes and there are new .py files, warn
if [ "$AGE" -gt 1800 ]; then
    # Count .py files modified in the last 30 min
    RECENT_PY=$(find "$CLAUDE_PROJECT_DIR/src" -name "*.py" -newer "$TRACKER" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$RECENT_PY" -gt 0 ]; then
        echo "{\"ok\": false, \"reason\": \"Implementation tracker is stale ($RECENT_PY new/modified .py files since last update). Update local_docs/implementation_tracker.md with current progress before stopping.\"}"
        exit 0
    fi
fi

echo '{"ok": true}'
