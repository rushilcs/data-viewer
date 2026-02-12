#!/usr/bin/env bash
# Single-command local boot: Postgres, migrations + demo data, then backend and frontend.
# Run from repo root. Backend runs in background; frontend runs in foreground (Ctrl+C to stop).
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
echo "Starting Postgres..."
docker-compose up -d
echo "Waiting for Postgres (max 15s)..."
for i in $(seq 1 15); do
  if docker-compose exec -T postgres pg_isready -U viewer -d viewer 2>/dev/null; then
    break
  fi
  sleep 1
done
# Prefer backend venv so deps are available
if [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
fi
if ! python -c "import alembic" 2>/dev/null; then
  echo "Backend deps not installed. From backend dir run: pip install -r requirements.txt"
  exit 1
fi
echo "Running migrations and demo data..."
python -m alembic upgrade head
python scripts/seed_dev.py
python scripts/generate_demo_data.py --seed 42 --items-per-dataset 50
echo "Starting backend on :8000..."
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
trap "kill $BACKEND_PID 2>/dev/null || true" EXIT
sleep 2
cd "$ROOT/frontend"
echo "Starting frontend on :3000..."
npm run dev
