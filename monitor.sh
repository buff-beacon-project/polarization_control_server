#!/usr/bin/env bash
set -euo pipefail

# Split into arrays
IFS=',' read -r -a NAMES <<< "$SERVICE_NAMES"
IFS=',' read -r -a URLS  <<< "$HEALTH_URLS"

# Ensure we have one URL per name
if (( ${#NAMES[@]} != ${#URLS[@]} )); then
  echo "ERROR: SERVICE_NAMES (${#NAMES[@]}) and HEALTH_URLS (${#URLS[@]}) counts differ" >&2
  exit 1
fi

LEN=${#NAMES[@]}
declare -a FAILS
for ((i=0; i<LEN; i++)); do
  FAILS[i]=0
done

INTERVAL=${INTERVAL:-10}
RETRIES=${RETRIES:-3}

while true; do
  for ((i=0; i<LEN; i++)); do
    name="${NAMES[i]}"
    url="${URLS[i]}"
    if curl --silent --fail "$url" >/dev/null; then
      FAILS[i]=0
    else
      FAILS[i]=$(( FAILS[i] + 1 ))
      echo "$(date) — $name heartbeat failed (${FAILS[i]}/${RETRIES})"
      if (( FAILS[i] >= RETRIES )); then
        echo "$(date) — restarting $name"
        docker-compose restart "$name"
        FAILS[i]=0
      fi
    fi
  done
  sleep "$INTERVAL"
done