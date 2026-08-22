# Architecture — AI Order Supervisor

## Overview

Each order gets its own background process (a Temporal workflow) that lives from creation to
completion. It does nothing until there's a real reason to act — no polling, no fixed check-in
loop.

## System Design

```mermaid
flowchart TD
    UI["Next.js UI<br/>(dashboard, event testing, controls)"] -->|"HTTP"| API["FastAPI backend<br/>(starts workflows, sends signals)"]
    API --> WF["Temporal workflow<br/>(one per order)"]
    WF --> ACT["Activities<br/>(LLM calls, database writes)"]
    API --> DB[("Postgres<br/>supervisors, runs, activity log")]
    ACT --> DB
```

- **Frontend (Next.js + Tailwind):** set up supervisors, start runs, send test events, add
  instructions, pause/resume/terminate a run, watch its timeline and memory update.
- **Backend (FastAPI):** thin layer between the frontend and everything else — starts workflows,
  passes events into them, sends run/timeline data back to the UI.
- **Temporal workflow:** one per order. Holds the run's state (memory, next wake-up time, paused
  or not) and decides *when* the agent should think. Never talks to the LLM or database directly.
- **The agent (Groq, in an activity called `run_agent_turn`):** reads recent history, asks the LLM
  what to do, gets back a decision — actions to take, an updated memory summary, how long to sleep.
- **Database (Postgres):** three tables — `supervisors`, `runs`, `activity_log`. Every event,
  sleep decision, action, instruction, and final summary is one row in `activity_log`.

## What Wakes the Workflow Up

Only three things:

1. **It just started** — the agent makes its first decision the moment a run is created.
2. **An event came in** — payment failed, shipment delayed, customer message, etc.
3. **A timer ran out** — the agent's own last "check back in X hours" decision came due.

## What Makes a Run End

Only three fixed rules — never the LLM's own opinion:

- the order was marked delivered
- someone terminated the run from the dashboard
- the run hit a max age (72 hours)

The agent can say "I think this is done," but that alone changes nothing. An ending that follows
fixed rules is easier to trust and explain than one left to a model's judgment.

## Deciding What's Worth Waking Up For

A quick rule check (`classify_event`) runs before the LLM ever gets involved:

- **Clearly urgent** (payment failed, shipment delayed, refund requested, customer message) →
  always wakes the agent.
- **Routine** (order created, payment confirmed, shipment created) → just logged, stays asleep —
  unless the supervisor is set to a more sensitive mode.
- **Unrecognized** → wakes the agent anyway, so nothing unusual slips through silently.

This keeps LLM calls low. The agent can also update its own "wake me up for this" list after each
turn, so the check gets smarter about that specific order over time.

## Memory, Not a Full Transcript

- One short memory summary per run, rewritten by the agent every time it acts.
- Each turn also gets the 15 most recent activity log entries and any manual instructions.
- Keeps enough context without sending the full run history to the LLM every time.

## The Business Actions

Five actions the agent can take: message fulfillment, message payments, message logistics,
message the customer, or leave an internal note. Each one just writes a row to the activity log —
nothing is actually sent to a real system. That's intentional for this project's scope.

## Deployment

```mermaid
flowchart TD
    V["Vercel<br/>(frontend)"] -->|"HTTPS"| R["Render<br/>(API + worker + Temporal server,<br/>one container)"]
    R --> N[("Neon<br/>managed Postgres")]
```

- **Frontend — Vercel.** `NEXT_PUBLIC_API_URL` points at the Render backend. Without it set
  correctly, nothing loads — the frontend has no backend of its own.
- **Backend — Render.** One free web service runs the Temporal server, the Temporal worker, and
  FastAPI together — Render's free tier only covers one service, so running them separately would
  cost extra. Needs `DATABASE_URL`, `GROQ_API_KEY`, and `FRONTEND_ORIGINS` set.
- **Database — Neon.** Chosen over Render's own free database, which gets deleted 30 days after
  creation. Neon's free tier doesn't expire.
- **No managed Temporal service:** Temporal Cloud starts at $100/month, so this project runs its
  own small Temporal server inside the free Render container instead.
- **The trade-off:** the Temporal server's state lives in a file inside the container. Render's
  free tier wipes that file on restart, so a sleeping run loses its live workflow when that
  happens (the run's history in the database is fine — only further actions on that run stop
  working). See [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) for details and what would fix it properly.

## What's Deliberately Left Out

This is a proof-of-concept, so a few things are left out on purpose:

- Real messaging or commerce integrations — actions just get logged, nothing is actually sent.
- User accounts, authentication, or multiple separate businesses.
- Trimming a run's history for extremely long-running orders (`continue_as_new` in Temporal
  terms) — the rolling memory summary already covers this project's scope.
- Analytics beyond the run list and filters already in the dashboard.
- A separate "pause" button — pause and interrupt do the same thing here, so they're one signal.

Listed here so it's clear these were left out on purpose, not missed.
