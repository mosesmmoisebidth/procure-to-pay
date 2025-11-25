#!/usr/bin/env bash
set -euo pipefail

APP_URL=${APP_URL:-http://localhost:8000}
LOG_FILE="logs/p2p.log"

echo "===> Health check ($APP_URL/health/)"
curl -fsS "$APP_URL/health/" | jq || curl -fsS "$APP_URL/health/"

echo "\n===> Metrics sample ($APP_URL/metrics)"
curl -fsS "$APP_URL/metrics" | head -n 25 || true

echo "\n===> Tail logs ($LOG_FILE)"
if [[ -f "$LOG_FILE" ]]; then
  tail -n 60 "$LOG_FILE"
else
  echo "No log file yet at $LOG_FILE"
fi
