CREATE TABLE IF NOT EXISTS delivery_projects (
 id UUID PRIMARY KEY, business_id UUID NOT NULL REFERENCES businesses(id), proposal_package_id UUID NULL REFERENCES proposal_packages(id), campaign_id UUID NULL REFERENCES campaigns(id), status VARCHAR(40) NOT NULL, title VARCHAR(300) NOT NULL, summary TEXT NOT NULL DEFAULT '', created_by_operator_id UUID NULL REFERENCES operators(id), created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), closed_at TIMESTAMPTZ NULL
);
CREATE TABLE IF NOT EXISTS delivery_checklist_items (
 id UUID PRIMARY KEY, delivery_project_id UUID NOT NULL REFERENCES delivery_projects(id), category VARCHAR(30) NOT NULL, code VARCHAR(100) NOT NULL, status VARCHAR(30) NOT NULL DEFAULT 'pending', notes TEXT NOT NULL DEFAULT '', updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS delivery_milestones (
 id UUID PRIMARY KEY, delivery_project_id UUID NOT NULL REFERENCES delivery_projects(id), milestone_type VARCHAR(100) NOT NULL, status VARCHAR(30) NOT NULL, operator_id UUID NULL REFERENCES operators(id), note TEXT NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), completed_at TIMESTAMPTZ NULL
);
CREATE TABLE IF NOT EXISTS delivery_approvals (
 id UUID PRIMARY KEY, delivery_project_id UUID NOT NULL REFERENCES delivery_projects(id), approval_type VARCHAR(80) NOT NULL, approved_item TEXT NOT NULL, operator_notes TEXT NOT NULL DEFAULT '', client_assertion TEXT NOT NULL DEFAULT '', artifact_reference TEXT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS delivery_exports (
 id UUID PRIMARY KEY, delivery_project_id UUID NOT NULL REFERENCES delivery_projects(id), status VARCHAR(30) NOT NULL, files JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_delivery_projects_business ON delivery_projects(business_id);
CREATE INDEX IF NOT EXISTS ix_delivery_checklist_project ON delivery_checklist_items(delivery_project_id);
CREATE INDEX IF NOT EXISTS ix_delivery_milestones_project ON delivery_milestones(delivery_project_id);
CREATE INDEX IF NOT EXISTS ix_delivery_approvals_project ON delivery_approvals(delivery_project_id);
CREATE INDEX IF NOT EXISTS ix_delivery_exports_project ON delivery_exports(delivery_project_id);
