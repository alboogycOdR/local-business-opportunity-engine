ALTER TABLE businesses ADD COLUMN IF NOT EXISTS source_identifier VARCHAR(300);
ALTER TABLE businesses ADD COLUMN IF NOT EXISTS normalized_phone VARCHAR(30);
ALTER TABLE businesses ADD COLUMN IF NOT EXISTS normalized_domain VARCHAR(255);
CREATE INDEX IF NOT EXISTS ix_businesses_source_identifier ON businesses(source_identifier);
CREATE INDEX IF NOT EXISTS ix_businesses_normalized_phone ON businesses(normalized_phone);
CREATE INDEX IF NOT EXISTS ix_businesses_normalized_domain ON businesses(normalized_domain);

CREATE TABLE IF NOT EXISTS dedupe_evidence (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), campaign_id UUID NOT NULL REFERENCES campaigns(id),
  candidate_source VARCHAR(80) NOT NULL, candidate_source_id VARCHAR(300),
  matched_business_id UUID REFERENCES businesses(id), method VARCHAR(50) NOT NULL,
  reason VARCHAR(500) NOT NULL, confidence DOUBLE PRECISION NOT NULL,
  merged BOOLEAN NOT NULL DEFAULT FALSE, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_dedupe_evidence_campaign_id ON dedupe_evidence(campaign_id);
CREATE INDEX IF NOT EXISTS ix_dedupe_evidence_matched_business_id ON dedupe_evidence(matched_business_id);
