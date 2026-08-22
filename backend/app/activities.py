from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from groq import Groq
from temporalio import activity

from app.db import ActivityLog, Run, SessionLocal


# Turns a timestamp into a UTC string like "2026-08-16T05:43:00Z" for the API
def _format_utc_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)

    return value.isoformat().replace("+00:00", "Z")


# Grabs the most recent activity log rows for a run, oldest first, so the
# agent has recent history to reason about
def _recent_activity_context(run_id: str, limit: int = 15) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        rows = (
            db.query(ActivityLog)
            .filter(ActivityLog.run_id == run_id)
            .order_by(ActivityLog.created_at.desc())
            .limit(limit)
            .all()
        )
    finally:
        db.close()

    ordered = list(reversed(rows))
    return [
        {
            "type": row.type,
            "payload": row.payload,
            "created_at": _format_utc_datetime(row.created_at),
        }
        for row in ordered
    ]


# Collects any manual instructions a person has added to this run so far
def _run_specific_instructions(run_id: str) -> list[str]:
    db = SessionLocal()
    try:
        rows = (
            db.query(ActivityLog)
            .filter(ActivityLog.run_id == run_id)
            .filter(ActivityLog.type == "manual_instruction")
            .order_by(ActivityLog.created_at.asc())
            .all()
        )
    finally:
        db.close()

    instructions: list[str] = []
    for row in rows:
        payload = row.payload or {}
        text = payload.get("text") if isinstance(payload, dict) else None
        if isinstance(text, str) and text.strip():
            instructions.append(text.strip())
    return instructions


# Events that should always wake the agent up right away
URGENT_EVENTS = {
    "payment_failed",
    "shipment_delayed",
    "refund_requested",
    "customer_message_received",
}

# Routine events that can just be logged, unless the supervisor wants to
# wake up for everything or the agent specifically asked to be told about them
NONURGENT_EVENTS = {
    "order_created",
    "payment_confirmed",
    "shipment_created",
    "no_update_for_n_hours",
}


# Decides whether an event should wake the agent now or just be logged for later
def classify_event(
    event_type: str,
    wakeup_guidance: list[str] | None = None,
    wakeup_aggressiveness: str | None = None,
) -> str:
    if wakeup_guidance and event_type in wakeup_guidance:
        return "wake_now"
    if event_type in URGENT_EVENTS:
        return "wake_now"
    if event_type in NONURGENT_EVENTS:
        # a supervisor configured as "high" aggressiveness wants to wake even for routine events
        if wakeup_aggressiveness == "high":
            return "wake_now"
        return "log_and_wait"
    return "wake_now"


# Used unless a supervisor has its own model configured
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"


# Picks which Groq model to use for this supervisor
def _resolve_model(supervisor: dict) -> str:
    configured = supervisor.get("model_config")
    if isinstance(configured, str) and configured.strip():
        return configured.strip()
    return DEFAULT_GROQ_MODEL


