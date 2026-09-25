CREATE TABLE IF NOT EXISTS outreach_readiness_reviews (
    id UUID PRIMARY KEY,
    business_id UUID NOT NULL REFERENCES businesses(id),
    outreach_draft_package_id UUID NOT NULL REFERENCES outreach_draft_packages(id),
    decision VARCHAR(50) NOT NULL,
    reviewer VARCHAR(200) NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    consent_basis_type VARCHAR(60) NOT NULL,
    consent_basis_notes TEXT NOT NULL DEFAULT '',
    resulting_business_state VARCHAR(40) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_outreach_readiness_reviews_business_id ON outreach_readiness_reviews(business_id);
CREATE INDEX IF NOT EXISTS ix_outreach_readiness_reviews_package_id ON outreach_readiness_reviews(outreach_draft_package_id);

CREATE TABLE IF NOT EXISTS outreach_channel_approvals (
    id UUID PRIMARY KEY,
    outreach_readiness_review_id UUID NOT NULL REFERENCES outreach_readiness_reviews(id),
    channel VARCHAR(30) NOT NULL,
    outreach_draft_message_id UUID REFERENCES outreach_draft_messages(id),
    approved BOOLEAN NOT NULL DEFAULT false,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS ix_outreach_channel_approvals_review_id ON outreach_channel_approvals(outreach_readiness_review_id);

CREATE TABLE IF NOT EXISTS outreach_readiness_checks (
    id UUID PRIMARY KEY,
    outreach_readiness_review_id UUID NOT NULL REFERENCES outreach_readiness_reviews(id),
    code VARCHAR(100) NOT NULL,
    passed BOOLEAN NOT NULL DEFAULT false,
    notes TEXT,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_outreach_readiness_checks_review_id ON outreach_readiness_checks(outreach_readiness_review_id);
