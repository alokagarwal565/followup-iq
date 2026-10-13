from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Query, status

from app.api import presenters
from app.api.deps import Conn, Now, Scheduler, SettingsDep
from app.api.schemas import (
    AnalyzeOut,
    Classification,
    DraftOut,
    DraftSaveIn,
    DraftSendIn,
    LeadCreateIn,
    LeadDetailOut,
    LeadListOut,
    LeadUpdateIn,
    MessagesIn,
    SummaryOut,
    VersionIn,
)
from app.services import drafts as draft_service
from app.services import leads as lead_service
from app.services.leads import NewLead, NewMessage

router = APIRouter(prefix="/api/v1", tags=["leads"])

DueFilter = Literal["overdue", "today", "upcoming", "none"]


async def _detail(conn: Conn, lead_id: UUID, now: Now) -> LeadDetailOut:
    detail = await lead_service.get_detail(conn, lead_id)
    return presenters.lead_detail(detail, today=now.today, now=now.now)


@router.get("/leads", response_model=LeadListOut)
async def list_leads(
    conn: Conn,
    now: Now,
    q: Annotated[str | None, Query(max_length=80)] = None,
    rep: Annotated[str | None, Query(max_length=60)] = None,
    classification: Classification | None = None,
    due_state: DueFilter | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> LeadListOut:
    leads = await lead_service.queue(
        conn, today=now.today, rep=rep, classification=classification, q=q, due=due_state
    )
    page = leads[offset : offset + limit]
    return LeadListOut(
        items=[presenters.lead_row(lead, today=now.today, now=now.now) for lead in page],
        total=len(leads),
    )


@router.get("/summary", response_model=SummaryOut)
async def get_summary(
    conn: Conn, now: Now, rep: Annotated[str | None, Query(max_length=60)] = None
) -> SummaryOut:
    return SummaryOut(**await lead_service.summary(conn, today=now.today, rep=rep))


@router.post("/leads", status_code=status.HTTP_201_CREATED, response_model=LeadDetailOut)
async def create_lead(
    body: LeadCreateIn,
    conn: Conn,
    now: Now,
    settings: SettingsDep,
    background: BackgroundTasks,
    schedule: Scheduler,
) -> LeadDetailOut:
    lead_id, created = await lead_service.create_lead(
        conn,
        NewLead(
            name=body.name,
            company=body.company,
            phone=body.phone,
            source=body.source,
            assigned_rep=body.assigned_rep,
            last_contact_date=body.last_contact_date,
            messages=[NewMessage(m.sender_type, m.body, m.sent_at) for m in body.messages],
            request_id=body.client_request_id,
        ),
        now=now.now,
        tz=settings.tz,
    )
    if created:
        schedule(background, lead_id)
    return await _detail(conn, lead_id, now)


@router.get("/leads/{lead_id}", response_model=LeadDetailOut)
async def get_lead(lead_id: UUID, conn: Conn, now: Now) -> LeadDetailOut:
    return await _detail(conn, lead_id, now)


@router.patch("/leads/{lead_id}", response_model=LeadDetailOut)
async def update_lead(lead_id: UUID, body: LeadUpdateIn, conn: Conn, now: Now) -> LeadDetailOut:
    await lead_service.update_lead(conn, lead_id, body.model_dump(exclude_none=True))
    return await _detail(conn, lead_id, now)


@router.post(
    "/leads/{lead_id}/messages", status_code=status.HTTP_201_CREATED, response_model=LeadDetailOut
)
async def add_messages(
    lead_id: UUID,
    body: MessagesIn,
    conn: Conn,
    now: Now,
    background: BackgroundTasks,
    schedule: Scheduler,
) -> LeadDetailOut:
    stored = await lead_service.add_messages(
        conn,
        lead_id,
        [NewMessage(m.sender_type, m.body, m.sent_at) for m in body.messages],
        request_id=body.client_request_id,
        now=now.now,
    )
    if stored:
        schedule(background, lead_id)
    return await _detail(conn, lead_id, now)


@router.put("/leads/{lead_id}/draft", response_model=DraftOut)
async def save_draft(lead_id: UUID, body: DraftSaveIn, conn: Conn, now: Now) -> DraftOut:
    await draft_service.save(conn, lead_id, body=body.body, version=body.version)
    return (await _detail(conn, lead_id, now)).draft


@router.post("/leads/{lead_id}/draft/accept-suggestion", response_model=DraftOut)
async def accept_suggestion(lead_id: UUID, body: VersionIn, conn: Conn, now: Now) -> DraftOut:
    await draft_service.accept_suggestion(conn, lead_id, version=body.version)
    return (await _detail(conn, lead_id, now)).draft


@router.post("/leads/{lead_id}/draft/send", response_model=LeadDetailOut)
async def send_draft(
    lead_id: UUID,
    body: DraftSendIn,
    conn: Conn,
    now: Now,
    settings: SettingsDep,
    background: BackgroundTasks,
    schedule: Scheduler,
) -> LeadDetailOut:
    sent = await draft_service.send(
        conn, lead_id, body=body.body, version=body.version, now=now.now, tz=settings.tz
    )
    if sent:
        schedule(background, lead_id)
    return await _detail(conn, lead_id, now)


@router.post("/leads/{lead_id}/draft/undo-send", response_model=LeadDetailOut)
async def undo_send(lead_id: UUID, conn: Conn, now: Now) -> LeadDetailOut:
    await draft_service.undo_send(conn, lead_id, now=now.now)
    return await _detail(conn, lead_id, now)


@router.post(
    "/leads/{lead_id}/analyze", status_code=status.HTTP_202_ACCEPTED, response_model=AnalyzeOut
)
async def analyze(
    lead_id: UUID, conn: Conn, now: Now, background: BackgroundTasks, schedule: Scheduler
) -> AnalyzeOut:
    await lead_service.request_analysis(conn, lead_id, now=now.now)
    # An explicit request re-runs Gemini even if the conversation is unchanged.
    schedule(background, lead_id, force=True)
    return AnalyzeOut(analysis_status="pending")
