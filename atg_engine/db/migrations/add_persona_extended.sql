-- Add persona_extended column to personas (PostgreSQL).
-- Run this in Supabase SQL Editor or psql if the column is missing after deployment.
-- Idempotent: safe to run multiple times.

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'personas' AND column_name = 'persona_extended'
  ) THEN
    ALTER TABLE personas ADD COLUMN persona_extended TEXT;
  END IF;
END $$;
