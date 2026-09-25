CREATE TABLE IF NOT EXISTS outreach_execution_records (
    id UUID PRIMARY KEY,
    business_id UUID NOT NULL REFERENCES businesses(id),
    outreach_draft_package_id UUID NOT NULL REFERENCES outreach_draft_packages(id),
    outreach_draft_message_id UUID NOT NULL REFERENCES outreach_draft_messages(id),
    channel VARCHAR(30) NOT NULL,
    operator VARCHAR(200) NOT NULL,
    sent_at TIMESTAMPTZ NOT NULL,
    external_reference VARCHAR(500),
    notes TEXT NOT NULL DEFAULT '',
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resulting_business_state VARCHAR(40) NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_outreach_execution_records_business_id ON outreach_execution_records(business_id);
CREATE INDEX IF NOT EXISTS ix_outreach_execution_records_package_id ON outreach_execution_records(outreach_draft_package_id);
CREATE INDEX IF NOT EXISTS ix_outreach_execution_records_message_id ON outreach_execution_records(outreach_draft_message_id);
