# Architecture Decision Records

## 1. Python + Flask as the backend framework
Date: 2026-10-09
Status: Decided
Context: The app is a small single-process web server for Madrid basketball captains: team accounts, court proposals, and challenges between teams, stored in SQLite. It has to run in one container and later be split into two services, and I have to be able to explain every line of it without notes.
Decision: Python 3.12 with Flask, using Python's built-in `sqlite3` module with plain SQL and Flask's Jinja templates for the pages.
Alternatives considered: Django, rejected because its ORM, admin, and auth system are far more than two small domains need, and its one-project structure works against splitting the domains later. FastAPI, rejected because the app serves HTML pages rather than a JSON API, so its main strengths (async, automatic API docs) would go unused. SQLAlchemy, rejected because plain SQL keeps the schema visible and leaves nothing hidden to explain.
Consequences: Very few dependencies, and each domain can become its own small Flask app in Assignment 2. The cost is writing SQL and input validation by hand, which an ORM or form library would otherwise handle.
