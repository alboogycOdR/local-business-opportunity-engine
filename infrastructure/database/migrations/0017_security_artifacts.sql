CREATE TABLE IF NOT EXISTS operator_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), operator_id UUID REFERENCES operators(id),
    session_hash VARCHAR(128) NOT NULL, csrf_hash VARCHAR(128) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), expires_at TIMESTAMPTZ NOT NULL, revoked_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_operator_sessions_hash ON operator_sessions(session_hash);
