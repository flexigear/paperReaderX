#!/bin/bash
BIN_DIR="$(cd "$(dirname "$0")" && pwd)"
"$BIN_DIR/stop.sh" 2>/dev/null
sleep 1
"$BIN_DIR/start.sh"
