from __future__ import annotations

import os
from typing import Any

from temporalio.client import Client, WorkflowHandle
from temporalio.service import RPCError, RPCStatusCode

from app.db import SessionLocal, Supervisor

# Worker and API share one container in every environment we deploy to, so
# this stays "localhost:7233" even in production. The env var exists so the
# value is never silently wrong, not because it needs to change here.
TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")


class WorkflowNotFoundError(Exception):
    """A signal targeted a run whose Temporal workflow no longer exists on
    the server.

    On this deployment (Temporal dev server, local sqlite persistence,
    inside the same container as the API), the most common cause is the
    Render free-tier container spinning down on idle and later restarting
    into a fresh, empty filesystem — the run's history in Neon is untouched,
    but the in-progress Temporal execution itself is gone. See notes.md for
    the full investigation and the options for actually eliminating this
    (upgrading off the free tier, or moving Temporal's persistence off local
    disk) versus the graceful-degradation path implemented here.
    """

    def __init__(self, run_id: str):
        self.run_id = run_id
        super().__init__(f"no live workflow found for run {run_id!r}")


def _is_not_found(exc: RPCError) -> bool:
    return exc.status == RPCStatusCode.NOT_FOUND


async def _signal(run_id: str, signal_name: str, args: list[Any] | None = None) -> None:
    """Send a signal to run_id's workflow, translating a not-found RPCError
    into WorkflowNotFoundError so callers can handle that case distinctly
    from other failures (network issues, bad payloads, etc.)."""
    client = await Client.connect(TEMPORAL_ADDRESS)
    handle: WorkflowHandle = client.get_workflow_handle(run_id)
    try:
        if args:
            await handle.signal(signal_name, args=args)
        else:
            await handle.signal(signal_name)
    except RPCError as exc:
        if _is_not_found(exc):
            raise WorkflowNotFoundError(run_id) from exc
        raise


async def start_run(
    order_id: str,
    supervisor_id: str,
    run_id: str | None = None,
    order_context: str | None = None,
) -> str:
    db = SessionLocal()
    try:
        supervisor = db.get(Supervisor, supervisor_id)
        if supervisor is None:
            raise ValueError(f"Supervisor {supervisor_id} not found")

        supervisor_payload = {
            "id": supervisor.id,
            "name": supervisor.name,
            "base_instruction": supervisor.base_instruction,
            "available_actions": supervisor.available_actions,
            "default_wakeup_behavior": supervisor.default_wakeup_behavior,
            "model_config": supervisor.model_config,
            "wakeup_aggressiveness": supervisor.wakeup_aggressiveness,
        }
    finally:
        db.close()

    client = await Client.connect(TEMPORAL_ADDRESS)
    workflow_id = run_id or f"run-{order_id}"
    await client.start_workflow(
        "OrderSupervisorWorkflow",
        args=[workflow_id, order_id, supervisor_payload, order_context],
        id=workflow_id,
        task_queue="order-supervisor-task-queue",
    )
    return workflow_id


async def send_order_event_signal(
    run_id: str, event_type: str, payload: dict[str, Any] | None = None
) -> None:
    await _signal(run_id, "order_event", args=[event_type, payload or {}])


async def send_terminate_signal(run_id: str) -> None:
    await _signal(run_id, "terminate")


async def send_interrupt_signal(run_id: str) -> None:
    await _signal(run_id, "interrupt")


async def send_resume_signal(run_id: str) -> None:
    await _signal(run_id, "resume")


async def send_add_instruction_signal(run_id: str, text: str) -> None:
    await _signal(run_id, "add_instruction", args=[text])
