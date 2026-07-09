#!/usr/bin/env bash
set -euo pipefail

host="${MSSQL_HOST:-mssql}"
database="${MSSQL_DB:-ai_receptionist}"

if [[ ! "$database" =~ ^[A-Za-z0-9_]+$ ]]; then
  echo "MSSQL_DB must contain only letters, numbers, and underscores" >&2
  exit 1
fi

for _ in $(seq 1 60); do
  if /opt/mssql-tools18/bin/sqlcmd -S "$host" -U sa -P "$MSSQL_SA_PASSWORD" -C -Q "SELECT 1" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

/opt/mssql-tools18/bin/sqlcmd \
  -S "$host" \
  -U sa \
  -P "$MSSQL_SA_PASSWORD" \
  -C \
  -b \
  -Q "IF DB_ID(N'${database}') IS NULL EXEC(N'CREATE DATABASE [${database}]')"
