from __future__ import annotations

import os
from typing import Any

from temporalio.client import Client

from app.db import SessionLocal, Supervisor

# Worker and API share one container in every environment we deploy to, so
# this stays "localhost:7233" even in production. The env var exists so the
# value is never silently wrong, not because it needs to change here.
TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")


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
    client = await Client.connect(TEMPORAL_ADDRESS)
    workflow_handle = client.get_workflow_handle(run_id)
    await workflow_handle.signal(
        "order_event",
        args=[event_type, payload or {}],
    )


async def send_terminate_signal(run_id: str) -> None:
    client = await Client.connect(TEMPORAL_ADDRESS)
    workflow_handle = client.get_workflow_handle(run_id)
    await workflow_handle.signal("terminate")


async def send_interrupt_signal(run_id: str) -> None:
    client = await Client.connect(TEMPORAL_ADDRESS)
    workflow_handle = client.get_workflow_handle(run_id)
    await workflow_handle.signal("interrupt")


async def send_resume_signal(run_id: str) -> None:
    client = await Client.connect(TEMPORAL_ADDRESS)
    workflow_handle = client.get_workflow_handle(run_id)
    await workflow_handle.signal("resume")


async def send_add_instruction_signal(run_id: str, text: str) -> None:
    client = await Client.connect(TEMPORAL_ADDRESS)
    workflow_handle = client.get_workflow_handle(run_id)
    await workflow_handle.signal("add_instruction", args=[text])
