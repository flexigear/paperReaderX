#!/bin/bash
WEB_DIR="$(cd "$(dirname "$0")/../web" && pwd)"
PID_FILE="$WEB_DIR/data/app.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "Stopped"
    exit 1
fi

PID=$(cat "$PID_FILE")
if kill -0 "$PID" 2>/dev/null; then
    echo "Running (PID $PID)"
    echo "Port: 8899"
    echo "Log:  $WEB_DIR/data/app.log"
    exit 0
else
    echo "Stopped (stale PID file)"
    rm -f "$PID_FILE"
    exit 1
fi
