# syntax=docker/dockerfile:1
# Teams service: team accounts and captain login.
# Build from the repo root with:  docker build -t hoops-teams services/teams

FROM python:3.12-slim

# PYTHONUNBUFFERED: print log lines straight away instead of buffering them.
# DATA_DIR: where the SQLite file lives until the move to SQL Server.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    DATA_DIR=/data

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
COPY teams/ ./teams/

# Commit SHA, passed in by the pipeline (--build-arg GIT_SHA=...). Not a secret.
ARG GIT_SHA=dev
ENV VERSION=$GIT_SHA

USER appuser
EXPOSE 8000

CMD ["python", "app.py"]
