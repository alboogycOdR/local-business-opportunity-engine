CREATE TABLE IF NOT EXISTS business_briefs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), business_id UUID NOT NULL REFERENCES businesses(id),
  score_id UUID REFERENCES opportunity_scores(id), audit_run_id UUID REFERENCES audit_runs(id),
  version VARCHAR(100) NOT NULL, summary TEXT NOT NULL, recommended_next_action VARCHAR(50) NOT NULL,
  confidence DOUBLE PRECISION NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_business_briefs_business_id ON business_briefs(business_id);
CREATE TABLE IF NOT EXISTS business_brief_facts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), business_brief_id UUID NOT NULL REFERENCES business_briefs(id),
  fact_type VARCHAR(50) NOT NULL, label VARCHAR(200) NOT NULL, value JSONB,
  source_type VARCHAR(80) NOT NULL, evidence JSONB NOT NULL DEFAULT '{}'::jsonb, confidence DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_business_brief_facts_brief_id ON business_brief_facts(business_brief_id);
CREATE TABLE IF NOT EXISTS business_brief_opportunities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), business_brief_id UUID NOT NULL REFERENCES business_briefs(id),
  code VARCHAR(100) NOT NULL, title VARCHAR(200) NOT NULL, description TEXT NOT NULL,
  priority VARCHAR(30) NOT NULL, evidence JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_business_brief_opportunities_brief_id ON business_brief_opportunities(business_brief_id);
CREATE TABLE IF NOT EXISTS business_brief_risks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), business_brief_id UUID NOT NULL REFERENCES business_briefs(id),
  code VARCHAR(100) NOT NULL, title VARCHAR(200) NOT NULL, description TEXT NOT NULL,
  severity VARCHAR(30) NOT NULL, evidence JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_business_brief_risks_brief_id ON business_brief_risks(business_brief_id);
