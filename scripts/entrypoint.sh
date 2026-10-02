#!/bin/sh
# Container start: migrate, seed and baseline on first start, then serve.
set -e
alembic upgrade head
ll seed --if-empty
ll drift baseline --if-empty
exec uvicorn launchledger.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
