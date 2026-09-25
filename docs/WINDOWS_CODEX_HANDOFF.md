# Windows → Codex CLI Handoff

This is the exact handoff once the bootstrap ZIP has been downloaded.

## 1. Clone the empty/new GitHub repository

Open PowerShell in the parent folder where you keep source code:

```powershell
git clone https://github.com/alboogycOdR/local-business-opportunity-engine.git
cd local-business-opportunity-engine
```

## 2. Copy bootstrap contents into the cloned repository

Extract the bootstrap ZIP. Copy the **contents inside its `local-business-opportunity-engine` folder** into the cloned Git repository root.

After copying, this should exist:

```powershell
Test-Path .\AGENTS.md
Test-Path .\CODEX_KICKOFF.md
Test-Path .\docs\SPRINT_01.md
```

All three should return `True`.

## 3. Inspect before committing

```powershell
git status
git diff -- . ':!*.zip'
```

Do not continue if you see credentials, `.env`, prospect datasets, or unrelated files.

## 4. Commit and push the bootstrap

```powershell
git add .
git commit -m "chore: bootstrap LBOE architecture and Codex development environment"
git push origin main
```

## 5. Start local infrastructure sanity check

Docker Desktop should be running.

```powershell
docker compose config
docker compose up -d postgres redis
docker compose ps
```

You may then stop them if desired:

```powershell
docker compose down
```

## 6. Start Codex

From the repository root:

```powershell
codex
```

First message to Codex:

```text
Read AGENTS.md and CODEX_KICKOFF.md completely.
Execute Sprint 1 exactly as specified.
Do not begin Sprint 2.
```

## 7. Do not leave Codex unattended without Git checkpoints

The repository is durable project memory. Ask Codex to commit stable milestones and push regularly after tests pass.

At Sprint 1 completion, bring the completion report and/or GitHub repo state back to ChatGPT for review before authorizing Sprint 2.
