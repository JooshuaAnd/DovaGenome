-- ============================================================================
-- DovaGenome — Phase 2: legacy recipe verification bootstrap
--
-- Existing menu_ingredients rows are evidence to review, not proof of safety.
-- This migration creates PENDING_VERIFICATION recipe versions and preserves
-- missing quantity/unit as unknown instead of inventing gramasi.
-- ============================================================================

ALTER TABLE recipe_components
    ALTER COLUMN quantity DROP NOT NULL;

ALTER TABLE recipe_components
    DROP CONSTRAINT IF EXISTS recipe_components_quantity_check;

ALTER TABLE recipe_components
    ADD CONSTRAINT recipe_components_quantity_check
    CHECK (quantity IS NULL OR quantity > 0);

ALTER TABLE recipe_components
    ALTER COLUMN unit SET DEFAULT 'UNKNOWN';

ALTER TABLE ingredients
    ADD COLUMN IF NOT EXISTS allergen_codes TEXT[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS allergen_evidence JSONB NOT NULL DEFAULT '{}'::JSONB,
    ADD COLUMN IF NOT EXISTS verified_by TEXT REFERENCES customers(customer_id),
    ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS uq_recipe_component_identity
    ON recipe_components (recipe_version_id, ingredient_id, sort_order)
    WHERE ingredient_id IS NOT NULL;

INSERT INTO recipe_versions (
    menu_id, version_no, status, source, source_ref, notes
)
SELECT
    m.menu_id,
    1,
    'PENDING_VERIFICATION',
    'legacy_menu_ingredients',
    'migration_006',
    'Imported from legacy menu_ingredients; quantity, unit, allergen mapping, and cross-contact require operator verification.'
FROM menus m
ON CONFLICT (menu_id, version_no) DO NOTHING;

INSERT INTO recipe_components (
    recipe_version_id, ingredient_id, quantity, unit, preparation,
    verification_status, source, sort_order
)
SELECT
    rv.recipe_version_id,
    mi.ingredient_id,
    NULL,
    'UNKNOWN',
    '',
    'UNVERIFIED',
    'legacy_menu_ingredients',
    mi.sort_order
FROM menu_ingredients mi
JOIN recipe_versions rv
  ON rv.menu_id = mi.menu_id
 AND rv.version_no = 1
WHERE mi.ingredient_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM recipe_components existing
      WHERE existing.recipe_version_id = rv.recipe_version_id
        AND existing.ingredient_id = mi.ingredient_id
        AND existing.sort_order = mi.sort_order
  );

CREATE INDEX IF NOT EXISTS idx_ingredients_allergen_codes
    ON ingredients USING GIN (allergen_codes);
