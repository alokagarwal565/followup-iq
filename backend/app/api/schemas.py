import re
from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
)

from app.domain.constants import REPS, SOURCES
from app.domain.types import DueState

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _clean(value: object) -> object:
    # Control characters are never meaningful in names or chat text and can corrupt logs/exports.
    # Stripping happens here, before the length checks run, so whitespace-only text is rejected.
    return _CONTROL_CHARS.sub("", value).strip() if isinstance(value, str) else value


def _member_of(allowed: tuple[str, ...]) -> AfterValidator:
    def check(value: str) -> str:
        if value not in allowed:
            raise ValueError(f"must be one of: {', '.join(allowed)}")
        return value

    return AfterValidator(check)


def _valid_phone(value: str) -> str:
    digits = sum(ch.isdigit() for ch in value)
    if not re.fullmatch(r"\+?[0-9 ()\-]{7,20}", value) or not 7 <= digits <= 15:
        raise ValueError("must be a phone number with 7 to 15 digits")
    return value


Name = Annotated[
    str,
    BeforeValidator(_clean),
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]
Company = Annotated[
    str,
    BeforeValidator(_clean),
    StringConstraints(strip_whitespace=True, min_length=1, max_length=160),
]
MessageBody = Annotated[
    str,
    BeforeValidator(_clean),
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2000),
]
DraftBody = Annotated[
    str, BeforeValidator(_clean), StringConstraints(strip_whitespace=True, max_length=1000)
]
SendBody = Annotated[
    str,
    BeforeValidator(_clean),
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
]
Phone = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=20), AfterValidator(_valid_phone)
]
Source = Annotated[str, _member_of(SOURCES)]
Rep = Annotated[str, _member_of(REPS)]
Sender = Literal["rep", "buyer"]
Classification = Literal["Hot", "Warm", "Cold"]


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MessageIn(_Request):
    sender_type: Sender
    body: MessageBody
    sent_at: AwareDatetime | None = None


class LeadCreateIn(_Request):
    name: Name
    company: Company
    phone: Phone
    source: Source
    assigned_rep: Rep
    last_contact_date: date | None = None
    messages: list[MessageIn] = Field(default_factory=list, max_length=20)
    client_request_id: UUID | None = None


class LeadUpdateIn(_Request):
    name: Name | None = None
    company: Company | None = None
    phone: Phone | None = None
    source: Source | None = None
    assigned_rep: Rep | None = None


class MessagesIn(_Request):
    client_request_id: UUID
    messages: list[MessageIn] = Field(min_length=1, max_length=20)


class DraftSaveIn(_Request):
    body: DraftBody
    version: int = Field(ge=1)


class DraftSendIn(_Request):
    body: SendBody
    version: int = Field(ge=1)


class VersionIn(_Request):
    version: int = Field(ge=1)


# --- Responses ----------------------------------------------------------------------------


class LeadRow(BaseModel):
    id: UUID
    name: str
    company: str
    phone: str
    source: str
    assigned_rep: str
    classification: Classification | None
    classification_reason: str | None
    next_follow_up_date: date | None
    due_state: DueState
    days_overdue: int
    last_contact_at: datetime | None
    analysis_status: Literal["never", "pending", "ok", "failed"]
    analysis_source: Literal["gemini", "rules_fallback"] | None
    analysis_error: str | None
    do_not_contact: bool
    awaiting_our_reply: bool


class LeadOut(LeadRow):
    follow_up_reason: str | None
    evidence: list[str]
    rule_id: str | None
    analysis_model: str | None
    analysis_updated_at: datetime | None
    created_at: datetime


class MessageOut(BaseModel):
    id: UUID
    sender_type: Sender
    body: str
    sent_at: datetime
    origin: Literal["seed", "logged", "draft_sent"]


class DraftOut(BaseModel):
    body: str
    suggested_body: str | None
    status: Literal["suggested", "edited", "sent", "none"]
    version: int
    sent_at: datetime | None
    can_undo: bool


class LeadDetailOut(BaseModel):
    lead: LeadOut
    messages: list[MessageOut]
    draft: DraftOut


class LeadListOut(BaseModel):
    items: list[LeadRow]
    total: int


class SummaryOut(BaseModel):
    overdue: int
    today: int
    hot: int
    active: int


class MetaOut(BaseModel):
    today: date
    business_tz: str
    reps: list[str]
    sources: list[str]
    version: str


class AnalyzeOut(BaseModel):
    analysis_status: Literal["pending"]


class ReadyOut(BaseModel):
    status: Literal["ok"]
    db: Literal["ok"]
    ai: Literal["configured", "unconfigured"]
