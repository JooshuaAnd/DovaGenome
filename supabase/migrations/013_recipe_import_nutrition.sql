-- Phase 2: document import provenance and deterministic nutrition evidence.
-- Apply only after the database backup/restore gate.

CREATE TABLE IF NOT EXISTS recipe_import_jobs (
    import_job_id TEXT PRIMARY KEY DEFAULT 'recipe_import_' || gen_random_uuid()::TEXT,
    recipe_version_id TEXT NOT NULL REFERENCES recipe_versions(recipe_version_id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN ('pdf','xlsx','csv','txt','md')),
    sha256 TEXT NOT NULL,
    byte_size INTEGER NOT NULL CHECK (byte_size > 0),
    extracted_text TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'EXTRACTED'
        CHECK (status IN ('RECEIVED','EXTRACTED','DRAFT_READY','FAILED')),
    created_by TEXT NOT NULL REFERENCES customers(customer_id),
    error_message TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_recipe_import_jobs_recipe
    ON recipe_import_jobs (recipe_version_id, created_at DESC);

ALTER TABLE ingredients
    ADD COLUMN IF NOT EXISTS calories_kcal_100g NUMERIC(12, 4),
    ADD COLUMN IF NOT EXISTS protein_g_100g NUMERIC(12, 4),
    ADD COLUMN IF NOT EXISTS carbs_g_100g NUMERIC(12, 4),
    ADD COLUMN IF NOT EXISTS fat_g_100g NUMERIC(12, 4),
    ADD COLUMN IF NOT EXISTS composition_basis TEXT NOT NULL DEFAULT 'unknown',
    ADD COLUMN IF NOT EXISTS composition_source TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS composition_evidence JSONB NOT NULL DEFAULT '{}'::JSONB;

ALTER TABLE recipe_versions
    ADD COLUMN IF NOT EXISTS nutrition_status TEXT NOT NULL DEFAULT 'UNAVAILABLE',
    ADD COLUMN IF NOT EXISTS nutrition_basis TEXT NOT NULL DEFAULT 'unknown',
    ADD COLUMN IF NOT EXISTS calories_kcal NUMERIC(12, 4),
    ADD COLUMN IF NOT EXISTS protein_g NUMERIC(12, 4),
    ADD COLUMN IF NOT EXISTS carbs_g NUMERIC(12, 4),
    ADD COLUMN IF NOT EXISTS fat_g NUMERIC(12, 4),
    ADD COLUMN IF NOT EXISTS macro_energy_pct JSONB NOT NULL DEFAULT '{}'::JSONB,
    ADD COLUMN IF NOT EXISTS nutrition_warnings JSONB NOT NULL DEFAULT '[]'::JSONB;

ALTER TABLE recipe_import_jobs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "deny_public_recipe_import_jobs" ON recipe_import_jobs;
CREATE POLICY "deny_public_recipe_import_jobs"
    ON recipe_import_jobs FOR ALL TO anon, authenticated USING (false);
