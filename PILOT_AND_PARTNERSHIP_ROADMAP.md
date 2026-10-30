# Pilot and Partnership Roadmap — DovaGenome

Status: **roadmap perencanaan; tidak menyatakan survei, kontrak, afiliasi, atau endorsement yang sudah terjadi.**

## 1. Positioning pilot

DovaGenome diuji pertama sebagai platform precision catering untuk satu operator Dova Kitchen dan satu segmen katering dengan kebutuhan diet/alergi khusus. Positioning utama adalah **traceable dietary safety dan operational control**. Forecast, procurement, CRM, dan AI adalah nilai tambahan yang harus dibuktikan setelah safety core stabil.

## 2. Roadmap adopsi

| Tahap | Fokus | Bukti minimum sebelum lanjut |
|---|---|---|
| P0 — Internal readiness | Source-of-truth, role, recipe fixture, guard, payment simulation | Traceability, architecture gap report, baseline test inventory |
| P1 — Controlled demo | Satu customer allergy scenario dan satu paid-order-to-PO scenario | Blocked order ditolak, kitchen ticket hanya paid, draft PO persistent dan approval tercatat |
| P2 — Design partner terbatas | Operator dapur/admin dan supplier yang setuju mencoba sandbox | Feedback terstruktur, data provenance, incident log, usability observations |
| P3 — Limited pilot | Transaksi nyata yang consented pada satu segmen | Safety incidents, adoption, processing time, reorder/stock metrics dengan definisi jelas |
| P4 — Expansion decision | Evaluasi apakah use case diperluas ke segmen F&B lain | Evidence matrix, economics sensitivity, security review, operational owner approval |

## 3. Stakeholder and role boundary

- Customer: mengelola passport dan order miliknya.
- Admin/operasional: mengelola katalog, recipe approval, payment review bila diperlukan, PO approval, campaign approval, dan audit.
- Kitchen: membaca paid kitchen ticket, melakukan produksi/receiving sesuai hak akses, tidak mengedit/approve recipe sendiri tanpa otorisasi.
- Supplier: melihat PO/katalog/performa miliknya saja; tidak melihat passport atau PII customer.

## 4. Pembeda terhadap POS ingredient tracking

| Potential differentiator | Yang sudah terlihat | Yang wajib dibuktikan dalam MVP |
|---|---|---|
| Dietary Passport → menu decision | Passport dan safety service ada | Decision API yang sama di web, Telegram, cart, checkout, order, kitchen; recipe evidence dapat diaudit. |
| LLM with deterministic safety boundary | AI/Langflow export dan backend menu suggestion ada | LLM tidak dapat override blocked/requires verification; structured output dan adversarial tests. |
| Order → procurement loop | PO schema dan supply-chain forecast ada | Paid order → BOM → inventory → persistent draft PO → admin approval → supplier response. |
| Recipe verification lifecycle | Belum tersedia secara lengkap | UI edit/approve terpisah, versioning, evidence, re-verification setelah perubahan. |
| Forecast/inventory evidence | Forecast dan SS/ROP formula ada | Baseline/backtest, assumptions, stockout comparison, no unsupported savings claims. |
| Omnichannel consistency | Web/API dan bot sama-sama ada namun terpisah | Same catalog, safety decision, order status, payment enforcement, and identity. |

## 5. Partnership hypotheses — belum terkonfirmasi

Kandidat diskusi, bukan klaim dukungan:

- Satu operator katering UMKM/mitra Dova Kitchen sebagai design partner.
- Supplier bahan dengan product specification/SKU/pack-size yang dapat dibuktikan.
- Asosiasi F&B untuk discovery dan distribution hypothesis.
- BPOM atau pihak berwenang terkait sebagai ide jalur konsultasi/validasi regulasi, **bukan afiliasi atau endorsement yang sudah ada**.

Setiap outreach harus mencatat: pihak, tanggal, tujuan, consent, status (idea/contacted/discussion/agreed), dan bukti tertulis. Jangan menampilkan logo/nama sebagai partner sebelum ada bukti resmi.

## 6. Partnership evidence checklist

- Problem interview terpisah dari product demo.
- Recipe/ingredient evidence berasal dari label, supplier specification, SOP, atau sumber yang dapat diaudit.
- Pemilik operasi menyetujui owner untuk recipe verification, payment review, kitchen workflow, dan PO approval.
- Supplier menyetujui field data dan batas aksesnya.
- Pilot agreement menjelaskan data, consent, retention, incident handling, dan penghentian pilot.
- Economic impact disajikan sebagai scenario/sensitivity jika belum ada baseline aktual.

## 7. Decision gates

Jangan memperluas pilot apabila salah satu kondisi berikut terjadi:

1. Ingredient evidence banyak yang unknown tetapi UI tetap menyatakan eligible.
2. Blocked order dapat melewati API, bot, atau direct payload.
3. Unpaid order muncul pada kitchen workflow.
4. PO dapat dikirim tanpa admin approval.
5. Supplier dapat membaca data supplier/customer lain.
6. Angka simulasi tampil tanpa label.
7. Partner/endorsement disebut tanpa bukti tertulis.
