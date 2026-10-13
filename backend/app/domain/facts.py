from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.domain.types import Facts, Sender


@dataclass(frozen=True)
class MessageView:
    sender_type: Sender
    sent_at: datetime
    created_at: datetime


def compute_facts(
    messages: Sequence[MessageView],
    *,
    created_at: datetime,
    last_contact_at: datetime | None,
    tz: ZoneInfo,
    today: date,
) -> Facts:
    # created_at breaks sent_at ties so messages logged with one timestamp keep their entry order.
    ordered = sorted(messages, key=lambda m: (m.sent_at, m.created_at))

    last_buyer_index = max(
        (i for i, m in enumerate(ordered) if m.sender_type == "buyer"), default=None
    )
    if last_buyer_index is None:
        last_buyer_date = None
        unanswered = len(ordered)
    else:
        last_buyer_date = ordered[last_buyer_index].sent_at.astimezone(tz).date()
        unanswered = len(ordered) - last_buyer_index - 1

    contact_candidates = [m.sent_at for m in ordered]
    if last_contact_at is not None:
        contact_candidates.append(last_contact_at)
    last_contact = max(contact_candidates, default=None)

    return Facts(
        has_conversation=bool(ordered),
        last_sender=ordered[-1].sender_type if ordered else None,
        last_buyer_message_date=last_buyer_date,
        days_since_buyer_reply=(today - last_buyer_date).days if last_buyer_date else None,
        unanswered_rep_messages=unanswered,
        last_contact_date=last_contact.astimezone(tz).date() if last_contact else None,
        created_date=created_at.astimezone(tz).date(),
    )
