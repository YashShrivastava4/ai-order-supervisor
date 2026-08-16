# Order Supervisor

An AI agent that babysits a single order from the moment it's placed until it's
resolved — without needing a human to poll it or a server to sit in a loop
"waiting." It wakes up when something happens, decides whether to act, and
goes back to sleep.

Built as a proof-of-concept take-home assignment.

---

## What this actually does

Imagine an order comes in. Normally you'd need either a human watching it, or
a script polling a database every few minutes forever. Neither is great —
humans get tired, and polling scripts waste resources checking things that
haven't changed.

Instead, this project starts one durable background process (a **Temporal
workflow**) per order. That process:

1. **Wakes up** when the order is created, when something relevant happens
   (payment confirmed, shipment delayed, customer message, etc.), or when a
   timer it set for itself fires.
2. **Decides what to do** by asking an LLM (via Groq) — should it message the
   customer, alert logistics, just make a note, or do nothing?
3. **Goes back to sleep**, either for a fixed number of hours or "until
   something happens," and tells the system exactly what would be worth
   waking it up early for.
4. Keeps a **memory summary** and a full **timeline** of everything it saw and
   did, so it's never starting from scratch when it wakes up.
5. Eventually **finishes** — because the order was delivered, someone
   terminated it from the UI, or it simply got too old — and writes a final
   report: what it did, what it learned, and what it'd recommend next time.

The trick to keeping this efficient: not every event deserves to wake the
full LLM. A cheap rule-based **classifier** looks at each incoming event
first. Routine, expected events get logged quietly. Only events that
actually matter wake the (more expensive) reasoning agent.

## Architecture

```
┌──────────────┐        HTTP         ┌──────────────┐      Temporal signals     ┌──────────────────────┐
│   Frontend   │ ──────────────────▶ │   Backend    │ ────────────────────────▶ │   Temporal Workflow   │
│ (Next.js UI) │ ◀────────────────── │  (FastAPI)   │ ◀──────────────────────── │  (one per order)      │
└──────────────┘      JSON           └──────┬───────┘                          └──────────┬────────────┘
                                             │                                             │
                                             ▼                                             ▼
                                      ┌─────────────┐                            ┌──────────────────┐
                                      │  PostgreSQL │ ◀───── activity log ────── │  Groq LLM calls   │
                                      │ (Docker)    │        & run state         │  (agent reasoning) │
                                      └─────────────┘                            └──────────────────┘
```

- **Frontend (Next.js)** — create supervisor configs, start runs, inject
  events, add live instructions, pause/resume/terminate, and watch the
  timeline and memory update in real time.
- **Backend (FastAPI)** — a thin HTTP layer that starts workflows, forwards
  events into them as Temporal signals, and reads/writes run state to
  Postgres.
- **Temporal workflow** — the actual "brain's schedule." It never runs a
  tight loop; it sleeps (via `workflow.wait_condition` with a timeout) until
  a signal arrives or its own wake-up timer fires, then hands off to an
  activity that calls the LLM.
- **Classifier** (`classify_signal`) — a fast, rule-based check that decides
  whether an incoming event is worth waking the full agent for, or can just
  be logged and left for the next scheduled wake-up.
- **Agent activities** (Groq, model `openai/gpt-oss-120b`) — reason about the
  order's current state and decide: which of the 5 business actions to take
  (if any), what to put in the memory summary, and how long to sleep for.
- **PostgreSQL** — stores supervisor configs, runs, and a single activity log
  table covering incoming events, sleep/wake decisions, agent actions,
  manual instructions, and final output.

The 5 business actions (`message_fulfillment_team`, `message_payments_team`,
`message_logistics_team`, `message_customer`, `create_internal_note`) don't
send anything externally — per the assignment scope, each one just writes an
activity record that shows up in the run's timeline.

## Screenshots

**Runs dashboard** — every run at a glance, with status and next wake-up time.
![Runs dashboard](screenshots/01-runs-dashboard.png)

**Run detail** — order context, live memory, activity timeline, and controls
to inject events or instructions.
![Run detail](screenshots/02-run-detail.png)

**Starting a new run** — pick a supervisor config, give it an order ID and
context.
![New run](screenshots/03-new-run.png)

**Supervisor configuration** — define name, base instruction, allowed
actions, and how aggressively it should wake up.
![Supervisor configuration](screenshots/04-supervisors.png)

**Temporal Web UI** — the actual workflow execution history: every signal,
activity, and timer, with real wall-clock durations between wake-ups.
![Temporal timeline](screenshots/05-temporal-timeline.png)

**Backend API docs** — auto-generated FastAPI/Swagger docs for every
endpoint.
![Backend API docs](screenshots/06-backend-api-docs.png)

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js (App Router) + Tailwind CSS |
| Backend | Python + FastAPI |
| Orchestration | Temporal (Python SDK, `temporalio`) |
| Database | PostgreSQL (via Docker) |
| LLM | Groq, model `openai/gpt-oss-120b` |

## Running it locally

You'll need **3 things running at once**: Postgres, a Temporal dev server,
and the backend worker + API — then the frontend on top. It sounds like a
lot, but each step is one command in its own terminal.

### 1. Get a Groq API key
Create `backend/.env` (this file is git-ignored, so your key never gets
committed):
```env
GROQ_API_KEY=your_groq_key_here
```

