#!/bin/bash
set -e
MAIN_PORT=${PORT:-8000}
exec chainlit run app.py --host 0.0.0.0 --port "$MAIN_PORT" --headless
