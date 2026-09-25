# Bootstrap → Codex CLI Handoff Checklist

Use this after extracting this bootstrap into the Git repository.

## Before Codex

- [ ] Repository URL is `https://github.com/alboogycOdR/local-business-opportunity-engine`.
- [ ] Bootstrap files are copied into the repository root.
- [ ] `git status` shows only intended bootstrap files.
- [ ] No `.env`, API key, prospect list, or private asset is present.
- [ ] Initial bootstrap commit is created and pushed to `main`.

Suggested commit:

```text
chore: bootstrap LBOE architecture and Codex development environment
```

## Start Codex

From repository root:

```text
codex
```

Then tell Codex:

```text
Read AGENTS.md and CODEX_KICKOFF.md completely.
Execute Sprint 1 exactly as specified.
Do not begin Sprint 2.
```

## During Sprint 1

Prefer milestone commits such as:

- `chore: configure Python workspace and dev tooling`
- `feat(db): add campaign and business foundation schema`
- `feat(domain): implement lead state transition engine`
- `feat(api): add campaign and manual import endpoints`
- `test: add Sprint 1 integration coverage`
- `ci: validate lint typecheck and tests`

## Review gate

Before moving to Sprint 2, review:

- Sprint 1 completion report
- test results
- migration status
- git history
- any ADR changes
- open TODOs
