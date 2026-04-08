#!/bin/bash
# update.sh — Pull latest code from GitHub and redeploy
# Run this manually on the server, or it's called automatically by the deploy hook

set -e

cd ~/kyc-app

echo "[$(date)] Pulling latest code from GitHub..."
git pull origin main

echo "[$(date)] Rebuilding and restarting services..."
docker compose build
docker compose up -d

echo "[$(date)] Running any new database migrations..."
docker compose exec -T backend alembic upgrade head

echo "[$(date)] Update complete."
