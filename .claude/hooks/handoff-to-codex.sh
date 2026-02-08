#!/bin/bash
# Orchestration: Push PR + trigger Codex review after Ralph loop completes
# Runs as Stop hook — only acts if .ralph-complete marker exists

# Only run if Ralph loop has COMPLETED (marker file present)
if [ ! -f "$CLAUDE_PROJECT_DIR/.ralph-complete" ]; then
  exit 0  # Ralph hasn't signaled completion yet — don't handoff
fi

# Clean up marker
rm -f "$CLAUDE_PROJECT_DIR/.ralph-complete"

BRANCH=$(git -C "$CLAUDE_PROJECT_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null)

# Don't push from main or dev
if [ "$BRANCH" = "main" ] || [ "$BRANCH" = "dev" ]; then
  echo "WARNING: Ralph completed on '$BRANCH' — skipping PR creation. Push to a feature branch." >&2
  exit 0
fi

# Push branch and create PR
cd "$CLAUDE_PROJECT_DIR"
git push -u origin "$BRANCH" 2>&1

# Create PR with 7-guideline summary
gh pr create \
  --title "$(git log -1 --format=%s)" \
  --body "$(cat <<'PREOF'
## Auto-generated PR from Claude Code + Ralph Wiggum loop

### Compliance Summary
- [ ] DRY: Shared utilities in src/shared/, no duplication
- [ ] Clean Code: ruff + mypy passing, functions <20 lines
- [ ] TDD: Tests written before implementation
- [ ] Architecture: No cross-boundary imports
- [ ] Immutable Tests: tests/safety/ unchanged
- [ ] Documentation: Docstrings + README.md present
- [ ] Plan compliance: Implementation matches plan

### Review requested from Codex
This PR is ready for automated review via the codex-review workflow.
PREOF
)" 2>&1

echo "PR created. Codex review will be triggered by GitHub Actions." >&2
exit 0
