# DovaGenome Database Recovery and Baseline Plan

Status: **Phase 0 plan only — not executed**  
Tanggal: 2026-10-30

## Current evidence

The current health probe reports PostgreSQL/Supabase connected, migration status
verified, and Astra `OFFLINE_LEGACY`. This establishes the active application
source path, but it does not establish a verified backup or restore point.

The repository contains the original schema migrations `001`–`004` and later working-tree migrations `005`–`012` for recipe provenance, payment/KDS, quantity, marketing, procurement, and dietary/nutrition extensions. Their presence in the repository is not evidence that every migration is applied to the connected database.

The `.env` file contains credentials and is intentionally excluded from this plan. No secret values are copied into repository documents, logs, tests, or prompts.

## Required pre-migration gates

1. Identify the exact database target used by the running backend without printing DSNs or passwords.
2. Export schema metadata and migration/version state read-only.
3. Create an encrypted, access-controlled backup of the current PostgreSQL/Supabase database and verify its checksum.
4. Restore that backup into an isolated staging database and run application health plus read-only row-count checks.
5. Reconcile Astra vs PostgreSQL ownership for customers, menus, dietary profiles, and orders. Do not migrate or delete either source based only on connection status.
6. Record a rollback owner, restore time objective, and an explicit approval before applying any new migration to a shared/production target.

## Recommended source-of-truth decision

Keep PostgreSQL/Supabase as the intended ERP system of record because the current backend repositories, recipe provenance, payment boundary, inventory ledger, supplier sourcing, and PO workflow are implemented around it. Treat Astra as legacy/read-only during reconciliation. Do not migrate to MySQL merely because a local Laragon process exists. Do not remove Astra until parity and historical data reconciliation are evidenced.

## Staged migration order after approval

1. Apply/verify core provenance and ledger prerequisites.
2. Apply/verify payment and kitchen-ticket constraints.
3. Apply/verify order quantity and meal-slot/batch extensions after a schema design review.
4. Apply/verify procurement, billing, and notification changes.
5. Run invariant checks: foreign keys, unique idempotency keys, non-negative quantities where required, verified recipe gates, payment-to-kitchen release, stock ledger reconciliation, and role visibility.
6. Only then enable scheduled alerts, supplier sending, or delivery workflows.

## Backup and restore evidence to collect

- Backup identifier, creation timestamp, target environment, schema version, and checksum.
- Restore target identifier and restore completion timestamp.
- Row counts for customers, menus, recipe versions/components, orders/order items, payments, inventory movements/reservations, suppliers, purchase orders/items, invoices, and notification outbox.
- Migration status for each file and any skipped/failed migration.
- Redacted health output and test report; never include credentials or personal dietary data.

## Rollback boundaries

Database writes involving orders, payment events, stock movements, receipts, PO approval, supplier invoices, and delivery statuses must not be undone by ad-hoc row edits. Rollback uses a planned migration rollback or restore procedure with an incident/audit record. Operational transactions should be corrected with compensating ledger events and idempotency keys.

## Blocking unknowns

- No verified backup/restore evidence is in the repository.
- No trusted migration table/status report for the currently connected database is in the health response.
- Astra and PostgreSQL both appear connected; ownership and synchronization are not yet proven.
- Langflow vector references require schema/RPC confirmation before RAG can be called live.

These unknowns block production schema changes but do not block a read-only Phase 1 connectivity audit.

## Phase 1 correction — 2026-10-30

The active application path is now explicit: Supabase/PostgreSQL is the sole
runtime source of truth and Astra is `OFFLINE_LEGACY`. The health endpoint
performs a read-only migration check and does not perform a migration, data
copy, deletion, or backup/restore operation. The encrypted backup and isolated
restore drill remain mandatory before any shared or production schema change.
