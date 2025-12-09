#!/usr/bin/env bash
# Run the Focal API server with proper environment variable export

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Export all variables from .env
if [[ -f .env ]]; then
    set -a
    source .env
    set +a
else
    echo "Warning: .env file not found"
fi

# Default values
HOST="${FOCAL_HOST:-0.0.0.0}"
PORT="${FOCAL_PORT:-8000}"
RELOAD=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --reload)
            RELOAD="--reload"
            shift
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--reload] [--port PORT] [--host HOST]"
            exit 1
            ;;
    esac
done

echo "Starting Focal API server on $HOST:$PORT"
exec uv run uvicorn focal.api.app:app --host "$HOST" --port "$PORT" $RELOAD
