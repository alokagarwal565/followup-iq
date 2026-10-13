import json
from datetime import date

import pytest
from pydantic import ValidationError

from app.ai.schema import LeadAnalysisOut, model_facing_schema

VALID = {
    "intent": "quote_requested",
    "timeline_days": 14,
    "evaluating": True,
    "objection": "none",
    "disqualified": False,
    "do_not_contact": False,
    "awaiting_our_reply": False,
    "commitment_date": "2026-10-16",
    "commitment_quote": "will send the quote by Friday",
    "suggested_label": "Hot",
    "reason": "Asked for a quote for two pouch fillers and wants to order this month.",
    "follow_up_reason": "Send the promised quote.",
    "draft_message": "Hi Rahul, sharing the quote for both pouch fillers today. Does Friday work?",
    "evidence": ["Asked for a quote for 2 pouch fillers", "Wants to order this month"],
}


def test_valid_output_round_trips():
    parsed = LeadAnalysisOut.model_validate_json(json.dumps(VALID))
    assert parsed.commitment_date == date(2026, 10, 16)
    assert parsed.suggested_label == "Hot"


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        LeadAnalysisOut.model_validate_json(json.dumps({**VALID, "budget": "10 lakh"}))


def test_label_outside_hot_warm_cold_is_rejected():
    with pytest.raises(ValidationError):
        LeadAnalysisOut.model_validate_json(json.dumps({**VALID, "suggested_label": "Lukewarm"}))


def test_reason_length_is_bounded():
    with pytest.raises(ValidationError):
        LeadAnalysisOut.model_validate_json(json.dumps({**VALID, "reason": "x" * 161}))


def test_evidence_needs_one_to_three_items():
    with pytest.raises(ValidationError):
        LeadAnalysisOut.model_validate_json(json.dumps({**VALID, "evidence": []}))
    with pytest.raises(ValidationError):
        LeadAnalysisOut.model_validate_json(json.dumps({**VALID, "evidence": ["a", "b", "c", "d"]}))


def test_malformed_date_is_rejected():
    with pytest.raises(ValidationError):
        LeadAnalysisOut.model_validate_json(json.dumps({**VALID, "commitment_date": "next Friday"}))


def _walk(node: object):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def test_model_facing_schema_uses_only_documented_keywords():
    schema = model_facing_schema()
    for node in _walk(schema):
        assert "minLength" not in node and "maxLength" not in node
        assert "anyOf" not in node, "nullable fields must use type arrays"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(LeadAnalysisOut.model_fields)


def test_model_facing_schema_expresses_nullability_as_type_arrays():
    props = model_facing_schema()["properties"]
    assert props["commitment_date"]["type"] == ["string", "null"]
    assert props["commitment_date"]["format"] == "date"
    assert props["timeline_days"]["type"] == ["integer", "null"]
    assert props["suggested_label"]["enum"] == ["Hot", "Warm", "Cold"]
