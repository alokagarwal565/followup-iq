-- FollowUpIQ initial schema. Forward-only: fix mistakes with a new migration file.
-- Conventions (see docs/IMPLEMENTATION_PLAN.md §4): id → FKs → business columns → created_at → updated_at;
-- every FK indexed with the FK column leading; explicit ON DELETE; CHECKs only for bounds the API enforces.

-- gen_random_uuid() is built into PostgreSQL 13+, so no extension is needed.

CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END $$;

CREATE TABLE leads (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name                   text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 120),
  company                text NOT NULL CHECK (char_length(company) BETWEEN 1 AND 160),
  phone                  text NOT NULL CHECK (char_length(phone) BETWEEN 7 AND 20),
  -- Digits-only form so "+91 90000 01234" and "9000001234"-style variants collide as duplicates.
  phone_digits           text NOT NULL CHECK (phone_digits ~ '^[0-9]{7,15}$'),
  source                 text NOT NULL CHECK (source IN ('Excel sheet','WhatsApp','Website','Referral','Trade show','IndiaMART')),
  assigned_rep           text NOT NULL CHECK (assigned_rep IN ('Priya Sharma','Arjun Mehta','Neha Kulkarni','Rohit Verma','Sana Qureshi')),
  last_contact_at        timestamptz,
  do_not_contact         boolean NOT NULL DEFAULT false,
  classification         text CHECK (classification IN ('Hot','Warm','Cold')),
  classification_reason  text CHECK (char_length(classification_reason) <= 200),
  -- A calendar day in the business timezone, never a timestamp, so it cannot shift under UTC conversion.
  next_follow_up_date    date,
  follow_up_reason       text CHECK (char_length(follow_up_reason) <= 200),
  evidence               jsonb NOT NULL DEFAULT '[]'::jsonb,
  signals                jsonb,
  analysis_status        text NOT NULL DEFAULT 'never' CHECK (analysis_status IN ('never','pending','ok','failed')),
  analysis_source        text CHECK (analysis_source IN ('gemini','rules_fallback')),
  analysis_model         text,
  analysis_error         text,
  analysis_requested_at  timestamptz,
  analysis_updated_at    timestamptz,
  analysis_fingerprint   text,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_leads_phone_digits ON leads (phone_digits);
CREATE INDEX ix_leads_next_follow_up_date ON leads (next_follow_up_date);
CREATE INDEX ix_leads_assigned_rep ON leads (assigned_rep);
CREATE TRIGGER trg_leads_updated_at BEFORE UPDATE ON leads
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE conversations (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id     uuid NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  channel     text NOT NULL DEFAULT 'whatsapp' CHECK (channel IN ('whatsapp')),
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_conversations_lead_id ON conversations (lead_id);

CREATE TABLE messages (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id    uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  sender_type        text NOT NULL CHECK (sender_type IN ('rep','buyer')),
  body               text NOT NULL CHECK (char_length(body) BETWEEN 1 AND 2000),
  sent_at            timestamptz NOT NULL,
  origin             text NOT NULL DEFAULT 'logged' CHECK (origin IN ('seed','logged','draft_sent')),
  -- Idempotency key for one "Log chat" / "Add lead" submission, which may insert several messages.
  client_request_id  uuid,
  -- clock_timestamp(), not now(): several messages inserted in one transaction must keep their
  -- entry order, and now() is fixed for the whole transaction.
  created_at         timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX ix_messages_conversation_id_sent_at ON messages (conversation_id, sent_at);
CREATE INDEX ix_messages_client_request_id ON messages (client_request_id) WHERE client_request_id IS NOT NULL;

CREATE TABLE drafts (
  lead_id         uuid PRIMARY KEY REFERENCES leads(id) ON DELETE CASCADE,
  body            text NOT NULL DEFAULT '' CHECK (char_length(body) <= 1000),
  -- Newer AI suggestion held aside while the rep has unsent edits, so edits are never overwritten.
  suggested_body  text CHECK (char_length(suggested_body) <= 1000),
  status          text NOT NULL DEFAULT 'none' CHECK (status IN ('suggested','edited','sent','none')),
  version         integer NOT NULL DEFAULT 1 CHECK (version >= 1),
  sent_at         timestamptz,
  undo_snapshot   jsonb,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_drafts_updated_at BEFORE UPDATE ON drafts
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Defense in depth: the Supabase Data API is off, and the backend connects as the table owner,
-- which RLS does not restrict. Any other role gets no access by default.
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE drafts ENABLE ROW LEVEL SECURITY;
