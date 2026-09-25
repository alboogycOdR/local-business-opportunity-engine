CREATE TABLE IF NOT EXISTS opportunity_scores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), business_id UUID NOT NULL REFERENCES businesses(id),
  audit_run_id UUID REFERENCES audit_runs(id), version VARCHAR(100) NOT NULL, score INTEGER NOT NULL CHECK(score >= 0 AND score <= 100),
  band VARCHAR(20) NOT NULL, recommended_next_action VARCHAR(50) NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_opportunity_scores_business_id ON opportunity_scores(business_id);
CREATE TABLE IF NOT EXISTS opportunity_components (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), opportunity_score_id UUID NOT NULL REFERENCES opportunity_scores(id),
  code VARCHAR(100) NOT NULL, category VARCHAR(50) NOT NULL, points INTEGER NOT NULL, max_points INTEGER NOT NULL,
  evidence JSONB NOT NULL DEFAULT '{}'::jsonb, source_type VARCHAR(80) NOT NULL, confidence DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_opportunity_components_score_id ON opportunity_components(opportunity_score_id);
CREATE TABLE IF NOT EXISTS opportunity_holds (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), opportunity_score_id UUID NOT NULL REFERENCES opportunity_scores(id),
  code VARCHAR(80) NOT NULL, reason VARCHAR(500) NOT NULL, severity VARCHAR(30) NOT NULL, evidence JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_opportunity_holds_score_id ON opportunity_holds(opportunity_score_id);
