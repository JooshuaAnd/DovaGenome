# Phase 7 — Goods receipt, supplier billing, and payable control

Status: **implemented locally; migrations 015/016 pending the Supabase backup gate**.

Implemented:

- Supplier receipt is a separate transaction from PO response. It supports
  partial receipt, canonical ingredient mapping, explicit unit conversion for
  g/kg, stock upsert, positive `RECEIPT` ledger movement, and PO status
  `PARTIAL`/`RECEIVED`.
- Receipt posting is idempotent through `Idempotency-Key`; retries return the
  original receipt and do not add stock twice.
- When the production-ledger migration is live, each receipt line also creates
  a `stock_lots` row with an internal `LOT-...` barcode, supplier, date,
  quantity, unit, and cost. It is an internal lot identity, not a fabricated
  GS1/SKU.
- Supplier invoices support `PAY_ON_DELIVERY` and `WEEKLY_INVOICE`.
- Expected value is calculated from posted goods receipts and the PO unit
  price. A mismatch becomes `REQUIRES_REVIEW`; it is never auto-approved.
- Admin verification moves `SUBMITTED` to `APPROVED`/`REJECTED`. Manual
  payment records support partial payment and final `PAID` state.
- `QR_ILLUSTRATIVE` is only a recorded reference method; no live gateway or
  automatic transfer is claimed.

Main routes:

- `POST /api/supplier/pos/{po_id}/receive`
- `GET|POST /api/supplier/invoices`
- `GET /api/admin/supplier-invoices`
- `POST /api/admin/supplier-invoices/{id}/verify`
- `POST /api/admin/supplier-invoices/{id}/pay`

Migrations:

- `supabase/migrations/015_goods_receipt.sql`
- `supabase/migrations/016_supplier_billing.sql`

The live database currently reports phase extensions pending, so the new write
paths intentionally return a clear unavailable/held response until backup,
apply, and read-only recheck are approved.
