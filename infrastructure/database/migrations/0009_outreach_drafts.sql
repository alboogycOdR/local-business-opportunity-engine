CREATE TABLE IF NOT EXISTS outreach_draft_packages (
    id UUID PRIMARY KEY,
    business_id UUID NOT NULL REFERENCES businesses(id),
    demo_id UUID NOT NULL REFERENCES generated_demos(id),
    brief_id UUID NOT NULL REFERENCES business_briefs(id),
    score_id UUID REFERENCES opportunity_scores(id),
    version VARCHAR(100) NOT NULL,
    offer_type VARCHAR(60) NOT NULL,
    offer_angle TEXT NOT NULL DEFAULT '',
    status VARCHAR(30) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_outreach_draft_packages_business_id ON outreach_draft_packages(business_id);
CREATE INDEX IF NOT EXISTS ix_outreach_draft_packages_demo_id ON outreach_draft_packages(demo_id);

CREATE TABLE IF NOT EXISTS outreach_draft_messages (
    id UUID PRIMARY KEY,
    package_id UUID NOT NULL REFERENCES outreach_draft_packages(id),
    channel VARCHAR(30) NOT NULL,
    subject VARCHAR(300),
    body TEXT NOT NULL,
    tone VARCHAR(50) NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    approved BOOLEAN NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS ix_outreach_draft_messages_package_id ON outreach_draft_messages(package_id);

CREATE TABLE IF NOT EXISTS outreach_draft_checks (
    id UUID PRIMARY KEY,
    package_id UUID NOT NULL REFERENCES outreach_draft_packages(id),
    code VARCHAR(100) NOT NULL,
    passed BOOLEAN NOT NULL DEFAULT false,
    notes TEXT,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_outreach_draft_checks_package_id ON outreach_draft_checks(package_id);
