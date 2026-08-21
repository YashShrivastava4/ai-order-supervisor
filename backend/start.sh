#!/bin/bash
set -e

echo "Starting Temporal dev server..."
# --headless: skip the Web UI, it isn't reachable outside the container on
# Render's free plan anyway (only one public port), and skipping it saves
# memory on a free-tier container running three processes at once.
# --db-filename: keep workflow state on disk for the container's lifetime,
# so a crash of just the temporal process (not the whole container) doesn't
# lose in-flight runs.
temporal server start-dev --headless --db-filename /tmp/temporal.db &

echo "Waiting for Temporal to accept connections..."
for i in $(seq 1 30); do
    if (exec 3<>/dev/tcp/127.0.0.1/7233) 2>/dev/null; then
        exec 3<&- 3>&-
        echo "Temporal is up."
        break
    fi
    sleep 1
done

echo "Starting Temporal worker..."
python -m app.worker &

echo "Starting FastAPI..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
