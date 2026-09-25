CREATE TABLE IF NOT EXISTS generated_demos (
    id UUID PRIMARY KEY,
    business_id UUID NOT NULL REFERENCES businesses(id),
    brief_id UUID NOT NULL REFERENCES business_briefs(id),
    score_id UUID REFERENCES opportunity_scores(id),
    audit_run_id UUID REFERENCES audit_runs(id),
    version VARCHAR(100) NOT NULL,
    demo_type VARCHAR(50) NOT NULL,
    status VARCHAR(30) NOT NULL,
    preview_path VARCHAR(1000) NOT NULL,
    preview_url VARCHAR(1000),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_generated_demos_business_id ON generated_demos(business_id);
CREATE INDEX IF NOT EXISTS ix_generated_demos_brief_id ON generated_demos(brief_id);

CREATE TABLE IF NOT EXISTS generated_demo_sections (
    id UUID PRIMARY KEY,
    demo_id UUID NOT NULL REFERENCES generated_demos(id),
    section_type VARCHAR(50) NOT NULL,
    heading VARCHAR(300) NOT NULL,
    body TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_generated_demo_sections_demo_id ON generated_demo_sections(demo_id);

CREATE TABLE IF NOT EXISTS generated_demo_claims (
    id UUID PRIMARY KEY,
    demo_id UUID NOT NULL REFERENCES generated_demos(id),
    claim_text TEXT NOT NULL,
    claim_type VARCHAR(50) NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence DOUBLE PRECISION NOT NULL,
    approved BOOLEAN NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS ix_generated_demo_claims_demo_id ON generated_demo_claims(demo_id);

CREATE TABLE IF NOT EXISTS demo_artifacts (
    id UUID PRIMARY KEY,
    demo_id UUID NOT NULL REFERENCES generated_demos(id),
    kind VARCHAR(50) NOT NULL,
    path VARCHAR(1000) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    byte_size INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_demo_artifacts_demo_id ON demo_artifacts(demo_id);

CREATE TABLE IF NOT EXISTS demo_qa_runs (
    id UUID PRIMARY KEY,
    demo_id UUID NOT NULL REFERENCES generated_demos(id),
    status VARCHAR(30) NOT NULL,
    checks JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_demo_qa_runs_demo_id ON demo_qa_runs(demo_id);
