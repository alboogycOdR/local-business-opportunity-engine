CREATE TABLE IF NOT EXISTS operators (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name VARCHAR(200) NOT NULL,
    email VARCHAR(320),
    role VARCHAR(30) NOT NULL DEFAULT 'operator',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS operator_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    operator_id UUID NOT NULL REFERENCES operators(id),
    assigned_by_operator_id UUID REFERENCES operators(id),
    status VARCHAR(30) NOT NULL DEFAULT 'assigned',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_operator_assignments_business_id ON operator_assignments(business_id);
CREATE INDEX IF NOT EXISTS ix_operator_assignments_operator_id ON operator_assignments(operator_id);
CREATE TABLE IF NOT EXISTS operator_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    operator_id UUID NOT NULL REFERENCES operators(id),
    comment_type VARCHAR(30) NOT NULL DEFAULT 'general',
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_operator_comments_business_id ON operator_comments(business_id);
CREATE TABLE IF NOT EXISTS operator_audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID REFERENCES operators(id),
    business_id UUID REFERENCES businesses(id),
    entity_type VARCHAR(80) NOT NULL,
    entity_id UUID,
    action VARCHAR(100) NOT NULL,
    before_data JSONB,
    after_data JSONB,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_operator_audit_events_business_id ON operator_audit_events(business_id);
CREATE TABLE IF NOT EXISTS demo_preview_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    demo_id UUID NOT NULL REFERENCES generated_demos(id),
    business_id UUID NOT NULL REFERENCES businesses(id),
    token_hash VARCHAR(128) NOT NULL UNIQUE,
    label VARCHAR(200) NOT NULL DEFAULT 'Concept preview',
    permission VARCHAR(30) NOT NULL DEFAULT 'external_view',
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    expires_at TIMESTAMPTZ,
    created_by_operator_id UUID REFERENCES operators(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_demo_preview_links_demo_id ON demo_preview_links(demo_id);
CREATE TABLE IF NOT EXISTS demo_preview_access_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    preview_link_id UUID NOT NULL REFERENCES demo_preview_links(id),
    accessed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ip_hash VARCHAR(128),
    user_agent_hash VARCHAR(128),
    outcome VARCHAR(40) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_demo_preview_access_events_link_id ON demo_preview_access_events(preview_link_id);
