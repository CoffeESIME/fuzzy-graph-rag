-- Migration: Fix privacy_level constraint to accept uppercase values
-- Date: 2026-01-02
-- Description: Updates constraint to accept enum names (uppercase) instead of values (lowercase)

BEGIN;

-- Drop old constraint
ALTER TABLE assets DROP CONSTRAINT IF EXISTS privacy_level_check;

-- Add new constraint with uppercase values
ALTER TABLE assets
ADD CONSTRAINT privacy_level_check 
CHECK (privacy_level IN ('STRICT_LOCAL', 'PUBLIC_CLOUD', 'strict_local', 'public_cloud'));

COMMIT;

-- Verify
SELECT constraint_name, check_clause
FROM information_schema.check_constraints
WHERE constraint_name = 'privacy_level_check';
