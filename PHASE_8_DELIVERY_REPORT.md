# Phase 8 — Status-based delivery dispatch

Status: **implemented locally; migration 017 pending the Supabase backup gate**.

Implemented:

- Admin can create a delivery stop only from a paid, non-cancelled order and
  assign it to an active `courier` account.
- Courier status transitions are explicit:
  `PLANNED → ASSIGNED → PICKED_UP → OUT_FOR_DELIVERY → DELIVERED`.
  Failed deliveries can be reassigned through the controlled transition.
- Every status event has an idempotency key, actor, note, and proof reference.
- Customer tracking is scoped to the customer’s own order; supplier data and
  other customer addresses are not exposed.
- The UI displays delivery status when live stops exist. No fake GPS position
  or provider delivery success is shown.

Main routes:

- `GET /api/admin/delivery/stops`
- `POST /api/admin/delivery/stops`
- `POST /api/admin/delivery/stops/{id}/assign`
- `GET /api/delivery/stops`
- `PATCH /api/delivery/stops/{id}/status`
- `GET /api/orders/{order_id}/delivery`

Migration: `supabase/migrations/017_delivery_dispatch.sql`.

The role constraint and stop/event tables are not applied automatically. The
current live health response therefore remains honest about pending phase
extensions.
