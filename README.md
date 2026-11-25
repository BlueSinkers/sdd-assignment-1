# Madrid Hoops (Assignment 2)

Madrid Hoops helps basketball teams in Madrid find opponents and agree on games. Assignment 2 splits the Assignment 1 monolith into **two services** (Teams and Games), a **static UI**, SQL Server, Compose, and CI. Azure CD comes next.

## Architecture

```
Browser (ui/) ──HTTPS/HTTP──► Teams service ──► teams DB
              └────────────► Games service ──► games DB
                                   │ HTTP TEAMS_URL
                                   └──► Teams
```

- **Teams** — register/login, team list, `GET /api/teams/{id}` summary (the seam).
- **Games** — courts, challenges, dashboard, turnout, stats. Calls Teams over HTTP with a timeout; designed 503 / degrade when Teams is down.
- **UI** — static files in `ui/`, configured by `ui/config.js` (not hardcoded service URLs).

## Run locally

```bash
cp .env.example .env   # set strong MSSQL passwords
docker compose up --build
```

Open http://localhost:8080  
- Teams API: http://localhost:8001/health  
- Games API: http://localhost:8002/health  

## Run a single service (needs SQL Server)

```bash
export DATABASE_URL='mssql+pymssql://teams_user:PASSWORD@localhost:1433/teams'
export SECRET_KEY=dev-only-change-me
export UI_ORIGIN=http://localhost:8080
cd services/teams && python app.py
```

## Tests and coverage

```bash
cd services/teams && pip install -r requirements.txt -r requirements-dev.txt
PYTHONPATH=. pytest -q --cov=teams.logic --cov=auth --cov-fail-under=70

cd services/games && pip install -r requirements.txt -r requirements-dev.txt
PYTHONPATH=. pytest -q --cov=games.logic --cov=games.teams_client --cov=games.store --cov-fail-under=70
```

Cross-seam behaviour is covered by Games route tests that stub Teams (`TeamsUnavailable` → HTTP 503).

## Configuration

| Variable | Where | Purpose |
|---|---|---|
| `DATABASE_URL` | each service | SQL Server connection (secret) |
| `SECRET_KEY` | both services | Signs/verifies captain bearer tokens (must match) |
| `TEAMS_URL` | games | Base URL of Teams |
| `TEAMS_TIMEOUT_S` | games | Outbound timeout (default 2) |
| `UI_ORIGIN` | both | CORS allow-list |
| `PORT` | both | Listen port (default 8000), binds `0.0.0.0` |
| `VERSION` | both | Git SHA in `/health` |

No secrets are committed. Use `.env` locally (gitignored) and GitHub Actions secrets on Azure.

## Azure

Not deployed yet. Fill `student` / `prefix` / Azure names in `system.yaml` with your IE username, then follow the Blackboard setup guide. CD workflow will land in a later PR.

Live URL: *pending*

## Project layout

```
services/teams/     Teams API, migrations, Dockerfile, OpenAPI
services/games/     Games API, teams_client, migrations, Dockerfile, OpenAPI
ui/                 Static site (nginx in compose)
db/init.sh          Idempotent local DB + login bootstrap
docker-compose.yml  sqlserver, db-init, teams, games, ui
system.yaml         Machine-readable system description
.github/workflows/ci.yml
ADR.md              Architecture decisions (1–5 from A1; 6+ for A2)
AI_USAGE.md         AI usage log
```
