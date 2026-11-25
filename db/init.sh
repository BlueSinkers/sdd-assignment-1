#!/bin/bash
# Idempotent local SQL Server bootstrap. Passwords come from the environment only.
set -euo pipefail

SQLCMD="${SQLCMD:-/opt/mssql-tools18/bin/sqlcmd}"
HOST="${MSSQL_HOST:-sqlserver}"
SA_PASSWORD="${MSSQL_SA_PASSWORD:?MSSQL_SA_PASSWORD is required}"
TEAMS_PASSWORD="${TEAMS_DB_PASSWORD:?TEAMS_DB_PASSWORD is required}"
GAMES_PASSWORD="${GAMES_DB_PASSWORD:?GAMES_DB_PASSWORD is required}"

echo "Waiting for SQL Server at ${HOST}..."
for i in $(seq 1 60); do
  if "$SQLCMD" -S "$HOST" -U sa -P "$SA_PASSWORD" -C -Q "SELECT 1" &>/dev/null; then
    break
  fi
  sleep 2
done
"$SQLCMD" -S "$HOST" -U sa -P "$SA_PASSWORD" -C -Q "SELECT 1" >/dev/null
echo "SQL Server is up."

"$SQLCMD" -S "$HOST" -U sa -P "$SA_PASSWORD" -C -Q "
IF DB_ID(N'teams') IS NULL CREATE DATABASE teams;
IF DB_ID(N'games') IS NULL CREATE DATABASE games;
"

"$SQLCMD" -S "$HOST" -U sa -P "$SA_PASSWORD" -C -Q "
IF NOT EXISTS (SELECT 1 FROM sys.sql_logins WHERE name = N'teams_user')
  CREATE LOGIN teams_user WITH PASSWORD = N'${TEAMS_PASSWORD}';
IF NOT EXISTS (SELECT 1 FROM sys.sql_logins WHERE name = N'games_user')
  CREATE LOGIN games_user WITH PASSWORD = N'${GAMES_PASSWORD}';
"

"$SQLCMD" -S "$HOST" -U sa -P "$SA_PASSWORD" -C -d teams -Q "
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'teams_user')
  CREATE USER teams_user FOR LOGIN teams_user;
ALTER ROLE db_owner ADD MEMBER teams_user;
"

"$SQLCMD" -S "$HOST" -U sa -P "$SA_PASSWORD" -C -d games -Q "
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'games_user')
  CREATE USER games_user FOR LOGIN games_user;
ALTER ROLE db_owner ADD MEMBER games_user;
"

echo "Databases and logins ready."
