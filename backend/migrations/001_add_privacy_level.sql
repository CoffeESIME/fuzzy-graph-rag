-- Migration: Add privacy_level column to assets table
-- Date: 2026-01-02
-- Description: Adds privacy governance field to support strict_local and public_cloud data processing

BEGIN;

-- Add privacy_level column with default value
ALTER TABLE assets 
ADD COLUMN privacy_level VARCHAR(20) NOT NULL DEFAULT 'strict_local';

-- Add check constraint to ensure valid values
ALTER TABLE assets
ADD CONSTRAINT privacy_level_check 
CHECK (privacy_level IN ('strict_local', 'public_cloud'));

-- Create index for privacy_level queries
CREATE INDEX idx_assets_privacy_level ON assets(privacy_level);

COMMIT;

-- Verify the change
SELECT column_name, data_type, column_default, is_nullable
FROM information_schema.columns
WHERE table_name = 'assets' AND column_name = 'privacy_level';
