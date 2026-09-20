#!/bin/sh
set -e

# Apply database migrations on every start (idempotent), then hand off to CMD.
python manage.py migrate --noinput

exec "$@"
