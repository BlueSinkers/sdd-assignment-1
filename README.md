# Madrid Hoops

Madrid Hoops helps basketball teams in Madrid find opponents and agree on games. Each team has one account, run by its captain. Captains add courts, challenge other teams to a game at a court and time, and the game is on once the other captain agrees to play.

## Features

**Teams**
- Register a team: name, password, captain, format (3v3 or 5v5), number of players, skill level, district.
- Captain log in / log out.
- Browse all teams. A Challenge button shows only next to teams that play your format.

**Games**
- Courts: captains add courts with an address, an optional name, and an optional Google Maps link.
- Challenges: pick a team, a court, and a date and time. The other captain can **agree to play** or **decline**, and the sender can **cancel** while it is still pending.
- Rules enforced:
  - 3v3 teams only play 3v3 teams, and 5v5 teams only play 5v5 teams.
  - A team can't challenge itself.
  - Games must be in the future.
  - No team or court can have two agreed games starting less than 2 hours apart.
- Dashboard for each captain: challenges received, challenges sent, upcoming games, played games, history.
- Turnout: after an agreed game has started, each captain records how many of their players came (0 up to their roster size). Recording again replaces the number.
- Stats page (`/stats`): games played, upcoming games, open challenges, acceptance rate, games by format, players attended, average players per game, turnout vs. roster size, busiest courts, and most active teams.
- Home page: upcoming agreed games across Madrid.

## Run it directly

Requires Python 3.12+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:8000. The database is created automatically on first start; no setup step is needed.

## Run it with Docker

```bash
docker build -t madrid-hoops .
docker run -p 8000:8000 -v madrid-hoops-data:/data madrid-hoops
```

Open http://localhost:8000. Data is kept in the `madrid-hoops-data` volume, so it survives the container being removed and recreated.

To use a different port:

```bash
docker run -e PORT=9000 -p 9000:9000 -v madrid-hoops-data:/data madrid-hoops
```

## Configuration

Everything is set with environment variables. None are required.

| Variable | Default | What it does |
|---|---|---|
| `PORT` | `8000` | Port the app listens on (always on `0.0.0.0`). |
| `DATA_DIR` | `./data` (`/data` in Docker) | Folder that holds the SQLite file. Created if missing. |
| `SECRET_KEY` | `dev-only-not-secret` | Signs the captain login cookie. Set a long random value for any real use. |

**SQLite file:** `$DATA_DIR/hoops.db`, so `./data/hoops.db` locally and `/data/hoops.db` in Docker.

Tables are created with `CREATE TABLE IF NOT EXISTS` on every start, so restarting never drops or duplicates data. The app ships no seed data: courts and teams are added by captains.

## Project structure

```
app.py              starts Flask, reads PORT / SECRET_KEY, registers both domains
db.py               SQLite connection and table creation
teams/              Teams domain
  logic.py            validation rules, password hashing (plain Python)
  store.py            SQL for the teams table
  routes.py           register, login, logout, team list
  api.py              the only functions other domains may call
games/              Games domain
  logic.py            court, challenge, and turnout rules, clash check, stats (plain Python)
  store.py            SQL for the courts, challenges, and attendance tables
  routes.py           courts, challenge form, accept/decline/cancel, turnout, dashboard, stats, home
templates/          HTML pages
tests/              pytest tests
Dockerfile          course template with the app's files filled in
ADR.md              architecture decision records
AI_USAGE.md         AI usage log
```

The two domains are separated so they can be split into separate services later. Games never reads the `teams` table; it asks `teams/api.py` for a team's public details. Challenges store team ids without a foreign key to `teams`, so the two domains can use separate databases. See ADR 2 and ADR 3.

## Tests and coverage

```bash
pytest --cov=app --cov=db --cov=teams --cov=games
```

Result:

```
Name                Stmts   Miss  Cover
---------------------------------------
app.py                 16      2    88%
db.py                  30      0   100%
games/__init__.py       0      0   100%
games/logic.py        106      0   100%
games/routes.py       138      0   100%
games/store.py         35      0   100%
teams/__init__.py       0      0   100%
teams/api.py            6      0   100%
teams/logic.py         42      0   100%
teams/routes.py        43      0   100%
teams/store.py         14      0   100%
---------------------------------------
TOTAL                 430      2    99%
81 passed
```

The two uncovered lines in `app.py` are the `if __name__ == "__main__":` block that starts the server.

## Container contract check

Output of `./container/run.sh .`:

```
=== SDD Assignment 1 contract check ===
Repository: /Users/BlueSyncers/Documents/Programs/school projects/sdd-assignment-1

==> Repository shape
  PASS  one Dockerfile, one manifest (requirements.txt)

==> Build from a clean context, no build args
  PASS  image built
  PASS  image size 53 MB

==> Start on PORT=8000 and reach it from the host
  PASS  HTTP 200 from http://localhost:8000/

==> SQLite file under DATA_DIR
  PASS  found in /data: hoops.db

==> Data persists, and a second boot does not re-seed
  PASS  volume at /data persists
  PASS  row counts unchanged across restart: attendance=0 challenges=0 courts=0 teams=0

==> PORT override is honoured (not hardcoded)
  PASS  HTTP 200 from http://localhost:9123/

=== ALL CHECKS PASSED ===
Paste this output into your README as the §7 evidence.
```
