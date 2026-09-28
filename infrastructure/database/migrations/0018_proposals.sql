CREATE TABLE IF NOT EXISTS proposal_packages (
    id UUID PRIMARY KEY, business_id UUID NOT NULL REFERENCES businesses(id),
    score_id UUID NULL REFERENCES opportunity_scores(id), audit_run_id UUID NULL REFERENCES audit_runs(id),
    brief_id UUID NULL REFERENCES business_briefs(id), demo_id UUID NULL REFERENCES generated_demos(id),
    version VARCHAR(100) NOT NULL, proposal_type VARCHAR(60) NOT NULL, status VARCHAR(40) NOT NULL,
    summary TEXT NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_proposal_packages_business ON proposal_packages(business_id);
CREATE TABLE IF NOT EXISTS proposal_sections (
    id UUID PRIMARY KEY, proposal_id UUID NOT NULL REFERENCES proposal_packages(id),
    section_type VARCHAR(60) NOT NULL, heading VARCHAR(300) NOT NULL, body TEXT NOT NULL,
    sort_order INTEGER NOT NULL, evidence JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE IF NOT EXISTS proposal_line_items (
    id UUID PRIMARY KEY, proposal_id UUID NOT NULL REFERENCES proposal_packages(id),
    code VARCHAR(100) NOT NULL, label VARCHAR(300) NOT NULL, description TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1, unit VARCHAR(80) NOT NULL, pricing_status VARCHAR(40) NOT NULL
);
CREATE TABLE IF NOT EXISTS proposal_assumptions (
    id UUID PRIMARY KEY, proposal_id UUID NOT NULL REFERENCES proposal_packages(id),
    code VARCHAR(100) NOT NULL, text TEXT NOT NULL, category VARCHAR(60) NOT NULL
);
CREATE TABLE IF NOT EXISTS proposal_review_events (
    id UUID PRIMARY KEY, proposal_id UUID NOT NULL REFERENCES proposal_packages(id),
    decision VARCHAR(40) NOT NULL, reviewer VARCHAR(200) NOT NULL, notes TEXT NOT NULL DEFAULT '',
    checks JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS proposal_exports (
    id UUID PRIMARY KEY, proposal_id UUID NOT NULL REFERENCES proposal_packages(id),
    status VARCHAR(30) NOT NULL, files JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_proposal_sections_proposal ON proposal_sections(proposal_id);
CREATE INDEX IF NOT EXISTS ix_proposal_line_items_proposal ON proposal_line_items(proposal_id);
CREATE INDEX IF NOT EXISTS ix_proposal_reviews_proposal ON proposal_review_events(proposal_id);
CREATE INDEX IF NOT EXISTS ix_proposal_exports_proposal ON proposal_exports(proposal_id);
