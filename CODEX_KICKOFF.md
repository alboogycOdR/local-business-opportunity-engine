# Codex Kickoff — Sprint 1

Use this file as the first instruction set after cloning the repository.

## First instruction to Codex

Read `AGENTS.md`, `docs/BLUEPRINT.md`, `docs/DECISIONS.md`, `docs/SPRINT_01.md`, `docs/MVP_BACKLOG.md`, and the existing schema/config files completely before modifying the repository.

Then execute **Sprint 1 only**.

### Sprint 1 goals

Establish a production-minded development foundation with:

- coherent Python project/package setup
- FastAPI core application
- PostgreSQL database connectivity
- Redis connectivity for future worker jobs
- database migrations
- campaign, business, source observation/provenance, pipeline event, suppression, and job/idempotency models
- authoritative lead state machine with tested transition rules
- manual JSON/CSV lead import path
- `/health` and `/ready` endpoints
- structured logging baseline
- automated tests
- formatting, linting, and type checking
- CI validation
- clear local developer setup documentation

### Explicitly out of scope

Do not implement:

- Maps scraping
- Google Places API calls
- browser auditing
- LLM integrations
- demo generation
- automated outreach
- production cloud deployment

Interfaces/stubs are allowed only when necessary for the Sprint 1 domain boundary.

### Working method

1. Inspect the repo and propose a concise Sprint 1 implementation plan.
2. Implement in logical slices.
3. Run tests/static checks after each slice.
4. Fix failures before continuing.
5. Make descriptive commits at stable milestones.
6. Do not change architecture silently.
7. Stop once `docs/SPRINT_01.md` acceptance criteria are satisfied.

### Completion report

At completion, print a concise report with:

- acceptance criteria checklist
- commands run and results
- commits created
- architectural deviations
- unresolved issues
- recommended Sprint 2 starting point
