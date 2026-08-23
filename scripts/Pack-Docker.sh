#!/usr/bin/env bash
# ==============================================================================
# Packs Docker images for ERA BaseRow Manager (Backend & Frontend)
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TAG="${1:-latest}"
EXPORT_TAR="${2:-false}"

# Check Docker availability
if ! command -v docker &> /dev/null; then
    echo "Error: Docker executable not found. Please install Docker Engine / Docker Desktop." >&2
    exit 1
fi

echo "================================================="
echo "  ERA ERP / BaseRow Manager - Docker Packager   "
echo "================================================="
echo "Image Tag: $TAG"
echo "Project Root: $PROJECT_ROOT"

# 1. Build Backend Image
echo -e "\n>>> Building Backend Docker Image (era-backend:$TAG)..."
docker build -t "era-backend:$TAG" -f "$PROJECT_ROOT/backend/Dockerfile" "$PROJECT_ROOT/backend"
echo "[✓] Backend image built successfully."

# 2. Build Frontend Image
echo -e "\n>>> Building Frontend Docker Image (era-frontend:$TAG)..."
docker build -t "era-frontend:$TAG" -f "$PROJECT_ROOT/frontend/Dockerfile" "$PROJECT_ROOT/frontend"
echo "[✓] Frontend image built successfully."

# 3. Optional Tar Export
if [ "$EXPORT_TAR" = "true" ] || [ "$EXPORT_TAR" = "--export-tar" ]; then
    OUTPUT_DIR="$PROJECT_ROOT/dist-docker"
    mkdir -p "$OUTPUT_DIR"

    echo -e "\n>>> Exporting images to $OUTPUT_DIR..."
    docker save -o "$OUTPUT_DIR/era-backend-$TAG.tar" "era-backend:$TAG"
    docker save -o "$OUTPUT_DIR/era-frontend-$TAG.tar" "era-frontend:$TAG"

    echo "[✓] Saved Backend archive: $OUTPUT_DIR/era-backend-$TAG.tar"
    echo "[✓] Saved Frontend archive: $OUTPUT_DIR/era-frontend-$TAG.tar"
fi

echo -e "\n================================================="
echo " Docker packaging completed successfully!"
echo "================================================="
