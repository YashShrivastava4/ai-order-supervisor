# Architecture Note — Order Supervisor

## Overview

Order Supervisor is a proof-of-concept AI agent that supervises a single order from creation to completion. Each order gets its own long-running Temporal workflow, which stays alive for the lifetime of the order, waking up to think and act only when something warrants it — never running in a continuous loop.

## System Design

```
 Next.js UI  ───►  FastAPI backend  ───►  Temporal workflow (1 per order)
 (config,           (REST API,             │
  monitoring,        starts workflows,     ├─► Activities (LLM calls, DB writes)
  event injection)   sends signals)        │
                                            └─► Postgres (supervisors, runs, activity_log)
```

- **Frontend (Next.js + Tailwind):** configure supervisors, start runs, inject events, add instructions, control runs, and inspect timeline/memory/final output.
- **Backend (FastAPI):** thin REST layer over Postgres and the Temporal client — creates workflows, forwards signals, and serves run/timeline data to the UI.
- **Orchestration (Temporal Python SDK):** one `OrderSupervisorWorkflow` per order. The workflow holds run state (memory, wake-up guidance, pause state) and decides *when* to think; it never calls the LLM or the database directly.
- **Agent runtime (Groq, via Activities):** all reasoning happens inside an Activity, `run_agent_turn`, which reads recent context, calls the LLM, and returns a structured decision (actions, memory update, sleep instruction).
- **Persistence (Postgres):** three tables — `supervisors`, `runs`, `activity_log`. A single `activity_log` table (as the brief allows) stores incoming events, sleep decisions, agent actions, manual instructions, and final output, all differentiated by a `type` column.

## Workflow Lifecycle

The workflow supports the three required triggers for agent inference, all routed through the same `run_agent_turn` activity so there's one agent runtime rather than duplicated logic per trigger:

1. **Workflow start** — fires immediately when a run is created, seeded with the order context and the supervisor's base instruction.
2. **Incoming signal** (`order_event`) — an order event arrives from outside.
3. **Scheduled wake-up** — a timer set by the agent's previous sleep decision elapses.

A workflow ends only through explicit, workflow-owned rules — never because the LLM decides to stop:
- a terminal order event (`delivered`) arrives,
- the run is manually terminated from the UI,
- or a max workflow age (72 hours) is reached.

The agent can *recommend* completion in its response, but that recommendation is not currently wired to end the workflow — only the three rules above can. This was a deliberate choice to keep completion deterministic and auditable, per the brief's explicit requirement that the AI not be the sole authority on when a run ends.

## Wake/Sleep Decision Flow

Every incoming event first passes through a lightweight, deterministic classifier (`classify_event`) before it ever reaches the LLM:

- Known urgent events (`payment_failed`, `shipment_delayed`, `refund_requested`, `customer_message_received`) or anything on the run's own agent-generated **wake-up guidance** list → wake the agent now.
- Known routine events (`order_created`, `payment_confirmed`, `shipment_created`, `no_update_for_n_hours`) → logged only, workflow stays asleep, unless the supervisor is configured with `high` wake-up aggressiveness.
- Any **unrecognized** event type defaults to waking the agent — a fail-safe so unknown signals are never silently dropped.

This keeps routine noise from costing an LLM call, while giving the agent a way to refine its own sensitivity over time: after each turn, the agent can update the wake-up guidance list, effectively teaching the classifier what matters for that specific order going forward.

## Memory and Context Compaction

Each run keeps a single rolling **memory summary** (plain text, rewritten by the agent every turn) instead of a full transcript. Each agent turn also receives the 15 most recent `activity_log` entries and any run-specific manual instructions as additional context. This bounds the size of what's sent to the LLM regardless of how long a run has been active, at the cost of not implementing `continue_as_new` for very long-running workflow histories — an acceptable simplification for a POC of this scope, and one of the brief's own listed "good-to-have, not mandatory" items.

## Business Actions

The five required actions (`message_fulfillment_team`, `message_payments_team`, `message_logistics_team`, `message_customer`, `create_internal_note`) don't send anything externally, as scoped. Each is its own Temporal Activity that writes one row to `activity_log`, which the UI renders in the run's timeline — satisfying the requirement without a separate messages table.

## Known Simplifications

In line with the brief's scope boundaries, the following were intentionally left out:
- Real commerce/messaging integrations, authentication, multi-tenant hardening.
- `continue_as_new` for very long histories.
- A more advanced memory-compaction strategy beyond the rolling summary described above.
- Richer run analytics beyond the list/filter view.
- A separate literal "pause" control — Interrupt and Pause were merged into a single signal, since they're functionally identical here (both stop the agent from acting until Resume is sent).

None of these affect the required acceptance criteria; they're flagged here for transparency rather than left unaddressed.
