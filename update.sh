#!/bin/bash
# update.sh — Pull latest code from GitHub and redeploy
# Run this manually on the server, or it's called automatically by the deploy hook

set -e

cd ~/kyc-app

echo "[$(date)] Pulling latest code from GitHub..."
git pull origin main

echo "[$(date)] Rebuilding Docker images..."
docker compose build

echo "[$(date)] Running any new database migrations..."
# Start a one-off backend container just to run migrations, then shut it down.
# This guarantees the schema is up to date BEFORE the main services start,
# preventing the backend from booting against a stale database.
docker compose run --rm backend alembic upgrade head

echo "[$(date)] Starting all services..."
docker compose up -d

echo "[$(date)] Update complete."
