from datetime import datetime, timedelta

from app.db.records import LeadRecord

# Longer than the analysis deadline plus slack, so a live analysis is never reported as stuck.
STALE_PENDING_AFTER = timedelta(seconds=120)


def effective_analysis_status(lead: LeadRecord, now: datetime) -> tuple[str, str | None]:
    """Reported status without writing on read: a restart can kill a background analysis, and a
    pending flag that outlives its deadline is shown as interrupted so the UI offers a retry."""
    if (
        lead.analysis_status == "pending"
        and lead.analysis_requested_at is not None
        and now - lead.analysis_requested_at > STALE_PENDING_AFTER
    ):
        return "failed", "interrupted"
    return lead.analysis_status, lead.analysis_error
