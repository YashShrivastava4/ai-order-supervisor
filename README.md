# Order Supervisor

A proof-of-concept AI order supervisor built to match the assignment requirements in the build guide.

## Stack
- Next.js App Router
- Tailwind CSS
- Python + FastAPI
- Temporal Python SDK
- PostgreSQL via Docker
- Groq with model `openai/gpt-oss-120b`

## Local setup

Run these steps in order from a fresh clone.

### 1) Backend environment file
Create a local file at `backend/.env` with:

```env
GROQ_API_KEY=YOUR_GROQ_KEY_HERE
```

This file is intentionally ignored by Git. The project loads it at startup with `python-dotenv`.

### 2) Postgres
From the project root:
```bash
docker compose up -d
```
This starts Postgres on port **5433** (mapped from the container's 5432), using a Docker-managed volume — no manual volume setup needed.

### 3) Create the database tables
```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m scripts.init_db
```
This creates the `supervisors`, `runs`, and `activity_log` tables. Run it once; it's safe to re-run (it won't drop existing tables).

### 4) Temporal dev server
In a new terminal:
```bash
temporal server start-dev --db-filename temporaldata
```

### 5) Backend worker and API
Back in the `backend` terminal from step 3 (venv already active):
```bash
python -m app.worker
```

Then, in another new terminal:
```bash
cd backend
.\.venv\Scripts\activate
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 6) Frontend
In another new terminal, from the **project root** (this is where `package.json` lives):
```bash
npm install
npm run dev
```
Open http://localhost:3000

## Current project state
The project is verified through the implemented Phase 5 and Phase 6 behavior, and includes the basic Phase 7 memory/wakeup-guidance state plumbing. This is a working prototype focused on clean architecture and reliable local demo execution rather than production hardening.

## Notes
- The workflow remains deterministic and does not call Groq/Postgres directly.
- The Groq API key is kept out of source control via the local `.env` file.
- The worker and workflow modules import cleanly.
