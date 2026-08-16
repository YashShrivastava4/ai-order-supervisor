from __future__ import annotations

import asyncio
from pathlib import Path

from dotenv import load_dotenv
from temporalio.client import Client
from temporalio.worker import Worker

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.activities import (
    classify_signal,
    create_internal_note,
    generate_final_output,
    log_incoming_event,
    message_customer,
    message_fulfillment_team,
    message_logistics_team,
    message_payments_team,
    record_manual_instruction,
    record_sleep_decision,
    run_agent_turn,
    sync_run_memory_and_guidance,
    sync_run_next_wakeup,
    update_run_completion,
    update_run_status,
)
from app.workflow import OrderSupervisorWorkflow


async def start_worker() -> None:
    print("Connecting to Temporal at localhost:7233...")
    client = await Client.connect("localhost:7233")
    worker = Worker(
        client,
        task_queue="order-supervisor-task-queue",
        workflows=[OrderSupervisorWorkflow],
        activities=[
            run_agent_turn,
            classify_signal,
            message_fulfillment_team,
            message_payments_team,
            message_logistics_team,
            message_customer,
            create_internal_note,
            log_incoming_event,
            record_manual_instruction,
            record_sleep_decision,
            sync_run_next_wakeup,
            sync_run_memory_and_guidance,
            generate_final_output,
            update_run_completion,
            update_run_status,
        ],
    )
    print("Worker started and polling task queue: order-supervisor-task-queue")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(start_worker())
