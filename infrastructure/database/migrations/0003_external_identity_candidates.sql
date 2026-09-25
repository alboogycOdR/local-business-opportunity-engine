CREATE TABLE IF NOT EXISTS business_external_identities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), business_id UUID NOT NULL REFERENCES businesses(id),
  source VARCHAR(80) NOT NULL, source_id VARCHAR(300) NOT NULL, observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  confidence DOUBLE PRECISION NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
  CONSTRAINT uq_external_identity_source_id UNIQUE (source, source_id)
);
CREATE INDEX IF NOT EXISTS ix_external_identity_business_id ON business_external_identities(business_id);

CREATE TABLE IF NOT EXISTS discovery_candidates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), campaign_id UUID NOT NULL REFERENCES campaigns(id),
  source VARCHAR(80) NOT NULL, source_id VARCHAR(300), status VARCHAR(30) NOT NULL DEFAULT 'ambiguous',
  normalized_payload JSONB NOT NULL DEFAULT '{}'::jsonb, provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  dedupe_evidence JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_discovery_candidates_campaign_id ON discovery_candidates(campaign_id);
CREATE INDEX IF NOT EXISTS ix_discovery_candidates_status ON discovery_candidates(status);
CREATE INDEX IF NOT EXISTS ix_discovery_candidates_source_id ON discovery_candidates(source_id);

ALTER TABLE dedupe_evidence ADD COLUMN IF NOT EXISTS discovery_candidate_id UUID REFERENCES discovery_candidates(id);
CREATE INDEX IF NOT EXISTS ix_dedupe_evidence_candidate_id ON dedupe_evidence(discovery_candidate_id);

-- Safe migration of the Sprint 2 legacy field. New code uses the external
-- identity table; malformed/empty legacy values remain untouched for review.
INSERT INTO business_external_identities (business_id, source, source_id, confidence)
SELECT b.id, split_part(b.source_identifier, ':', 1), split_part(b.source_identifier, ':', 2), 0.8
FROM businesses b
WHERE b.source_identifier IS NOT NULL
  AND position(':' in b.source_identifier) > 0
ON CONFLICT (source, source_id) DO NOTHING;
