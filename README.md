# Order Supervisor

A POC for a long-running AI supervisor: one Temporal workflow per order, driven
by signals, with an LLM-powered agent that reasons, acts, sleeps, and wakes.

Full design decisions live in `01_MASTER_SPEC.md` (locked). Current status
lives in `02_PROGRESS.md` — read that first if you're picking this up mid-build.

**Status: S1 verified. S2 (SQLAlchemy models) built, awaiting verification —
see the S2 setup section below.** Nothing in `backend/app/` beyond S1+S2 is
implemented yet — see the TODO comment at the top of each remaining file for
which build step fills it in.

---

## Prerequisites

- **Docker** (Desktop or Engine) — for Postgres
- **Temporal CLI** — for the local dev server (`temporal server start-dev`)
- **Python 3.10+**
- Node.js 18+ and a free Groq API key (console.groq.com/keys, no credit card
  needed) are needed later (S4, S11) — not for S1. `USE_MOCK_LLM=true` also
  works with no key at all.

### Installing the Temporal CLI

```bash
# macOS or Linux
curl -sSf https://temporal.download/cli.sh | sh
# or, on macOS with Homebrew:
brew install temporal
```
Windows: download the binary from https://temporal.io/setup and add it to your PATH.

Verify: `temporal --version`

---

## S1 setup — repo scaffold, Postgres, Temporal connectivity

1. **Start Postgres**
   ```bash
   docker compose up -d
   docker compose ps   # postgres should show "healthy"
   ```

2. **Start the Temporal dev server** (separate terminal, leave it running)
   ```bash
   temporal server start-dev
   ```
   This serves the Temporal frontend on `localhost:7233` and a Web UI at
   http://localhost:8233. Data is in-memory — restarting the command wipes it,
   which is fine for a demo.

3. **Set up the Python backend**
   ```bash
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   cp .env.example .env
   ```

4. **Run the smoke test** (separate terminal, venv activated, from `backend/`)
   ```bash
   python scripts/smoke_test_temporal.py
   ```
   Expected output ends with:
   ```
   Workflow result: Hello, Order Supervisor! Temporal is wired up correctly.
   S1 smoke test PASSED — Temporal server, worker, and SDK are all working.
   ```
   You can also see the `smoke-test-workflow` execution in the Temporal Web UI
   at http://localhost:8233.

Once all of the above works, S1 is verified and we move to S2 (SQLAlchemy
models). More setup steps land here as each phase completes.

---

## S2 setup — SQLAlchemy models, tables, DB smoke test

1. **Postgres must be running** (from S1):
   ```bash
   docker compose up -d
   docker compose ps   # postgres should show "healthy"
   ```

2. **Run the DB smoke test** (from `backend/`, venv activated)
   ```bash
   python scripts/smoke_test_db.py
   ```
   This creates the 3 tables (`supervisor_configs`, `runs`, `activity_log`) if
   they don't exist yet, inserts one row into each to prove the foreign keys
   and JSONB columns work, prints what it inserted, then rolls the transaction
   back — nothing is left in the database, so it's safe to re-run.

   Expected output ends with:
   ```
   S2 smoke test PASSED — models, foreign keys, and JSONB columns all work.
   ```

3. **(Optional) look at the tables directly**, e.g. via `psql` or any Postgres
   GUI, to confirm the schema matches `01_MASTER_SPEC.md` §4:
   ```bash
   docker compose exec postgres psql -U postgres -d order_supervisor -c "\dt"
   docker compose exec postgres psql -U postgres -d order_supervisor -c "\d runs"
   ```

Once this passes, S2 is verified and we move to S3 (FastAPI skeleton +
supervisor endpoints).

---

## Running the full system

(Filled in as each phase lands — API server, worker process, and frontend dev
server all need to be running simultaneously; see `01_MASTER_SPEC.md` §3.)
