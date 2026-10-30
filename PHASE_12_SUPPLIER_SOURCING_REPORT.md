# Phase 12 — Supplier Sourcing & Draft PO Checkpoint

Tanggal: 2026-10-27

## Status

**IN PROGRESS — supplier ranking dan workflow draft/approval/queue sudah diimplementasikan lokal; live PO tetap ditahan sampai dependency inventory/BOM/forecast memenuhi gate.**

Implementasi baru:

- `backend/app/services/supplier_sourcing_service.py`
- `backend/app/services/procurement_service.py`
- `GET /api/admin/analytics/supplier-sourcing`
- `POST /api/admin/procurement/drafts`
- `POST /api/admin/procurement/purchase-orders/{po_id}/approve`
- `POST /api/admin/procurement/purchase-orders/{po_id}/send`
- `backend/app/api/routers/supplier.py`
- `supabase/migrations/010_procurement_workflow.sql`
- `backend/tests/test_supplier_sourcing_service.py`, `backend/tests/test_procurement_service.py`
- `frontend/src/services/admin.ts`, `frontend/src/pages/admin/AdminDashboardPage.tsx`,
  `frontend/src/pages/supplier/SupplierPage.tsx`

## Kontrak scoring

Kandidat hanya diranking bila memiliki `supplier_id`, harga per unit, lead
time, dan rating 0–5. Kandidat yang incomplete ditolak; tidak ada nilai
default atau supplier hasil hardcode.

Bobot eksplisit:

- harga: 50%
- lead time: 30%
- rating: 20%

Harga dan lead time dinormalisasi dengan inverse score pada kandidat untuk
bahan yang sama. Tie-breaker deterministik memakai `supplier_id`.

## Workflow PO

1. Sourcing live yang berstatus `OK` diubah menjadi draft per supplier.
2. Draft dipersist atomik dengan `Idempotency-Key`; retry mengembalikan PO yang
   sama, bukan membuat duplikasi.
3. Admin harus memanggil endpoint approval untuk mengubah `DRAFT` menjadi
   `APPROVED`.
4. Endpoint send hanya menerima `APPROVED`, mengubah status menjadi `SENT`,
   dan membuat notification outbox `PENDING` dengan key idempoten.
5. `PENDING` berarti menunggu provider delivery; sistem tidak mengklaim pesan
   sudah terkirim. Supplier hanya melihat PO non-draft milik tenant-nya dan
   responsnya dipetakan ke status schema (`ACCEPTED`, `PARTIAL`, dll.).
6. Admin UI hanya menampilkan tombol approve/queue untuk status yang sesuai;
   portal supplier tidak lagi merender PO/katalog fixture saat API belum
   mengembalikan data.

Jika inventory report bukan `OK`, hasil sourcing tetap
`REQUIRES_VERIFICATION` dengan `draft_po.status=BLOCKED`, sehingga endpoint
persist tidak dapat membuat PO live.

## Evidence lokal

- Ranking, kandidat incomplete, blocked stale/BOM, preview-only, dan invalid
  weight diuji di unit test.
- Builder PO menguji live-only provenance, grouping supplier, MOQ, unit
  mismatch, bounded idempotency key, dan tidak mengarang need-by date.
- Full backend suite: **148 passed**, compile backend berhasil, dan frontend
  production build berhasil (warning bundle >500 kB).
- Langflow quota tidak memengaruhi scoring karena jalur ini deterministik dan
  membaca output inventory backend.

## Open items

- Verifikasi 18 recipe live dan memperoleh forecast paid/non-cancelled yang
  fresh sebelum angka shortage/supplier recommendation muncul.
- Tambahkan supplier performance history (on-time, fill-rate, quality) bila
  memang tersedia secara auditabel; jangan memakai angka UI fixture.
- Terapkan dan verifikasi migration `010_procurement_workflow.sql` pada
  Supabase live sebelum endpoint workflow dipakai.
- Tambahkan provider delivery worker, callback delivery, dan receiving/stock
  transaction; queue saat ini sengaja hanya berstatus `PENDING`.
- Verifikasi 18 recipe live dan memperoleh forecast paid/non-cancelled yang
  fresh sebelum angka shortage/supplier recommendation dan draft PO live
  muncul.
