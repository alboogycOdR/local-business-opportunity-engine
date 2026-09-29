-- Indexes declared on the ORM models (and therefore present in every test database created
-- with metadata.create_all) that no earlier migration created. Without them PostgreSQL
-- sequentially scans contacts, suppression_entries, businesses.identity_key/state and others
-- on every per-business lookup in the operator UI, import dedupe, and queue pages.
-- Idempotent: safe to re-run and safe on databases created with create_all.

CREATE INDEX IF NOT EXISTS ix_businesses_identity_key ON businesses (identity_key);
CREATE INDEX IF NOT EXISTS ix_businesses_state ON businesses (state);
CREATE INDEX IF NOT EXISTS ix_business_aliases_business_id ON business_aliases (business_id);
CREATE INDEX IF NOT EXISTS ix_contacts_business_id ON contacts (business_id);
CREATE INDEX IF NOT EXISTS ix_suppression_entries_business_id ON suppression_entries (business_id);
CREATE INDEX IF NOT EXISTS ix_audit_runs_status ON audit_runs (status);
CREATE INDEX IF NOT EXISTS ix_audit_runs_website_id ON audit_runs (website_id);
CREATE INDEX IF NOT EXISTS ix_opportunity_scores_audit_run_id ON opportunity_scores (audit_run_id);
CREATE INDEX IF NOT EXISTS ix_business_briefs_audit_run_id ON business_briefs (audit_run_id);
CREATE INDEX IF NOT EXISTS ix_business_briefs_score_id ON business_briefs (score_id);
CREATE INDEX IF NOT EXISTS ix_generated_demos_audit_run_id ON generated_demos (audit_run_id);
CREATE INDEX IF NOT EXISTS ix_generated_demos_score_id ON generated_demos (score_id);
CREATE INDEX IF NOT EXISTS ix_generated_demos_status ON generated_demos (status);
CREATE INDEX IF NOT EXISTS ix_outreach_draft_packages_brief_id ON outreach_draft_packages (brief_id);
CREATE INDEX IF NOT EXISTS ix_outreach_draft_packages_score_id ON outreach_draft_packages (score_id);
CREATE INDEX IF NOT EXISTS ix_outreach_draft_packages_status ON outreach_draft_packages (status);
CREATE INDEX IF NOT EXISTS ix_outreach_channel_approvals_outreach_draft_message_id ON outreach_channel_approvals (outreach_draft_message_id);
CREATE INDEX IF NOT EXISTS ix_proposal_packages_status ON proposal_packages (status);
CREATE INDEX IF NOT EXISTS ix_proposal_assumptions_proposal_id ON proposal_assumptions (proposal_id);
CREATE INDEX IF NOT EXISTS ix_delivery_projects_status ON delivery_projects (status);
CREATE INDEX IF NOT EXISTS ix_operator_comments_operator_id ON operator_comments (operator_id);
CREATE INDEX IF NOT EXISTS ix_demo_preview_links_business_id ON demo_preview_links (business_id);
