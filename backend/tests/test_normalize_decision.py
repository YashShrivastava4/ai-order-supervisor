"""Unit tests for _normalize_decision — the block that cleans up whatever
JSON shape Groq hands back into something the rest of the app can trust.

No Temporal, no DB, no network: this is a pure function, so we can just feed
it malformed shapes directly and check it falls back to safe defaults
instead of raising.
"""
from app.activities import _normalize_decision


def test_empty_decision_falls_back_to_defaults():
    result = _normalize_decision({}, current_memory="prior memory")
    assert result["actions"] == []
    assert result["wakeup_guidance"] == []
    assert result["memory_summary"] == "prior memory"
    assert result["sleep"] == {"mode": "duration_hours", "value": 6}
    assert result["recommend_completion"] is False
    assert isinstance(result["reasoning"], str) and result["reasoning"]


def test_actions_with_missing_fields_are_dropped():
    decision = {
        "actions": [
            {"type": "message_customer", "details": "hello"},  # valid
            {"type": "message_customer"},  # missing details
            {"details": "no type"},  # missing type
            "not_even_a_dict",  # wrong shape entirely
            None,
        ]
    }
    result = _normalize_decision(decision, current_memory="mem")
    assert result["actions"] == [{"type": "message_customer", "details": "hello"}]


def test_non_list_actions_field_is_ignored():
    result = _normalize_decision({"actions": "not-a-list"}, current_memory="mem")
    assert result["actions"] == []


def test_non_list_wakeup_guidance_is_ignored():
    result = _normalize_decision({"wakeup_guidance": "not-a-list"}, current_memory="mem")
    assert result["wakeup_guidance"] == []


def test_wakeup_guidance_items_are_stringified():
    result = _normalize_decision({"wakeup_guidance": ["shipment_delayed", 123]}, current_memory="mem")
    assert result["wakeup_guidance"] == ["shipment_delayed", "123"]


def test_invalid_sleep_mode_falls_back_to_duration_hours():
    result = _normalize_decision({"sleep": {"mode": "not_a_real_mode"}}, current_memory="mem")
    assert result["sleep"] == {"mode": "duration_hours", "value": 6}


def test_non_numeric_sleep_value_falls_back_to_six_hours():
    result = _normalize_decision(
        {"sleep": {"mode": "duration_hours", "value": "not_a_number"}},
        current_memory="mem",
    )
    assert result["sleep"] == {"mode": "duration_hours", "value": 6}


def test_until_next_event_sleep_mode_is_preserved():
    result = _normalize_decision(
        {"sleep": {"mode": "until_next_event"}}, current_memory="mem"
    )
    assert result["sleep"] == {"mode": "until_next_event"}


def test_missing_memory_summary_falls_back_to_current_memory():
    result = _normalize_decision({"memory_summary": ""}, current_memory="the prior summary")
    assert result["memory_summary"] == "the prior summary"


def test_recommend_completion_is_coerced_to_bool():
    assert _normalize_decision({"recommend_completion": "true"}, current_memory="mem")[
        "recommend_completion"
    ] is True
    assert _normalize_decision({"recommend_completion": 0}, current_memory="mem")[
        "recommend_completion"
    ] is False