### 2. Start Postgres
From the project root:
```bash
docker compose up -d
```
This runs Postgres on port `5433` with a Docker-managed volume — nothing to
set up by hand.

### 3. Create the database tables
```bash
cd backend
python -m venv .venv

# Windows
.\.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
python -m scripts.init_db
```
This creates the `supervisors`, `runs`, and `activity_log` tables. Safe to
re-run — it won't drop existing data.

### 4. Start the Temporal dev server
In a **new terminal**:
```bash
temporal server start-dev --db-filename temporaldata
```
> This writes a local `temporaldata` file for Temporal's own state. It's
> git-ignored on purpose — it's a runtime artifact, not something to commit.

### 5. Start the backend worker and API
Back in the `backend` terminal from step 3 (venv still active):
```bash
python -m app.worker
```
Then, in **another new terminal**:
```bash
cd backend
source .venv/bin/activate   # or .\.venv\Scripts\activate on Windows
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
API docs will be at http://localhost:8000/docs

### 6. Start the frontend
In one more terminal, from the **project root**:
```bash
npm install
npm run dev
```
Open http://localhost:3000

By default the frontend talks to `http://localhost:8000`. If you ever run
the backend somewhere else, set `NEXT_PUBLIC_API_URL` (see `.env.example`).

## Deployment

The honest version: this app has **three moving backend pieces** — Postgres,
a Temporal server, and a Python worker that has to stay connected to
Temporal — plus the FastAPI process. Hosting all of that for free, reliably,
isn't realistic (Temporal in particular has no simple free-forever managed
option). So rather than fake a "live demo" that quietly breaks, here's what's
actually worth doing for free:

### Deploy the frontend to Vercel (free, ~10 minutes)

This gets you a real public URL for the UI/code, which is genuinely useful
for a portfolio link — with one important caveat below.

1. Push this repo to GitHub if it isn't already there.
2. Go to [vercel.com](https://vercel.com) and sign up/log in with GitHub.
3. Click **Add New → Project**, and import this repository.
4. Vercel auto-detects Next.js — leave the build settings as default.
5. Before deploying, add an environment variable:
   - **Key:** `NEXT_PUBLIC_API_URL`
   - **Value:** the public URL of your backend (see caveat below)
6. Click **Deploy**. You'll get a URL like `https://order-supervisor.vercel.app`.
7. Paste that URL into the placeholder at the top of this section.

**The caveat, stated plainly:** the frontend has no backend of its own — it's
just a UI that calls the FastAPI server. If `NEXT_PUBLIC_API_URL` points at
nothing reachable (e.g. you leave it as `localhost:8000`), every page will
load but every action (viewing runs, creating a run, etc.) will fail, because
it's trying to reach a server that only exists on your own machine. Two
honest ways to handle this:

- **For a portfolio link:** deploy the frontend as-is and say clearly in the
  UI/README that it's a code + design showcase, and that a live run needs the
  backend running locally. This is a completely normal thing to do for a POC.
- **For a live working demo (e.g. on a call):** run steps 2–5 from the local
  setup on your machine, expose port 8000 with a tunnel (e.g.
  `ngrok http 8000` or Cloudflare Tunnel), and set `NEXT_PUBLIC_API_URL` to
  that tunnel URL for the session. Also add the tunnel URL to
  `FRONTEND_ORIGINS` in `backend/.env` so CORS doesn't block it.

### If you want the backend reachable too (optional, still mostly free)

- **Postgres:** [Neon](https://neon.tech) has a genuinely free tier and
  you're already familiar with it.
- **FastAPI + worker:** [Render](https://render.com) free web services work,
  but sleep after inactivity and cold-start slowly — fine for a demo, not for
  something you want always-on.
- **Temporal:** this is the real blocker. Temporal Cloud doesn't have a
  permanent free tier, and self-hosting a Temporal server reliably on a free
  instance is more infrastructure than this POC calls for. Realistically,
  keep Temporal + the worker running locally and treat "always-on public
  backend" as out of scope for a free deployment — the assignment itself
  scopes this as a local POC, not a production platform.

**Live frontend:** _add your Vercel URL here once deployed_

## Project structure

```
.
├── src/                  # Next.js frontend (App Router)
│   ├── app/
│   │   ├── page.tsx          # Runs dashboard
│   │   ├── new-run/          # Start a new run
│   │   ├── runs/[run_id]/    # Run detail, timeline, controls
│   │   └── supervisors/      # Supervisor configuration
│   └── lib/
│       ├── api.ts            # Backend base URL (env-configurable)
│       └── format-time.ts
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI routes
│   │   ├── workflow.py       # Temporal workflow definition
│   │   ├── activities.py     # LLM calls, classifier, business actions
│   │   ├── temporal_client.py
│   │   └── worker.py         # Temporal worker process
│   └── scripts/
│       ├── init_db.py        # Creates DB tables
│       └── seed_demo.py
├── docker-compose.yml    # Postgres
└── screenshots/
```

## Current state

Working end-to-end: one Temporal workflow per order, signal-driven wake-ups,
scheduled wake-ups, the 5 business actions logged as activity records, a live
memory summary and timeline in the UI, run interrupt/resume/terminate, and a
generated final summary with learnings and feedback on completion.

Explicitly out of scope: real external messaging/commerce integrations,
authentication, multi-tenant hardening, and production-grade polish. This is
a POC focused on clean architecture and a reliable local demo, not a
shippable product.
