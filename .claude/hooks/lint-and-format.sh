#!/bin/bash
# Guideline 2: Run ruff format + ruff check + mypy on changed Python files
# Runs after every Write/Edit to a .py file
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Only check Python files
if [[ "$FILE_PATH" != *.py ]]; then
  exit 0
fi

# Skip if file doesn't exist (was deleted)
if [ ! -f "$FILE_PATH" ]; then
  exit 0
fi

# Check if tools are installed (graceful during initial setup)
if ! command -v ruff &> /dev/null; then
  exit 0  # ruff not installed yet — skip silently
fi

# Format (auto-fix)
ruff format "$FILE_PATH" 2>/dev/null

# Lint (auto-fix what we can, report the rest)
LINT_OUTPUT=$(ruff check "$FILE_PATH" --fix 2>&1)
LINT_EXIT=$?

# Type check (only if mypy is installed)
MYPY_EXIT=0
MYPY_OUTPUT=""
if command -v mypy &> /dev/null; then
  MYPY_OUTPUT=$(mypy "$FILE_PATH" --strict --no-error-summary 2>&1)
  MYPY_EXIT=$?
fi

if [ $LINT_EXIT -ne 0 ] || [ $MYPY_EXIT -ne 0 ]; then
  echo "Clean code violations found:" >&2
  [ $LINT_EXIT -ne 0 ] && echo "LINT: $LINT_OUTPUT" >&2
  [ $MYPY_EXIT -ne 0 ] && echo "TYPE: $MYPY_OUTPUT" >&2
  exit 2  # Block — Claude must fix
fi

exit 0
