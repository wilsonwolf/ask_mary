#!/bin/bash
# Guideline 5: Warn if working directly on main or dev (safety net behind Superpowers)
# Advisory only — does not block

BRANCH=$(git -C "$CLAUDE_PROJECT_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null)

if [ "$BRANCH" = "main" ] || [ "$BRANCH" = "dev" ]; then
  echo "WARNING: You are on '$BRANCH'. For feature work, create a worktree:"
  echo "  git worktree add ../ask-mary-{feature} -b feature/{feature}"
  echo ""
  echo "Active worktrees:"
  git -C "$CLAUDE_PROJECT_DIR" worktree list
fi

exit 0  # Advisory only, doesn't block
