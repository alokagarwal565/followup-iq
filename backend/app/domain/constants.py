from typing import Final

# Mirrored by CHECK constraints in migrations/001_init.sql; change both together.
REPS: Final = ("Priya Sharma", "Arjun Mehta", "Neha Kulkarni", "Rohit Verma", "Sana Qureshi")
SOURCES: Final = ("Excel sheet", "WhatsApp", "Website", "Referral", "Trade show", "IndiaMART")

STRONG_INTENTS: Final = frozenset(
    {"quote_requested", "demo_requested", "negotiating", "ready_to_order"}
)

HOT_MAX_TIMELINE_DAYS: Final = 30
HOT_MAX_DAYS_SINCE_REPLY: Final = 14
COLD_MIN_UNANSWERED: Final = 3
COLD_MIN_SILENCE_DAYS: Final = 21
STALE_CONTACT_DAYS: Final = 30
COMMITMENT_WINDOW_DAYS: Final = 120

CADENCE_DAYS: Final = {"Hot": 1, "Warm": 3}
COLD_UNRESPONSIVE_DAYS: Final = 14
COLD_LOST_DAYS: Final = 90

RULE_DESCRIPTIONS: Final = {
    "C1": "the buyer is not interested, bought elsewhere, is not a fit, or asked for no contact",
    "C2": "three or more follow-ups went unanswered and the buyer has been silent for 21+ days",
    "C3": "there is no conversation and no contact in the last 30 days",
    "H1": "clear buying intent with a timeline of 30 days or active evaluation, and a recent reply",
    "W1": "there is interest but no committed timeline",
    "W2": "the project is postponed or the timeline is beyond 30 days",
    "W3": "the buyer is evaluating or waiting on information",
    "W4": "this is a new lead with no conversation yet",
}
