from datetime import date
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.types import Intent, Label, Objection

Evidence = Annotated[str, Field(min_length=3, max_length=100)]


class LeadAnalysisOut(BaseModel):
    """The model's structured answer. Bounds here are enforced by us, not trusted to the model."""

    model_config = ConfigDict(extra="forbid")

    intent: Intent
    timeline_days: int | None = Field(ge=0, le=730)
    evaluating: bool
    objection: Objection
    disqualified: bool
    do_not_contact: bool
    awaiting_our_reply: bool
    commitment_date: date | None
    commitment_quote: str | None = Field(max_length=200)
    suggested_label: Label
    reason: str = Field(min_length=10, max_length=160)
    follow_up_reason: str = Field(min_length=5, max_length=160)
    # Empty only for do-not-contact leads; guards.check_do_not_contact enforces the pairing.
    draft_message: str = Field(max_length=600)
    evidence: list[Evidence] = Field(min_length=1, max_length=3)


# Keywords the Gemini structured-output docs list as supported. Everything else is dropped from the
# schema we send, because unsupported keywords can get the request rejected; LeadAnalysisOut still
# enforces the full bounds when we parse the reply.
_ALLOWED_KEYS = {
    "type",
    "properties",
    "required",
    "additionalProperties",
    "enum",
    "format",
    "items",
    "minItems",
    "maxItems",
    "minimum",
    "maximum",
    "description",
}


def _simplify(node: Any) -> Any:
    if isinstance(node, list):
        return [_simplify(item) for item in node]
    if not isinstance(node, dict):
        return node
    if "anyOf" in node:
        # Pydantic renders `X | None` as anyOf; the API documents nullability as a type array.
        variants = [v for v in node["anyOf"] if v.get("type") != "null"]
        if len(variants) == 1 and len(node["anyOf"]) == 2:
            merged = {**variants[0], **{k: v for k, v in node.items() if k != "anyOf"}}
            simplified = _simplify(merged)
            simplified["type"] = [simplified["type"], "null"]
            return simplified
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key == "properties":
            out[key] = {name: _simplify(prop) for name, prop in value.items()}
        elif key in _ALLOWED_KEYS:
            out[key] = _simplify(value)
    return out


def model_facing_schema() -> dict[str, Any]:
    schema = LeadAnalysisOut.model_json_schema()
    simplified: dict[str, Any] = _simplify(schema)
    # Every field is required in the reply (nullable ones may be null); this avoids the model
    # silently omitting a signal and us mistaking absence for "false".
    simplified["required"] = list(LeadAnalysisOut.model_fields)
    simplified["additionalProperties"] = False
    return simplified