# Shared helper: saves one business action (like messaging a team) to the activity log
def _write_activity_log_row(run_id: str, action: str, details: str) -> dict[str, str]:
    payload = {"action": str(action), "details": str(details)}
    db = SessionLocal()
    try:
        row = ActivityLog(
            id=str(uuid.uuid4()),
            run_id=str(run_id),
            type="agent_action",
            payload=payload,
            created_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return payload
    finally:
        db.close()


# The 5 business actions the agent can take. Each just writes a row to the
# activity log — nothing is actually sent to a real team or customer.
@activity.defn
async def message_fulfillment_team(run_id: str, details: str) -> dict[str, str]:
    return _write_activity_log_row(run_id, "message_fulfillment_team", details)


@activity.defn
async def message_payments_team(run_id: str, details: str) -> dict[str, str]:
    return _write_activity_log_row(run_id, "message_payments_team", details)


@activity.defn
async def message_logistics_team(run_id: str, details: str) -> dict[str, str]:
    return _write_activity_log_row(run_id, "message_logistics_team", details)


@activity.defn
async def message_customer(run_id: str, details: str) -> dict[str, str]:
    return _write_activity_log_row(run_id, "message_customer", details)


@activity.defn
async def create_internal_note(run_id: str, details: str) -> dict[str, str]:
    return _write_activity_log_row(run_id, "create_internal_note", details)


# Saves a routine event to the activity log without waking the agent up
@activity.defn
async def log_incoming_event(
    run_id: str, event_type: str, payload: dict | None = None
) -> dict[str, Any]:
    db = SessionLocal()
    try:
        row = ActivityLog(
            id=str(uuid.uuid4()),
            run_id=str(run_id),
            type="incoming_event",
            payload={"event_type": str(event_type), "payload": payload or {}},
            created_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.payload
    finally:
        db.close()


# Saves a person's manual instruction to the activity log so the agent sees it next turn
@activity.defn
async def record_manual_instruction(run_id: str, text: str) -> dict[str, str]:
    cleaned = str(text).strip()
    if not cleaned:
        return {"text": ""}

    db = SessionLocal()
    try:
        row = ActivityLog(
            id=str(uuid.uuid4()),
            run_id=str(run_id),
            type="manual_instruction",
            payload={"text": cleaned},
            created_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.payload
    finally:
        db.close()


@activity.defn
async def record_sleep_decision(
    run_id: str,
    reasoning: str | None,
    mode: str,
    next_wakeup_at: str | None,
) -> dict[str, str]:
    """Log why the agent went back to sleep, and for how long."""
    payload = {
        "reasoning": reasoning or "No reasoning provided.",
        "mode": mode,
        "next_wakeup_at": next_wakeup_at or "no timer",
    }
    db = SessionLocal()
    try:
        row = ActivityLog(
            id=str(uuid.uuid4()),
            run_id=str(run_id),
            type="sleep_decision",
            payload=payload,
            created_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.payload
    finally:
        db.close()


# Saves the run's next wake-up time to the database (or clears it if there isn't one)
@activity.defn
async def sync_run_next_wakeup(
    run_id: str, next_wakeup_at: str | None
) -> dict[str, Any] | None:
    parsed_next_wakeup_at = (
        datetime.fromisoformat(next_wakeup_at) if next_wakeup_at is not None else None
    )

    db = SessionLocal()
    try:
        row = db.get(Run, run_id)
        if row is None:
            return None

        row.next_wakeup_at = parsed_next_wakeup_at
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
        return {
            "run_id": row.id,
            "next_wakeup_at": _format_utc_datetime(row.next_wakeup_at),
        }
    finally:
        db.close()


# Saves the agent's updated memory summary and wake-up guidance to the database
@activity.defn
async def sync_run_memory_and_guidance(
    run_id: str,
    memory_summary: str | None,
    wakeup_guidance: list[str] | None,
) -> dict[str, Any] | None:
    db = SessionLocal()
    try:
        row = db.get(Run, run_id)
        if row is None:
            return None

        if memory_summary is not None:
            row.memory_summary = str(memory_summary)
        if wakeup_guidance is not None:
            row.wakeup_guidance = list(wakeup_guidance)
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
        return {
            "run_id": row.id,
            "memory_summary": row.memory_summary,
            "wakeup_guidance": row.wakeup_guidance,
        }
    finally:
        db.close()


# The main agent call: asks Groq what to do next given the run's history,
# then returns a normalized decision (actions, memory, sleep, etc.)
@activity.defn
async def run_agent_turn(
    trigger_type: str,
    run_id: str,
    order_id: str,
    supervisor: dict,
    event: dict | None = None,
    order_context: str | None = None,
) -> dict:
    # Pull together everything the agent needs to know about this run so far
    db = SessionLocal()
    try:
        run_row = db.get(Run, run_id)
        current_memory = (
            run_row.memory_summary
            if run_row and run_row.memory_summary
            else "No prior memory."
        )
        recent_activity_log = _recent_activity_context(run_id)
        run_specific_instructions = _run_specific_instructions(run_id)
    finally:
        db.close()

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set")

    client = Groq(api_key=api_key)

    base_instruction = supervisor.get("base_instruction", "")
    available_actions = supervisor.get("available_actions", [])
    event_payload = event or {}

    context_instruction_block = ""
    if run_specific_instructions:
        context_instruction_block = (
            "\nAdditional run-specific instructions for this run:\n- "
            + "\n- ".join(run_specific_instructions)
            + "\n"
        )

    # Tell the model exactly what JSON shape to respond with
    system_prompt = (
        f"{base_instruction}\n\n"
        "You are an order supervisor. "
        "Return valid JSON only, with this exact shape:\n"
        "{\n"
        '  "reasoning": "short explanation",\n'
        '  "actions": [{"type": "message_customer", "details": "..."}],\n'
        '  "memory_summary": "updated compact summary text",\n'
        '  "wakeup_guidance": ["shipment_delayed", "refund_requested"],\n'
        '  "sleep": {"mode": "duration_hours", "value": 6},\n'
        '  "recommend_completion": false\n'
        "}\n\n"
        "Available actions: "
        + (", ".join(available_actions) if available_actions else "none")
        + context_instruction_block
    )

    user_context = {
        "trigger_type": trigger_type,
        "run_id": run_id,
        "order_id": order_id,
        "order_context": order_context,
        "current_memory": current_memory,
        "recent_activity_log": recent_activity_log,
        "run_specific_instructions": run_specific_instructions,
        "event": event_payload,
        "available_actions": available_actions,
    }

    # Ask Groq for a decision
    try:
        response = client.chat.completions.create(
            model=_resolve_model(supervisor),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_context, default=str)},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
    except Exception as exc:
        raise RuntimeError(f"Groq API call failed for run {run_id}: {exc}") from exc

    raw_response = response.choices[0].message.content
    if not raw_response:
        raise RuntimeError(f"Groq returned an empty response for run {run_id}")

    try:
        decision = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Groq returned invalid JSON for run {run_id}: {exc}"
        ) from exc

    if not isinstance(decision, dict):
        raise RuntimeError(f"Groq returned a non-object payload for run {run_id}")

    # Don't trust the model's JSON blindly — clean it up into a shape the
    # rest of the app can rely on, falling back to safe defaults where needed
    actions = decision.get("actions") or []
    normalized_actions = []
    if isinstance(actions, list):
        for item in actions:
            if isinstance(item, dict):
                action_type = item.get("type")
                details = item.get("details")
                if action_type is not None and details is not None:
                    normalized_actions.append(
                        {"type": str(action_type), "details": str(details)}
                    )

    wakeup_guidance = decision.get("wakeup_guidance") or []
    normalized_guidance = []
    if isinstance(wakeup_guidance, list):
        normalized_guidance = [str(item) for item in wakeup_guidance]

    sleep_value = decision.get("sleep") or {"mode": "duration_hours", "value": 6}
    if isinstance(sleep_value, dict):
        sleep_mode = sleep_value.get("mode")
        if sleep_mode not in {"duration_hours", "until_next_event"}:
            sleep_mode = "duration_hours"
        if sleep_mode == "duration_hours":
            try:
                sleep_duration = int(sleep_value.get("value", 6))
            except (TypeError, ValueError):
                sleep_duration = 6
            normalized_sleep = {"mode": "duration_hours", "value": sleep_duration}
        else:
            normalized_sleep = {"mode": "until_next_event"}
    else:
        normalized_sleep = {"mode": "duration_hours", "value": 6}

    normalized = {
        "reasoning": str(
            decision.get("reasoning")
            or "Monitoring order health and making a decision."
        ),
        "actions": normalized_actions,
        "memory_summary": str(decision.get("memory_summary") or current_memory),
        "wakeup_guidance": normalized_guidance,
        "sleep": normalized_sleep,
        "recommend_completion": bool(decision.get("recommend_completion", False)),
    }

    return normalized


# Thin wrapper so the workflow can call classify_event as a Temporal activity
@activity.defn
async def classify_signal(
    event_type: str,
    wakeup_guidance: list[str] | None = None,
    wakeup_aggressiveness: str | None = None,
) -> str:
    return classify_event(event_type, wakeup_guidance, wakeup_aggressiveness)


# Asks Groq to write a final summary once the run is ending
@activity.defn
async def generate_final_output(
    run_id: str, order_id: str, supervisor: dict, completion_reason: str
) -> dict[str, Any]:
    db = SessionLocal()
    try:
        recent_activity_log = _recent_activity_context(run_id)
        run = db.get(Run, run_id)
        current_memory = (
            run.memory_summary if run and run.memory_summary else "No prior memory."
        )
    finally:
        db.close()

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set")

    client = Groq(api_key=api_key)

    base_instruction = supervisor.get("base_instruction", "")

    system_prompt = (
        f"{base_instruction}\n\n"
        "The order workflow is ending. Generate a JSON final summary with exactly this shape:\n"
        "{\n"
        '  "summary": "one sentence about the order outcome",\n'
        '  "actions_taken": ["action1", "action2"],\n'
        '  "key_learnings": ["learning1", "learning2"],\n'
        '  "feedback": ["feedback1"]\n'
        "}\n"
        f"Completion reason: {completion_reason}\n"
        "Return only the JSON object."
    )

    user_context = {
        "run_id": run_id,
        "order_id": order_id,
        "current_memory": current_memory,
        "recent_activity_log": recent_activity_log,
        "completion_reason": completion_reason,
    }

    try:
        response = client.chat.completions.create(
            model=_resolve_model(supervisor),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_context, default=str)},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Groq API call failed for final output of run {run_id}: {exc}"
        ) from exc

    raw_response = response.choices[0].message.content
    if not raw_response:
        raise RuntimeError(f"Groq returned empty final output for run {run_id}")

    try:
        final_output = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Groq returned invalid JSON for final output of run {run_id}: {exc}"
        ) from exc

    if not isinstance(final_output, dict):
        raise RuntimeError(f"Groq returned non-object final output for run {run_id}")

    return {
        "summary": str(final_output.get("summary", "")),
        "actions_taken": (
            final_output.get("actions_taken", [])
            if isinstance(final_output.get("actions_taken"), list)
            else []
        ),
        "key_learnings": (
            final_output.get("key_learnings", [])
            if isinstance(final_output.get("key_learnings"), list)
            else []
        ),
        "feedback": (
            final_output.get("feedback", [])
            if isinstance(final_output.get("feedback"), list)
            else []
        ),
    }


@activity.defn
async def update_run_completion(
    run_id: str, final_output: dict[str, Any], completion_status: str
) -> dict[str, str]:
    """Update runs table with final_summary and status, and log final_output."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        run = db.get(Run, run_id)
        if run is None:
            raise RuntimeError(f"Run {run_id} not found")

        run.final_summary = final_output
        run.status = completion_status
        run.updated_at = now
        db.add(run)

        activity_log_row = ActivityLog(
            id=str(uuid.uuid4()),
            run_id=run_id,
            type="final_output",
            payload=final_output,
            created_at=now,
        )
        db.add(activity_log_row)

        db.commit()
    finally:
        db.close()

    return {
        "status": "updated",
        "run_id": run_id,
        "completion_status": completion_status,
    }


@activity.defn
async def update_run_status(run_id: str, status: str) -> dict[str, str]:
    """Update runs.status for pause/resume operations."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        run = db.get(Run, run_id)
        if run is None:
            raise RuntimeError(f"Run {run_id} not found")

        run.status = status
        run.updated_at = now
        db.commit()
    finally:
        db.close()

    return {"run_id": run_id, "status": status}
