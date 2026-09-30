-- First-party operator credentials. Store only versioned salted password hashes.

ALTER TABLE operators ADD COLUMN IF NOT EXISTS username VARCHAR(64);
ALTER TABLE operators ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);
CREATE UNIQUE INDEX IF NOT EXISTS uq_operators_username ON operators (username);
