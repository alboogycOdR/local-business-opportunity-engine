CREATE TABLE IF NOT EXISTS websites (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), business_id UUID NOT NULL REFERENCES businesses(id),
  discovered_url VARCHAR(1000) NOT NULL, normalized_url VARCHAR(1000), final_url VARCHAR(1000),
  http_status INTEGER, resolution_status VARCHAR(40) NOT NULL, checked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_websites_business_id ON websites(business_id);
CREATE TABLE IF NOT EXISTS audit_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), business_id UUID NOT NULL REFERENCES businesses(id),
  website_id UUID REFERENCES websites(id), auditor_version VARCHAR(100) NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(), completed_at TIMESTAMPTZ,
  status VARCHAR(30) NOT NULL DEFAULT 'running', error_summary TEXT, technical_metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_audit_runs_business_id ON audit_runs(business_id);
CREATE TABLE IF NOT EXISTS audit_findings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), audit_run_id UUID NOT NULL REFERENCES audit_runs(id),
  code VARCHAR(100) NOT NULL, category VARCHAR(50) NOT NULL, severity VARCHAR(30) NOT NULL,
  deterministic BOOLEAN NOT NULL DEFAULT true, status VARCHAR(40) NOT NULL, observed_value JSONB,
  evidence JSONB NOT NULL DEFAULT '{}'::jsonb, source_url VARCHAR(1000), confidence DOUBLE PRECISION NOT NULL,
  observed_at TIMESTAMPTZ NOT NULL, auditor_version VARCHAR(100) NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_audit_findings_run_id ON audit_findings(audit_run_id);
CREATE TABLE IF NOT EXISTS audit_artifacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), audit_run_id UUID NOT NULL REFERENCES audit_runs(id),
  kind VARCHAR(50) NOT NULL, path VARCHAR(1000) NOT NULL, mime_type VARCHAR(100) NOT NULL,
  byte_size BIGINT, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_audit_artifacts_run_id ON audit_artifacts(audit_run_id);
