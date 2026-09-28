CREATE TABLE IF NOT EXISTS enrichment_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), business_id UUID NOT NULL REFERENCES businesses(id),
    source_type VARCHAR(80) NOT NULL, status VARCHAR(40) NOT NULL, adapter_version VARCHAR(100) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(), completed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_enrichment_runs_business_id ON enrichment_runs(business_id);
CREATE TABLE IF NOT EXISTS enrichment_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), enrichment_run_id UUID NOT NULL REFERENCES enrichment_runs(id),
    business_id UUID NOT NULL REFERENCES businesses(id), source_type VARCHAR(80) NOT NULL,
    source_url TEXT, fact_type VARCHAR(100) NOT NULL, value TEXT NOT NULL, confidence DOUBLE PRECISION NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL, evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    policy VARCHAR(40) NOT NULL DEFAULT 'persistent'
);
CREATE INDEX IF NOT EXISTS ix_enrichment_facts_business_id ON enrichment_facts(business_id);
CREATE INDEX IF NOT EXISTS ix_enrichment_facts_run_id ON enrichment_facts(enrichment_run_id);
