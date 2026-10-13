import type { Draft, Lead, LeadDetail, LeadRow, Message, Meta, Summary } from "@/lib/types";

export const TODAY = "2026-10-12";
export const TZ = "Asia/Kolkata";

export const meta: Meta = {
  today: TODAY,
  business_tz: TZ,
  reps: ["Priya Sharma", "Arjun Mehta", "Neha Kulkarni", "Rohit Verma", "Sana Qureshi"],
  sources: ["Excel sheet", "WhatsApp", "Website", "Referral", "Trade show", "IndiaMART"],
  version: "0.1.0",
};

export function row(overrides: Partial<LeadRow> = {}): LeadRow {
  return {
    id: "lead-1",
    name: "Rahul Mehta",
    company: "Shree Snacks Pvt Ltd",
    phone: "+91 90000 01001",
    source: "IndiaMART",
    assigned_rep: "Priya Sharma",
    classification: "Hot",
    classification_reason: "Asked for a quote for 2 pouch fillers, ordering this month.",
    next_follow_up_date: "2026-10-09",
    due_state: "overdue",
    days_overdue: 3,
    last_contact_at: "2026-10-08T06:00:00Z",
    analysis_status: "ok",
    analysis_source: "gemini",
    analysis_error: null,
    do_not_contact: false,
    awaiting_our_reply: false,
    ...overrides,
  };
}

export function lead(overrides: Partial<Lead> = {}): Lead {
  return {
    ...row(),
    follow_up_reason: "Send the promised quotation.",
    evidence: ["Asked for a quote for 2 pouch fillers", "Wants to order this month"],
    rule_id: "H1",
    analysis_model: "gemini-3.6-flash",
    analysis_updated_at: "2026-10-12T05:00:00Z",
    created_at: "2026-10-05T06:00:00Z",
    ...overrides,
  };
}

export function message(overrides: Partial<Message> = {}): Message {
  return {
    id: "m1",
    sender_type: "buyer",
    body: "Need a quote for 2 pouch fillers.",
    sent_at: "2026-10-08T06:00:00Z",
    origin: "seed",
    ...overrides,
  };
}

export function draft(overrides: Partial<Draft> = {}): Draft {
  return {
    body: "Hi Rahul, sharing the quotation for both pouch fillers today.",
    suggested_body: null,
    status: "suggested",
    version: 3,
    sent_at: null,
    can_undo: false,
    ...overrides,
  };
}

export function detail(overrides: Partial<LeadDetail> = {}): LeadDetail {
  return {
    lead: lead(),
    messages: [
      message(),
      message({ id: "m2", sender_type: "rep", body: "Sure, sending it soon." }),
    ],
    draft: draft(),
    ...overrides,
  };
}

export const summary: Summary = { overdue: 4, today: 5, hot: 6, active: 21 };
