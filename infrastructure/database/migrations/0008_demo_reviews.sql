CREATE TABLE IF NOT EXISTS demo_reviews (
    id UUID PRIMARY KEY,
    demo_id UUID NOT NULL REFERENCES generated_demos(id),
    business_id UUID NOT NULL REFERENCES businesses(id),
    decision VARCHAR(40) NOT NULL,
    reviewer VARCHAR(200) NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resulting_demo_status VARCHAR(40) NOT NULL,
    resulting_business_state VARCHAR(40) NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_demo_reviews_demo_id ON demo_reviews(demo_id);
CREATE INDEX IF NOT EXISTS ix_demo_reviews_business_id ON demo_reviews(business_id);

CREATE TABLE IF NOT EXISTS demo_review_checklist_items (
    id UUID PRIMARY KEY,
    demo_review_id UUID NOT NULL REFERENCES demo_reviews(id),
    code VARCHAR(100) NOT NULL,
    label VARCHAR(300) NOT NULL,
    passed BOOLEAN NOT NULL DEFAULT false,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS ix_demo_review_checklist_items_review_id ON demo_review_checklist_items(demo_review_id);
