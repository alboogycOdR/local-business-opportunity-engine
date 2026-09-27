CREATE TABLE IF NOT EXISTS pilot_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), campaign_id UUID NOT NULL REFERENCES campaigns(id),
    name TEXT NOT NULL, vertical TEXT NOT NULL, geography TEXT NOT NULL, target_lead_count INTEGER NOT NULL,
    mode VARCHAR(20) NOT NULL, status VARCHAR(20) NOT NULL, source_policy_version VARCHAR(80) NOT NULL,
    default_preview_expiry_days INTEGER NOT NULL, max_businesses INTEGER NOT NULL, daily_demo_cap INTEGER NOT NULL,
    daily_preview_link_cap INTEGER NOT NULL, daily_manual_contact_cap INTEGER NOT NULL,
    daily_readiness_approval_cap INTEGER NOT NULL, created_by_operator_id UUID REFERENCES operators(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    activated_at TIMESTAMPTZ, closed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_pilot_runs_campaign_id ON pilot_runs(campaign_id);
CREATE INDEX IF NOT EXISTS ix_pilot_runs_status ON pilot_runs(status);
CREATE TABLE IF NOT EXISTS pilot_source_policy_acknowledgements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), pilot_id UUID NOT NULL REFERENCES pilot_runs(id),
    operator_id UUID REFERENCES operators(id), policy_version VARCHAR(80) NOT NULL,
    acknowledged_at TIMESTAMPTZ NOT NULL DEFAULT now(), acknowledgement_text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_pilot_policy_ack_pilot_id ON pilot_source_policy_acknowledgements(pilot_id);
CREATE TABLE IF NOT EXISTS pilot_retrospectives (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), pilot_id UUID NOT NULL REFERENCES pilot_runs(id),
    created_by_operator_id UUID REFERENCES operators(id), what_worked TEXT NOT NULL DEFAULT '',
    what_failed TEXT NOT NULL DEFAULT '', false_positives TEXT NOT NULL DEFAULT '', false_negatives TEXT NOT NULL DEFAULT '',
    operator_friction TEXT NOT NULL DEFAULT '', demo_quality_issues TEXT NOT NULL DEFAULT '', source_quality_issues TEXT NOT NULL DEFAULT '',
    business_objections TEXT NOT NULL DEFAULT '', reply_quality TEXT NOT NULL DEFAULT '', meeting_quality TEXT NOT NULL DEFAULT '',
    next_sprint_recommendation TEXT NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_pilot_retrospectives_pilot_id ON pilot_retrospectives(pilot_id);
CREATE TABLE IF NOT EXISTS pilot_export_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), pilot_id UUID NOT NULL REFERENCES pilot_runs(id),
    status VARCHAR(30) NOT NULL, export_root TEXT NOT NULL, files JSONB NOT NULL DEFAULT '{}'::jsonb,
    warnings JSONB NOT NULL DEFAULT '[]'::jsonb, created_by_operator_id UUID REFERENCES operators(id), created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_pilot_export_runs_pilot_id ON pilot_export_runs(pilot_id);
