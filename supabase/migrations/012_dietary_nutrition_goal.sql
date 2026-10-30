-- Store the onboarding goal separately from allergy and preference rules.
ALTER TABLE dietary_passports
    ADD COLUMN IF NOT EXISTS nutrition_goal TEXT NOT NULL DEFAULT '';
