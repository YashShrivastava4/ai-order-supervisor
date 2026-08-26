"""Unit tests for classify_event — pure function, no Temporal or DB needed.

One case per branch in app.activities.classify_event.
"""
from app.activities import classify_event


def test_urgent_event_wakes_now():
    assert classify_event("shipment_delayed") == "wake_now"


def test_routine_event_logs_and_waits_by_default():
    assert classify_event("order_created") == "log_and_wait"


def test_routine_event_wakes_now_when_aggressiveness_is_high():
    assert classify_event("order_created", wakeup_aggressiveness="high") == "wake_now"


def test_unknown_event_defaults_to_wake_now():
    # Anything the classifier hasn't seen before is treated as worth a look,
    # rather than silently logged and possibly missed.
    assert classify_event("some_future_event_type") == "wake_now"


def test_wakeup_guidance_overrides_a_routine_event():
    # Even a normally-routine event should wake the agent if the agent
    # itself previously asked to be told about it.
    assert (
        classify_event("order_created", wakeup_guidance=["order_created"])
        == "wake_now"
    )
