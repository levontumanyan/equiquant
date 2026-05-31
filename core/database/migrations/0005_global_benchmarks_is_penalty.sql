-- Add is_penalty column to global_benchmarks.
-- On databases that already have this column the runner catches the
-- "duplicate column name" error and marks the migration as applied.
ALTER TABLE global_benchmarks ADD COLUMN is_penalty BOOLEAN DEFAULT 0;
