"""Workflow-level tests for OrderSupervisorWorkflow, using Temporal's
time-skipping test environment (temporalio.testing.WorkflowEnvironment) with
mocked activities — no real Postgres or Groq call involved.

These need network access the first time they run, since the SDK downloads
a small local test server binary. If that download is blocked in your
environment, these tests will error out on the `WorkflowEnvironment.start_time_skipping()`
call rather than fail on assertions — that's an environment limitation, not
a workflow bug (see README "Running tests").
"""
from __future__ import annotations

import asyncio

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from app.workflow import OrderSupervisorWorkflow

SUPERVISOR = {
    "id": "sup-1",
    "name": "Test Supervisor",
    "base_instruction": "Watch the order.",
    "available_actions": ["message_customer", "create_internal_note"],
    "wakeup_guidance": [],
    "wakeup_aggressiveness": "normal",
}

DEFAULT_DECISION = {
    "reasoning": "mock",
    "actions": [],
    "memory_summary": "mock memory",
    "wakeup_guidance": [],
    "sleep": {"mode": "duration_hours", "value": 6},
    "recommend_completion": False,
}


class Recorder:
    """Shared state the mock activities below write into, so tests can
    assert on what happened and in what order / how much overlap there was."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.agent_turn_in_flight = 0
        self.agent_turn_max_in_flight = 0

    def reset(self) -> None:
        self.calls.clear()
        self.agent_turn_in_flight = 0
        self.agent_turn_max_in_flight = 0


recorder = Recorder()


# ---- Mock activities. Same names/signatures as app.activities, registered
# under those names so the workflow (which references them by name over the
# wire) runs completely unmodified against these instead of the real ones. ----


@activity.defn(name="classify_signal")
async def mock_classify_signal(event_type, wakeup_guidance=None, wakeup_aggressiveness=None):
    recorder.calls.append(("classify_signal", event_type))
    if event_type in {"shipment_delayed", "payment_failed"}:
        return "wake_now"
    return "log_and_wait"


@activity.defn(name="run_agent_turn")
async def mock_run_agent_turn(trigger_type, run_id, order_id, supervisor, event, order_context):
    recorder.agent_turn_in_flight += 1
    recorder.agent_turn_max_in_flight = max(
        recorder.agent_turn_max_in_flight, recorder.agent_turn_in_flight
    )
    recorder.calls.append(("run_agent_turn", trigger_type))
    # A small delay so two overlapping calls (if the bug were still present)
    # would actually overlap in wall-clock time instead of finishing instantly.
    await asyncio.sleep(0.05)
    recorder.agent_turn_in_flight -= 1
    return dict(DEFAULT_DECISION)


@activity.defn(name="log_incoming_event")
async def mock_log_incoming_event(run_id, event_type, payload, log_id):
    recorder.calls.append(("log_incoming_event", event_type))
    return {}


@activity.defn(name="sync_run_memory_and_guidance")
async def mock_sync_run_memory_and_guidance(run_id, memory_summary, wakeup_guidance):
    return {}


@activity.defn(name="sync_run_next_wakeup")
async def mock_sync_run_next_wakeup(run_id, next_wakeup_at):
    return {}


@activity.defn(name="record_sleep_decision")
async def mock_record_sleep_decision(run_id, reasoning, mode, next_wakeup_at, log_id):
    recorder.calls.append(("record_sleep_decision", mode))
    return {}


@activity.defn(name="message_fulfillment_team")
async def mock_message_fulfillment_team(run_id, details, log_id):
    return {}


@activity.defn(name="message_payments_team")
async def mock_message_payments_team(run_id, details, log_id):
    return {}


@activity.defn(name="message_logistics_team")
async def mock_message_logistics_team(run_id, details, log_id):
    return {}


@activity.defn(name="message_customer")
async def mock_message_customer(run_id, details, log_id):
    return {}


@activity.defn(name="create_internal_note")
async def mock_create_internal_note(run_id, details, log_id):
    recorder.calls.append(("create_internal_note", details))
    return {}


@activity.defn(name="record_manual_instruction")
async def mock_record_manual_instruction(run_id, text, log_id):
    # Deliberately slow, so tests can check the workflow waits for this to
    # finish before closing (see test_terminate_waits_for_inflight_handler).
    await asyncio.sleep(0.4)
    recorder.calls.append(("record_manual_instruction", text))
    return {}


@activity.defn(name="generate_final_output")
async def mock_generate_final_output(run_id, order_id, supervisor, reason):
    recorder.calls.append(("generate_final_output", reason))
    return {"summary": "done", "actions_taken": [], "key_learnings": [], "feedback": []}


@activity.defn(name="update_run_completion")
async def mock_update_run_completion(run_id, final_output, completion_status, log_id):
    recorder.calls.append(("update_run_completion", completion_status))
    return {}


@activity.defn(name="update_run_status")
async def mock_update_run_status(run_id, status):
    recorder.calls.append(("update_run_status", status))
    return {}


ALL_MOCK_ACTIVITIES = [
    mock_classify_signal,
    mock_run_agent_turn,
    mock_log_incoming_event,
    mock_sync_run_memory_and_guidance,
    mock_sync_run_next_wakeup,
    mock_record_sleep_decision,
    mock_message_fulfillment_team,
    mock_message_payments_team,
    mock_message_logistics_team,
    mock_message_customer,
    mock_create_internal_note,
    mock_record_manual_instruction,
    mock_generate_final_output,
    mock_update_run_completion,
    mock_update_run_status,
]


@pytest.fixture(scope="module")
async def env():
    async with await WorkflowEnvironment.start_time_skipping() as environment:
        yield environment


async def _start(env, run_id: str, task_queue: str):
    worker = Worker(
        env.client,
        task_queue=task_queue,
        workflows=[OrderSupervisorWorkflow],
        activities=ALL_MOCK_ACTIVITIES,
    )
    return worker


@pytest.mark.asyncio
async def test_concurrent_signals_never_run_two_agent_turns_at_once(env):
    """Two order_event signals arriving back-to-back must each get their own
    agent turn, processed one after another — never two in flight at the
    same time. This is the regression test for Fix 1 (the signal-handler
    race that used to let two agent turns run concurrently)."""
    recorder.reset()
    task_queue = "test-queue-concurrent-signals"
    worker = await _start(env, "run-1", task_queue)
    async with worker:
        handle = await env.client.start_workflow(
            OrderSupervisorWorkflow.run,
            args=["run-1", "order-1", SUPERVISOR, "context"],
            id="wf-concurrent-signals",
            task_queue=task_queue,
        )
        await asyncio.sleep(0.2)  # let the workflow_start turn finish
        recorder.reset()

        await handle.signal(OrderSupervisorWorkflow.order_event, args=["shipment_delayed", {}])
        await handle.signal(OrderSupervisorWorkflow.order_event, args=["shipment_delayed", {}])
        await asyncio.sleep(0.5)

        agent_turn_calls = [c for c in recorder.calls if c[0] == "run_agent_turn"]
        assert len(agent_turn_calls) == 2
        assert recorder.agent_turn_max_in_flight == 1

        await handle.terminate()


@pytest.mark.asyncio
async def test_terminate_waits_for_inflight_handler(env):
    """A terminate signal must not let the workflow close while another
    signal handler's activity (here, add_instruction's write) is still
    running. Regression test for Fix 3 (wait_condition(all_handlers_finished)
    before completion)."""
    recorder.reset()
    task_queue = "test-queue-terminate-waits"
    worker = await _start(env, "run-2", task_queue)
    async with worker:
        handle = await env.client.start_workflow(
            OrderSupervisorWorkflow.run,
            args=["run-2", "order-2", SUPERVISOR, "context"],
            id="wf-terminate-waits",
            task_queue=task_queue,
        )
        await asyncio.sleep(0.2)
        recorder.reset()

        await handle.signal(OrderSupervisorWorkflow.add_instruction, args=["Prioritize speed."])
        await handle.signal(OrderSupervisorWorkflow.terminate)

        await handle.result()

        names = [c[0] for c in recorder.calls]
        assert "record_manual_instruction" in names
        assert "update_run_completion" in names
        assert names.index("record_manual_instruction") < names.index(
            "update_run_completion"
        )


@pytest.mark.asyncio
async def test_scheduled_wakeup_fires_after_sleep_duration_not_before(env):
    """The agent asked to sleep 6 hours; the scheduled wake-up should not
    fire before that, and should fire once it's reached."""
    recorder.reset()
    task_queue = "test-queue-scheduled-wakeup"
    worker = await _start(env, "run-3", task_queue)
    async with worker:
        handle = await env.client.start_workflow(
            OrderSupervisorWorkflow.run,
            args=["run-3", "order-3", SUPERVISOR, "context"],
            id="wf-scheduled-wakeup",
            task_queue=task_queue,
        )
        await asyncio.sleep(0.2)
        recorder.reset()

        # Not enough simulated time for the 6-hour sleep to elapse yet.
        await env.sleep(60 * 60 * 3)  # 3 hours
        assert not any(c[0] == "run_agent_turn" for c in recorder.calls)

        # Now push past the 6-hour mark.
        await env.sleep(60 * 60 * 4)  # +4 hours = 7 hours total
        scheduled_wakeups = [
            c for c in recorder.calls if c == ("run_agent_turn", "scheduled_wakeup")
        ]
        assert len(scheduled_wakeups) == 1

        await handle.terminate()


@pytest.mark.asyncio
async def test_interrupt_stops_reactions_and_resume_restores_them(env):
    """While paused, an incoming event must not trigger an agent turn.
    After resume, the workflow should react to events again."""
    recorder.reset()
    task_queue = "test-queue-interrupt-resume"
    worker = await _start(env, "run-4", task_queue)
    async with worker:
        handle = await env.client.start_workflow(
            OrderSupervisorWorkflow.run,
            args=["run-4", "order-4", SUPERVISOR, "context"],
            id="wf-interrupt-resume",
            task_queue=task_queue,
        )
        await asyncio.sleep(0.2)
        recorder.reset()

        await handle.signal(OrderSupervisorWorkflow.interrupt)
        await asyncio.sleep(0.1)
        await handle.signal(OrderSupervisorWorkflow.order_event, args=["shipment_delayed", {}])
        await asyncio.sleep(0.3)

        assert not any(c[0] == "run_agent_turn" for c in recorder.calls)

        await handle.signal(OrderSupervisorWorkflow.resume)
        await asyncio.sleep(0.3)

        # The event that was queued while paused should now have been drained.
        assert any(c[0] == "run_agent_turn" for c in recorder.calls)

        await handle.terminate()
