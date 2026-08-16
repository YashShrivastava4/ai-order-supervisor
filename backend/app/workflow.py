from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from .activities import (
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

AGENT_TURN_RETRY_POLICY = RetryPolicy(maximum_attempts=3)


@workflow.defn
class OrderSupervisorWorkflow:
    def __init__(self):
        self._run_id: str | None = None
        self._order_id: str | None = None
        self._order_context: str | None = None
        self._supervisor: dict | None = None
        self._next_wakeup_at: object | None = None
        self._signal_received = False
        self._terminate_requested = False
        self._delivered_completion_requested = False
        self._paused = False
        self._max_age_deadline: object | None = None

    async def _sync_run_state(self, decision: dict | None):
        if self._run_id is None or not isinstance(decision, dict):
            return

        await workflow.execute_activity(
            sync_run_memory_and_guidance,
            args=[
                self._run_id,
                decision.get("memory_summary"),
                decision.get("wakeup_guidance"),
            ],
            start_to_close_timeout=timedelta(minutes=2),
        )

        if self._supervisor is not None:
            self._supervisor["wakeup_guidance"] = decision.get("wakeup_guidance") or []

    async def _dispatch_actions(self, decision: dict | None):
        if self._run_id is None or not isinstance(decision, dict):
            return

        actions = decision.get("actions")
        if not isinstance(actions, list):
            return

        action_type_map = {
            "message_fulfillment_team": message_fulfillment_team,
            "message_payments_team": message_payments_team,
            "message_logistics_team": message_logistics_team,
            "message_customer": message_customer,
            "create_internal_note": create_internal_note,
        }

        for action in actions:
            if not isinstance(action, dict):
                continue

            action_type = action.get("type")
            details = action.get("details", "")

            if action_type not in action_type_map:
                continue

            activity_fn = action_type_map[action_type]
            await workflow.execute_activity(
                activity_fn,
                args=[self._run_id, details],
                start_to_close_timeout=timedelta(minutes=2),
            )

    async def _apply_sleep_decision(self, decision: dict | None):
        sleep_decision = decision.get("sleep") if isinstance(decision, dict) else None
        reasoning = decision.get("reasoning") if isinstance(decision, dict) else None

        if not isinstance(sleep_decision, dict):
            self._next_wakeup_at = None
            mode = "none"
        elif sleep_decision.get("mode") == "duration_hours":
            try:
                hours = int(sleep_decision.get("value", 6))
            except (TypeError, ValueError):
                hours = 6
            self._next_wakeup_at = workflow.now() + timedelta(hours=max(hours, 0))
            mode = "duration_hours"
        else:
            self._next_wakeup_at = None
            mode = "until_next_event"

        if self._run_id is None:
            return

        next_wakeup_iso = (
            self._next_wakeup_at.isoformat()
            if self._next_wakeup_at is not None
            else None
        )
        await workflow.execute_activity(
            sync_run_next_wakeup,
            args=[self._run_id, next_wakeup_iso],
            start_to_close_timeout=timedelta(minutes=2),
        )
        # record what the agent decided and why, so it shows up on the run timeline
        await workflow.execute_activity(
            record_sleep_decision,
            args=[self._run_id, reasoning, mode, next_wakeup_iso],
            start_to_close_timeout=timedelta(minutes=2),
        )

    async def _wait_for_signal_or_timer(self):
        if self._next_wakeup_at is None and self._max_age_deadline is None:
            await workflow.wait_condition(lambda: self._signal_received)
            self._signal_received = False
            return "signal"

        timeouts = []
        if self._next_wakeup_at is not None:
            wakeup_timeout = self._next_wakeup_at - workflow.now()
            if wakeup_timeout > timedelta(0):
                timeouts.append(wakeup_timeout)

        if self._max_age_deadline is not None:
            age_timeout = self._max_age_deadline - workflow.now()
            if age_timeout > timedelta(0):
                timeouts.append(age_timeout)

        if not timeouts:
            self._next_wakeup_at = None
            return "timer"

        timeout = min(timeouts)

        try:
            await workflow.wait_condition(
                lambda: self._signal_received,
                timeout=timeout,
            )
        except TimeoutError:
            if (
                self._max_age_deadline is not None
                and workflow.now() >= self._max_age_deadline
            ):
                return "max_age"
            if (
                self._next_wakeup_at is not None
                and workflow.now() >= self._next_wakeup_at
            ):
                self._next_wakeup_at = None
            return "timer"

        if self._signal_received:
            self._signal_received = False
            return "signal"

        if (
            self._max_age_deadline is not None
            and workflow.now() >= self._max_age_deadline
        ):
            return "max_age"

        if self._next_wakeup_at is not None and workflow.now() >= self._next_wakeup_at:
            self._next_wakeup_at = None
            return "timer"

        return "timer"

    async def _handle_order_event(
        self, event_type: str, payload: dict | None = None
    ) -> bool:
        if self._run_id is None or self._order_id is None or self._supervisor is None:
            return False

        if event_type == "delivered":
            return True

        decision = await workflow.execute_activity(
            classify_signal,
            args=[
                event_type,
                self._supervisor.get("wakeup_guidance") or [],
                self._supervisor.get("wakeup_aggressiveness"),
            ],
            start_to_close_timeout=timedelta(minutes=2),
        )

        if decision == "wake_now":
            result = await workflow.execute_activity(
                run_agent_turn,
                args=[
                    "event",
                    self._run_id,
                    self._order_id,
                    self._supervisor,
                    {"type": event_type, "payload": payload or {}},
                    self._order_context,
                ],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=AGENT_TURN_RETRY_POLICY,
            )
            await self._dispatch_actions(result)
            await self._sync_run_state(result)
            await self._apply_sleep_decision(result)
        elif decision == "log_and_wait":
            await workflow.execute_activity(
                log_incoming_event,
                args=[self._run_id, event_type, payload or {}],
                start_to_close_timeout=timedelta(minutes=2),
            )
            await self._apply_sleep_decision({"sleep": {"mode": "until_next_event"}})

        return False

    async def _handle_completion(self, reason: str, completion_status: str) -> None:
        """Handle workflow completion: generate final output and update run."""
        if self._run_id is None or self._order_id is None or self._supervisor is None:
            return

        final_output = await workflow.execute_activity(
            generate_final_output,
            args=[
                self._run_id,
                self._order_id,
                self._supervisor,
                reason,
            ],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=AGENT_TURN_RETRY_POLICY,
        )

        await workflow.execute_activity(
            update_run_completion,
            args=[self._run_id, final_output, completion_status],
            start_to_close_timeout=timedelta(minutes=2),
        )

    @workflow.signal
    async def order_event(self, event_type: str, payload: dict | None = None):
        self._signal_received = True
        if self._paused:
            return

        completion_triggered = await self._handle_order_event(event_type, payload)
        if completion_triggered:
            self._delivered_completion_requested = True
            return

    @workflow.signal
    async def terminate(self) -> None:
        self._signal_received = True
        self._terminate_requested = True
        self._paused = False

    @workflow.signal
    async def interrupt(self) -> None:
        self._signal_received = True
        self._paused = True
        if self._run_id is not None:
            await workflow.execute_activity(
                update_run_status,
                args=[self._run_id, "paused"],
                start_to_close_timeout=timedelta(minutes=2),
            )

    @workflow.signal
    async def resume(self) -> None:
        self._signal_received = True
        self._paused = False
        if self._run_id is not None:
            await workflow.execute_activity(
                update_run_status,
                args=[self._run_id, "running"],
                start_to_close_timeout=timedelta(minutes=2),
            )

    @workflow.signal
    async def add_instruction(self, text: str) -> None:
        self._signal_received = True
        cleaned = str(text).strip()
        if not cleaned or self._run_id is None:
            return

        await workflow.execute_activity(
            record_manual_instruction,
            args=[self._run_id, cleaned],
            start_to_close_timeout=timedelta(minutes=2),
        )

    @workflow.run
    async def run(
        self,
        run_id: str,
        order_id: str,
        supervisor: dict,
        order_context: str | None = None,
    ):
        self._run_id = run_id
        self._order_id = order_id
        self._order_context = order_context
        self._supervisor = supervisor

        max_age_hours = 72
        self._max_age_deadline = workflow.now() + timedelta(hours=max_age_hours)

        initial_decision = await workflow.execute_activity(
            run_agent_turn,
            args=["workflow_start", run_id, order_id, supervisor, None, order_context],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=AGENT_TURN_RETRY_POLICY,
        )
        await self._dispatch_actions(initial_decision)
        await self._sync_run_state(initial_decision)
        await self._apply_sleep_decision(initial_decision)

        while True:
            if self._delivered_completion_requested:
                self._delivered_completion_requested = False
                await self._handle_completion("delivered event received", "completed")
                return

            if self._terminate_requested:
                await self._handle_completion("terminate signal received", "terminated")
                return

            if (
                self._max_age_deadline is not None
                and workflow.now() >= self._max_age_deadline
            ):
                await self._handle_completion("max workflow age reached", "completed")
                return

            if self._paused:
                await workflow.wait_condition(lambda: not self._paused)
                self._signal_received = False
                continue

            next_action = await self._wait_for_signal_or_timer()

            if self._delivered_completion_requested:
                self._delivered_completion_requested = False
                await self._handle_completion("delivered event received", "completed")
                return

            if self._terminate_requested:
                await self._handle_completion("terminate signal received", "terminated")
                return

            if (
                self._max_age_deadline is not None
                and workflow.now() >= self._max_age_deadline
            ):
                await self._handle_completion("max workflow age reached", "completed")
                return

            if next_action == "signal" and not self._signal_received:
                continue

            if next_action == "signal" and self._signal_received:
                continue

            if next_action == "max_age":
                await self._handle_completion("max workflow age reached", "completed")
                return

            if next_action == "timer":
                decision = await workflow.execute_activity(
                    run_agent_turn,
                    args=[
                        "scheduled_wakeup",
                        run_id,
                        order_id,
                        supervisor,
                        None,
                        self._order_context,
                    ],
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=AGENT_TURN_RETRY_POLICY,
                )
                await self._dispatch_actions(decision)
                await self._sync_run_state(decision)
                await self._apply_sleep_decision(decision)
