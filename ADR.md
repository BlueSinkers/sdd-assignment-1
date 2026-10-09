# Architecture Decision Records

## 1. Python + Flask as the backend framework
Date: 2026-10-09
Status: Decided
Context: The app is a small single-process web server for Madrid basketball captains: team accounts, court proposals, and challenges between teams, stored in SQLite. It has to run in one container and later be split into two services, and I have to be able to explain every line of it without notes.
Decision: Python 3.12 with Flask, using Python's built-in `sqlite3` module with plain SQL and Flask's Jinja templates for the pages.
Alternatives considered: Django, rejected because its ORM, admin, and auth system are far more than two small domains need, and its one-project structure works against splitting the domains later. FastAPI, rejected because the app serves HTML pages rather than a JSON API, so its main strengths (async, automatic API docs) would go unused. SQLAlchemy, rejected because plain SQL keeps the schema visible and leaves nothing hidden to explain.
Consequences: Very few dependencies, and each domain can become its own small Flask app in Assignment 2. The cost is writing SQL and input validation by hand, which an ORM or form library would otherwise handle.

## 2. Two domains, Teams and Games, that only talk through teams/api.py
Date: 2026-10-10
Status: Decided
Context: Assignment 2 splits this app into separate services, so the two feature areas need a clear boundary now. Games needs a few facts about teams (whether a team exists, its name, its format) to check a challenge, but should not depend on how Teams stores its data.
Decision: Each domain is its own folder with logic.py (plain Python rules), store.py (its own SQL, its own tables), and routes.py (a Flask Blueprint). Games never queries the teams table; it calls `teams.api.get_team_summary`, which returns a small dict of public fields with no password hash.
Alternatives considered: Letting Games join `challenges` to `teams` in SQL to get team names in one query, rejected because that ties Games to the teams table layout and breaks the moment the tables live in different databases. A single shared models.py for both domains, rejected because a change to one domain's data would ripple into the other.
Consequences: In Assignment 2, `get_team_summary` becomes an HTTP call to a Teams service and the Games code stays the same. The cost is an extra lookup per team when showing a list of challenges, instead of one SQL join.

## 3. Challenges store team ids with no foreign key to teams
Date: 2026-10-10
Status: Decided
Context: A challenge belongs to the Games domain but refers to two teams owned by the Teams domain. SQLite can only enforce a foreign key between tables in the same database file, and Assignment 2 will give each service its own database.
Decision: `challenges.challenger_team_id`, `challenges.opponent_team_id`, and `courts.proposed_by_team_id` are plain integers with no FOREIGN KEY. Games checks that a team exists through `teams.api` before saving. `challenges.court_id` does keep a real FOREIGN KEY to `courts`, because both tables are in the Games domain and will stay together.
Alternatives considered: A real foreign key from challenges to teams, rejected because it would fail as soon as the two domains are in separate databases, and would make it impossible to create the Games tables without the Teams tables. Copying team names into the challenges table, rejected because the copy would go stale if a team were ever renamed.
Consequences: The database can no longer stop a challenge from pointing at a team id that does not exist, so that check now lives in application code (`validate_challenge`). In exchange, the Games tables can move to their own database in Assignment 2 with no schema change.
