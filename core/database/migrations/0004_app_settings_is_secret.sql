-- Add is_secret column to app_settings.
-- On databases that already have this column the runner catches the
-- "duplicate column name" error and marks the migration as applied.
ALTER TABLE app_settings ADD COLUMN is_secret BOOLEAN DEFAULT 0;
