#!/bin/bash
WEB_DIR="$(cd "$(dirname "$0")/../web" && pwd)"
PID_FILE="$WEB_DIR/data/app.pid"

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "Already running (PID $(cat "$PID_FILE"))"
    exit 1
fi

mkdir -p "$WEB_DIR/data"
cd "$WEB_DIR"
nohup .venv/bin/python app.py > data/app.log 2>&1 &
echo $! > "$PID_FILE"
echo "Started (PID $!), log: $WEB_DIR/data/app.log"
