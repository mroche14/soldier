#!/bin/bash
# Run the MkDocs documentation server

cd "$(dirname "$0")" || exit 1

PORT=${1:-8001}

echo "Starting Soldier documentation server..."
echo "View at: http://127.0.0.1:$PORT"
echo ""

uv run python -m mkdocs serve -a "127.0.0.1:$PORT"
