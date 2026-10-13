from datetime import date, datetime

from app.api.schemas import DraftOut, LeadDetailOut, LeadOut, LeadRow, MessageOut
from app.db.records import LeadRecord
from app.domain.rules import days_overdue, due_state
from app.services.drafts import can_undo
from app.services.leads import LeadDetail
from app.services.status import effective_analysis_status


def lead_row(lead: LeadRecord, *, today: date, now: datetime) -> LeadRow:
    status, error = effective_analysis_status(lead, now)
    return LeadRow(
        id=lead.id,
        name=lead.name,
        company=lead.company,
        phone=lead.phone,
        source=lead.source,
        assigned_rep=lead.assigned_rep,
        classification=lead.classification,
        classification_reason=lead.classification_reason,
        next_follow_up_date=lead.next_follow_up_date,
        due_state=due_state(lead.next_follow_up_date, today),
        days_overdue=days_overdue(lead.next_follow_up_date, today),
        last_contact_at=lead.last_contact_at,
        analysis_status=status,
        analysis_source=lead.analysis_source,
        analysis_error=error,
        do_not_contact=lead.do_not_contact,
        awaiting_our_reply=lead.awaiting_our_reply,
    )


def lead_detail(detail: LeadDetail, *, today: date, now: datetime) -> LeadDetailOut:
    lead = detail.lead
    row = lead_row(lead, today=today, now=now)
    return LeadDetailOut(
        lead=LeadOut(
            **row.model_dump(),
            follow_up_reason=lead.follow_up_reason,
            evidence=list(lead.evidence or []),
            rule_id=lead.rule_id,
            analysis_model=lead.analysis_model,
            analysis_updated_at=lead.analysis_updated_at,
            created_at=lead.created_at,
        ),
        messages=[
            MessageOut(
                id=m.id,
                sender_type=m.sender_type,
                body=m.body,
                sent_at=m.sent_at,
                origin=m.origin,
            )
            for m in detail.messages
        ],
        draft=DraftOut(
            body=detail.draft.body,
            suggested_body=detail.draft.suggested_body,
            status=detail.draft.status,
            version=detail.draft.version,
            sent_at=detail.draft.sent_at,
            can_undo=can_undo(detail.draft, now),
        ),
    )
