-- Add is_penalty column to profile_metric_settings.
-- On databases that already have this column the runner catches the
-- "duplicate column name" error and marks the migration as applied.
ALTER TABLE profile_metric_settings ADD COLUMN is_penalty BOOLEAN DEFAULT 0;
