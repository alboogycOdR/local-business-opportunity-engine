-- Sprint 1 schema. Apply with PostgreSQL (psql) or via the migration runner.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS campaigns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), name VARCHAR(200) NOT NULL,
  vertical VARCHAR(100) NOT NULL, geography VARCHAR(200), policy JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS businesses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), campaign_id UUID NOT NULL REFERENCES campaigns(id),
  display_name VARCHAR(200) NOT NULL, category VARCHAR(100), locality VARCHAR(200), address_text TEXT,
  identity_key VARCHAR(300) NOT NULL, state VARCHAR(40) NOT NULL DEFAULT 'DISCOVERED',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_business_campaign_identity UNIQUE (campaign_id, identity_key)
);
CREATE TABLE IF NOT EXISTS business_aliases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), business_id UUID NOT NULL REFERENCES businesses(id), alias VARCHAR(300) NOT NULL
);
CREATE TABLE IF NOT EXISTS source_observations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), business_id UUID NOT NULL REFERENCES businesses(id), field VARCHAR(200) NOT NULL,
  source_type VARCHAR(80) NOT NULL, source_ref VARCHAR(500), observed_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ, storage_policy VARCHAR(30) NOT NULL CHECK(storage_policy IN ('persistent','ephemeral','reference_only')),
  confidence DOUBLE PRECISION NOT NULL CHECK(confidence >= 0 AND confidence <= 1), value TEXT
);
CREATE TABLE IF NOT EXISTS contacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), business_id UUID NOT NULL REFERENCES businesses(id), channel VARCHAR(30) NOT NULL,
  value VARCHAR(500) NOT NULL, source_observation_id UUID REFERENCES source_observations(id)
);
CREATE TABLE IF NOT EXISTS suppression_entries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), business_id UUID NOT NULL REFERENCES businesses(id), reason VARCHAR(500) NOT NULL,
  channel VARCHAR(30), created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS pipeline_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), business_id UUID NOT NULL REFERENCES businesses(id), from_state VARCHAR(40),
  to_state VARCHAR(40) NOT NULL, actor VARCHAR(100) NOT NULL DEFAULT 'system', reason TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), idempotency_key VARCHAR(300) NOT NULL UNIQUE, job_type VARCHAR(100) NOT NULL,
  status VARCHAR(30) NOT NULL DEFAULT 'queued', payload JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_businesses_campaign_id ON businesses(campaign_id);
CREATE INDEX IF NOT EXISTS ix_source_observations_business_id ON source_observations(business_id);
CREATE INDEX IF NOT EXISTS ix_pipeline_events_business_id ON pipeline_events(business_id);
