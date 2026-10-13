from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class LeadRecord:
    id: UUID
    name: str
    company: str
    phone: str
    phone_digits: str
    source: str
    assigned_rep: str
    last_contact_at: datetime | None
    do_not_contact: bool
    classification: str | None
    classification_reason: str | None
    next_follow_up_date: date | None
    follow_up_reason: str | None
    evidence: list[str]
    signals: dict[str, Any] | None
    analysis_status: str
    analysis_source: str | None
    analysis_model: str | None
    analysis_error: str | None
    analysis_requested_at: datetime | None
    analysis_updated_at: datetime | None
    analysis_fingerprint: str | None
    created_at: datetime
    updated_at: datetime

    @property
    def rule_id(self) -> str | None:
        value = (self.signals or {}).get("rule_id")
        return str(value) if value else None

    @property
    def awaiting_our_reply(self) -> bool:
        # Stored by the analysis only when the follow-up date was set because the buyer is waiting.
        return (self.signals or {}).get("follow_up_basis") == "awaiting_reply"


@dataclass(frozen=True)
class MessageRecord:
    id: UUID
    conversation_id: UUID
    sender_type: str
    body: str
    sent_at: datetime
    origin: str
    client_request_id: UUID | None
    created_at: datetime


@dataclass(frozen=True)
class DraftRecord:
    lead_id: UUID
    body: str
    suggested_body: str | None
    status: str
    version: int
    sent_at: datetime | None
    undo_snapshot: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
