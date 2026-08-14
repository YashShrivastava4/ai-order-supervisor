"""
S1 verification only — proves `temporal server start-dev` is reachable and a
worker can register + execute a trivial workflow end-to-end. Not part of the
real app; superseded by app/worker.py once S5 builds OrderSupervisorWorkflow.
Safe to delete once S1 is confirmed working.

Run:
    temporal server start-dev          # in one terminal, leave it running
    python scripts/smoke_test_temporal.py   # in another terminal

Expected: prints a workflow result and "S1 smoke test PASSED".
"""
import asyncio
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker

TASK_QUEUE = "smoke-test-task-queue"


@activity.defn
async def say_hello(name: str) -> str:
    return f"Hello, {name}! Temporal is wired up correctly."


@workflow.defn
class HelloWorkflow:
    @workflow.run
    async def run(self, name: str) -> str:
        return await workflow.execute_activity(
            say_hello,
            name,
            start_to_close_timeout=timedelta(seconds=10),
        )


async def main():
    print("Connecting to Temporal at localhost:7233 ...")
    client = await Client.connect("localhost:7233")
    print("Connected. Starting worker + running a test workflow ...")

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[HelloWorkflow],
        activities=[say_hello],
    )

    async with worker:
        result = await client.execute_workflow(
            HelloWorkflow.run,
            "Order Supervisor",
            id="smoke-test-workflow",
            task_queue=TASK_QUEUE,
        )
        print(f"Workflow result: {result}")

    print("S1 smoke test PASSED — Temporal server, worker, and SDK are all working.")


if __name__ == "__main__":
    asyncio.run(main())
