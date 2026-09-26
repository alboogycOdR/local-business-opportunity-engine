CREATE TABLE IF NOT EXISTS lead_crm_events (
    id UUID PRIMARY KEY,
    business_id UUID NOT NULL REFERENCES businesses(id),
    outreach_execution_record_id UUID REFERENCES outreach_execution_records(id),
    event_type VARCHAR(40) NOT NULL,
    channel VARCHAR(30) NOT NULL,
    operator VARCHAR(200) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    next_step TEXT,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    resulting_business_state VARCHAR(40) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_lead_crm_events_business_id ON lead_crm_events(business_id);
CREATE INDEX IF NOT EXISTS ix_lead_crm_events_execution_id ON lead_crm_events(outreach_execution_record_id);
