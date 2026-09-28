ALTER TABLE lead_crm_events ADD COLUMN IF NOT EXISTS classification VARCHAR(40);
ALTER TABLE lead_crm_events ADD COLUMN IF NOT EXISTS objection_code VARCHAR(40);
CREATE TABLE IF NOT EXISTS manual_follow_up_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), business_id UUID NOT NULL REFERENCES businesses(id),
    operator_id UUID REFERENCES operators(id), reason TEXT NOT NULL, due_at TIMESTAMPTZ NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'open', created_at TIMESTAMPTZ NOT NULL DEFAULT now(), completed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_manual_follow_up_business_id ON manual_follow_up_tasks(business_id);
CREATE TABLE IF NOT EXISTS outreach_objections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), business_id UUID NOT NULL REFERENCES businesses(id),
    operator VARCHAR(200) NOT NULL, code VARCHAR(40) NOT NULL, notes TEXT NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_outreach_objections_business_id ON outreach_objections(business_id);
