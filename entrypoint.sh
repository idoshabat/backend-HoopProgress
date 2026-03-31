#!/bin/sh
set -e

echo "⏳ Waiting for PostgreSQL..."

# wait until Postgres is ready
while ! nc -z db 5432; do
  sleep 1
done

echo "✅ PostgreSQL is up, running migrations..."

# run migrations
python manage.py migrate --noinput

# start Gunicorn
exec gunicorn backend.wsgi:application --bind 0.0.0.0:8000
