# Contributing

This project is built with an agentic SDLC: Claude Code agents draft and implement, people review and decide.

## Workflow (a "bolt")
1. Pick one task from `specs/<unit>/tasks.md`.
2. Create a worktree and branch: `git worktree add ../ra-T4.06 -b T4.06-short-name`.
3. Start Claude Code there and run `/bolt T4.06` in plan mode; approve or edit the plan.
4. Tests first: add the acceptance test (from `features/`) and make sure it fails.
5. Implement; hooks lint and scan every edit.
6. For AI changes run `make eval-quick` and include the eval diff.
7. Open the PR with `/pr`. CI, the eval gate and AI reviewers run; a human code owner approves.
8. Squash merge. The bolt is done when acceptance tests and evals pass in Test.

## Rules
- One task per branch; commit messages start with the task ID.
- No production credentials in any developer or agent session.
- Do not change ADRs, agent cards, tool contracts or design specs inside a bolt; raise a question instead.
- AI reviewer comments are advisory; a human code owner approval is required.

## Definition of done
- Acceptance tests and unit tests pass; coverage on changed code >= 80%.
- For AI units: no eval metric drops more than 1 point, no safety failure, cost per case within +10%.
- Runbook and docs updated.
