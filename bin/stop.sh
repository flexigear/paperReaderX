#!/bin/bash
WEB_DIR="$(cd "$(dirname "$0")/../web" && pwd)"
PID_FILE="$WEB_DIR/data/app.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "Not running (no PID file)"
    exit 1
fi

PID=$(cat "$PID_FILE")
if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    sleep 1
    if kill -0 "$PID" 2>/dev/null; then
        kill -9 "$PID"
    fi
    echo "Stopped (PID $PID)"
else
    echo "Process $PID not found (stale PID file)"
fi
rm -f "$PID_FILE"
