"""Runs the live agent over the sample chats and prints expected vs actual tags and the drafts.

    python -m app.cli.eval            all seeded leads that have a chat
    python -m app.cli.eval --all      include Excel-only leads too

This is the evidence for "the tags make sense": a human reads the output. It calls Gemini once
per lead (paced to respect free-tier limits) and never touches the database.
"""

import argparse
import asyncio
from datetime import UTC, datetime, timedelta

from app.ai.analyzer import GeminiAnalyzer
from app.ai.prompt import PromptContext, PromptMessage
from app.ai.provider import AnalysisFailed
from app.ai.validation import make_validator
from app.cli.seed import _at, _last_contact
from app.config import load_settings
from app.domain.facts import MessageView, compute_facts
from app.domain.rules import business_today, due_state
from app.logging import configure_logging
from app.runtime import run
from app.seed_data import SEED_LEADS

PACING_SECONDS = 4.0


async def main(include_all: bool, only: str | None) -> None:
    settings = load_settings()
    configure_logging("WARNING")
    analyzer = GeminiAnalyzer(settings)
    now = datetime.now(UTC)
    tz = settings.tz
    today = business_today(tz, now)
    leads = [lead for lead in SEED_LEADS if (include_all or lead.messages)]
    if only:
        leads = [lead for lead in leads if only in lead.key]
    matches = 0
    for index, lead in enumerate(leads):
        if index:
            await asyncio.sleep(PACING_SECONDS)
        times = [_at(today - timedelta(days=m.days_ago), m.time, tz) for m in lead.messages]
        facts = compute_facts(
            [MessageView(m.sender, t, t) for m, t in zip(lead.messages, times, strict=True)],
            created_at=now - timedelta(days=lead.created_days_ago),
            last_contact_at=_last_contact(lead, today, tz),
            tz=tz,
            today=today,
        )
        context = PromptContext(
            today=today,
            tz=tz,
            rep_name=lead.rep,
            buyer_name=lead.name,
            company=lead.company,
            source=lead.source,
            facts=facts,
            messages=[
                PromptMessage(m.sender, t, m.body)
                for m, t in zip(lead.messages, times, strict=True)
            ],
        )
        print(f"\n=== {lead.name} / {lead.company}  ({lead.scenario})")
        try:
            result = await analyzer.analyze(
                context=context, validate=make_validator(context), lead_id=lead.key
            )
        except AnalysisFailed as failure:
            print(f"  FAILED: {failure.category} after {failure.attempts} attempts")
            continue
        a = result.value
        ok = a.label == lead.expected_label
        matches += ok
        print(
            f"  expected {lead.expected_label:<4} got {a.label:<4} ({a.rule_id})"
            f"  {'MATCH' if ok else 'DIFF'}   model={result.model} attempts={result.attempts}"
        )
        print(f"  reason:    {a.out.reason}")
        due = due_state(a.follow_up, today)
        print(f"  follow-up: {a.follow_up} [{due}, {a.follow_up_basis}]  {a.out.follow_up_reason}")
        print(f"  draft:     {a.out.draft_message or '(none: do not contact)'}")
    print(f"\n{matches}/{len(leads)} tags matched the expected labels.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="include leads without a chat")
    parser.add_argument("--only", help="run only leads whose key contains this text")
    args = parser.parse_args()
    run(main(args.all, args.only))
