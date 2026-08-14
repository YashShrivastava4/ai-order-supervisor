"""Seeds the 2 hardcoded supervisor templates (PDF: "hardcoded templates are
acceptable"). Called from main.py's startup event, and reused later by S12's
seed_demo.py so the demo reset script doesn't duplicate this list.
"""
from sqlalchemy.orm import Session

from app.db.models import SupervisorConfig

_ACTIONS = [
    "message_fulfillment_team",
    "message_payments_team",
    "message_logistics_team",
    "message_customer",
    "create_internal_note",
]

_TEMPLATES = [
    dict(
        name="Standard Order Supervisor",
        base_instruction=(
            "You are an order supervisor monitoring a standard order from "
            "creation to delivery. Act only when something needs a person's "
            "attention, keep the customer informed on major status changes, "
            "and prefer the least disruptive action that resolves the issue."
        ),
        available_actions=_ACTIONS,
        default_wake_seconds=21600,  # 6h
        wake_aggressiveness="balanced",
        model_config={"provider": "groq", "model": "openai/gpt-oss-120b"},
    ),
    dict(
        name="High-Touch VIP Supervisor",
        base_instruction=(
            "You are supervising a VIP order. Err on the side of proactive "
            "communication — flag problems early, escalate delays "
            "immediately, and prioritize customer experience over cost or "
            "speed."
        ),
        available_actions=_ACTIONS,
        default_wake_seconds=3600,  # 1h
        wake_aggressiveness="aggressive",
        model_config={"provider": "groq", "model": "openai/gpt-oss-120b"},
    ),
]


def seed_supervisor_templates(db: Session) -> None:
    for template in _TEMPLATES:
        exists = db.query(SupervisorConfig).filter_by(name=template["name"]).first()
        if exists:
            continue
        db.add(SupervisorConfig(**template))
    db.commit()
