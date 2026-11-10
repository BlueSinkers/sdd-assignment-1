# syntax=docker/dockerfile:1
# Games service: courts, challenges and attendance. Calls Teams over HTTP.
# Build from the repo root with:  docker build -t hoops-games services/games

FROM python:3.12-slim

# PYTHONUNBUFFERED: print log lines straight away instead of buffering them.
# DATA_DIR: where the SQLite file lives until the move to SQL Server.
# TEAMS_URL: where to find the Teams service ("teams" is its name on the
# Docker network); overridden on Azure. TEAMS_TIMEOUT_S: max wait per call.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    DATA_DIR=/data \
    TEAMS_URL=http://teams:8000 \
    TEAMS_TIMEOUT_S=2

WORKDIR /app

# Unprivileged user, and a folder it can write the database to.
RUN useradd --create-home --uid 10001 appuser \
 && mkdir -p /data \
 && chown -R appuser:appuser /data /app

# Dependencies before source, so editing code does not reinstall packages.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Only what the service needs to run: no tests, no .env, no COPY . .
COPY app.py db.py ./
COPY games/ ./games/

# Commit SHA, passed in by the pipeline (--build-arg GIT_SHA=...). Not a secret.
ARG GIT_SHA=dev
ENV VERSION=$GIT_SHA

USER appuser
EXPOSE 8000

CMD ["python", "app.py"]
