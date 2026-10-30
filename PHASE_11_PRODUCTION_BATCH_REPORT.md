# Phase 11 — Production batch & weigh ledger

Status: **implemented locally; Supabase migration pending**.

Implemented:

- `production_batches` stores service date, meal slot, site, verified recipe,
  planned portions, and operational status.
- `production_batch_requirements` explodes a verified recipe BOM into planned
  ingredient quantities.
- `weigh_events` is an idempotent audit record for each manual net-weight
  entry. Duplicate retries return the original event instead of deducting stock
  twice.
- The same transaction updates `inventory_stocks`, inserts a negative
  `inventory_movements` row, updates issued/variance quantities, and moves the
  batch to `IN_PROGRESS`.
- Only `g`/`kg` recipe units are accepted by the first weighing contract. No
  unit is silently guessed.
- Bluetooth is intentionally not active yet. The API accepts only
  `scale_source=manual`; a future adapter will submit the same validated
  contract.

API:

- `GET /api/kitchen/production-batches`
- `POST /api/kitchen/production-batches`
- `POST /api/kitchen/production-batches/plan-from-paid-orders` aggregates
  paid/non-cancelled order quantities per service date and meal slot, uses the
  latest recipe `VERIFIED`, and holds all writes when any menu is unresolved.
- `POST /api/kitchen/production-batches/{batch_id}/weigh`
- `POST /api/kitchen/production-batches/{batch_id}/complete`

The PAID-demand planner treats legacy `order_items` without `meal_slot` as
lunch only; it never reinterprets those rows as breakfast or dinner. New
orders are separated by meal slot before the recipe verification gate.

Migration `014_production_batch_weigh_ledger.sql` is rerunnable but has not
been applied automatically. Apply it only after the Supabase backup/restore
gate; until then the existing inventory screen remains usable and the batch
screen states that the migration is pending.

Completion now requires every planned requirement to have at least one issued
weigh event, then changes the batch to `COMPLETED` in an audited transaction.

Evidence:

- isolated acceptance scenario: `backend/scripts/run_phase_acceptance_demo.py`
- backend test suite: 222 passed
- backend compile: passed
- frontend production build: passed

