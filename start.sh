#!/bin/bash
# start.sh - Boot Chainlit + health server in one process.
# Railway sets $PORT for the main service.

set -e

# Default ports
MAIN_PORT=${PORT:-8000}


# Start Chainlit on the main port
exec chainlit run app.py --host 0.0.0.0 --port "$MAIN_PORT" --headless
