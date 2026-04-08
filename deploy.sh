#!/bin/bash
# deploy.sh — Run this script on the server to deploy or update the KYC app
# Usage: bash deploy.sh

set -e

echo "=== KYC/KYB App Deployment ==="

# 1. Check that the external Traefik network exists
if ! docker network ls | grep -q "traefik_network"; then
  echo "Creating traefik_network..."
  docker network create traefik_network
fi

# 2. Check that .env files exist
if [ ! -f ".env" ]; then
  echo "ERROR: .env file not found. Copy .env.example to .env and fill in the values."
  exit 1
fi

if [ ! -f "backend/.env" ]; then
  echo "ERROR: backend/.env not found. Copy backend/.env.example to backend/.env and fill in the values."
  exit 1
fi

# 3. Pull/build images
echo "Building images..."
docker compose build

# 4. Start database first and wait for it to be healthy
echo "Starting database..."
docker compose up -d db
echo "Waiting for database to be ready..."
sleep 5

# 5. Run Alembic migrations
echo "Running database migrations..."
docker compose run --rm backend alembic upgrade head

# 6. Start all services
echo "Starting all services..."
docker compose up -d

echo ""
echo "=== Deployment complete ==="
echo "App available at: https://partnerdocs.tuio.com"
echo ""
echo "To create the first analyst account, run:"
echo "  docker compose exec backend python create_analyst.py analyst@tuio.com 'Full Name' 'password'"
echo ""
echo "To view logs:"
echo "  docker compose logs -f backend"
echo "  docker compose logs -f frontend"
