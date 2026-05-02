#!/usr/bin/env bash
set -euo pipefail

# Optional: change to project root if script run from elsewhere
# cd "$(dirname "$0")"

# Optional: activate your virtualenv (edit the path to your venv activate script)
# source /home/you/path/to/venv/bin/activate

# Ensure logs dir exists
LOGDIR="./logs/celery"
mkdir -p "$LOGDIR"

# Helper function to start a worker
start_worker() {
  local queue=$1
  local name=$2
  local logfile="$LOGDIR/${name}.log"
  local pidfile="$LOGDIR/${name}.pid"

  echo "Starting worker: queue=${queue}, name=${name}"
  nohup celery -A price_comparison worker -l info -Q "${queue}" -n "${name}@%h" \
    >> "${logfile}" 2>&1 &

  echo $! > "${pidfile}"
  echo " -> pid $(cat ${pidfile}), log ${logfile}"
}

# Start workers (edit concurrency or other flags if needed)
start_worker "ryans_queue" "ryans"
start_worker "ucc_bd_queue" "ucc_bd"
start_worker "startech_queue" "startech"
start_worker "techland_queue" "techland"

echo "All workers started. PIDs are in ${LOGDIR}/*.pid"