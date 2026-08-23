#!/usr/bin/env bash
# ==============================================================================
# Orchestrates Docker container builds and launches via Docker Compose
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Check if Docker is in PATH
if ! command -v docker &> /dev/null; then
    echo "Error: Docker executable not found. Please install Docker Engine / Docker Desktop." >&2
    exit 1
fi

cd "$PROJECT_ROOT"

if [ "$1" = "down" ] || [ "$1" = "--down" ]; then
    echo ">>> Stopping ERA BaseRow Manager Docker containers..."
    docker compose down
    exit 0
fi

echo "=== ERA BaseRow Manager Docker Orchestration ==="

# Check for .env file
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    if [ -f "$PROJECT_ROOT/.env.example" ]; then
        echo "No .env found. Creating .env from .env.example..."
        cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
    else
        echo "Warning: .env file not found. Containers will use default environment variables."
    fi
fi

# 1. Build and bring up containers
echo ">>> Running docker compose up --build -d..."
docker compose up --build -d

echo ""
echo "Docker containers started successfully!"
echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:5000"
echo "Use './scripts/Run-Docker.sh down' or 'docker compose down' to stop the containers."
