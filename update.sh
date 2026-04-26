#!/bin/bash
# update.sh — Pull latest code from GitHub and redeploy
# Run this manually on the server, or it's called automatically by the deploy hook

set -e

cd ~/kyc-app

echo "[$(date)] Pulling latest code from GitHub..."
git pull origin main

echo "[$(date)] Rebuilding Docker images..."
docker compose build

echo "[$(date)] Applying database migrations..."
# Stop the backend only (keep DB running), run migrations, then start everything
docker compose stop backend
docker compose up -d db
docker compose run --rm -e PYTHONPATH=/app backend alembic upgrade head
docker compose up -d

echo "[$(date)] Update complete."
