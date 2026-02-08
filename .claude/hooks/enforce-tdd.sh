#!/bin/bash
# Guideline 3: Block task completion if tests don't pass (safety net behind Superpowers TDD)
# Only runs on TaskCompleted events

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
  exit 0  # pytest not installed yet — skip silently during setup
fi

# Check if tests directory exists
if [ ! -d "$CLAUDE_PROJECT_DIR/tests" ]; then
  exit 0  # No tests directory yet — skip during initial scaffolding
fi

# Check if there are any test files
TEST_COUNT=$(find "$CLAUDE_PROJECT_DIR/tests" -name "test_*.py" 2>/dev/null | wc -l)
if [ "$TEST_COUNT" -eq 0 ]; then
  exit 0  # No test files yet — skip
fi

RESULT=$(cd "$CLAUDE_PROJECT_DIR" && python -m pytest tests/ --tb=short -q 2>&1)
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
  echo "TDD gate failed — tests must pass before task completion:" >&2
  echo "$RESULT" >&2
  exit 2  # Block task completion
fi

exit 0
