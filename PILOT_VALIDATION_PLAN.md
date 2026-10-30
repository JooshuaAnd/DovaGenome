# Pilot Validation Plan — DovaGenome

Status: **rencana validasi; bukan hasil survei, bukan kesepakatan mitra, dan bukan klaim dampak.**

## 1. Scope pilot

- Pilot awal: **satu use case Dova Kitchen** untuk satu segmen katering yang melayani kebutuhan alergi/diet khusus.
- Tidak mencakup sekaligus fine dining, hotel, restoran umum, atau semua tipe F&B.
- Fokus nilai utama: ingredient/allergen traceability dan order safety.
- Nilai tambahan: efisiensi pengadaan, forecast, dan retention.
- Technical roles: Customer, Admin, Kitchen, Supplier.
- Stakeholder bisnis: customer, pengelola/operasional Dova Kitchen, supplier.

## 2. Pertanyaan validasi

### Customer

- Apakah customer dapat memasukkan allergy/intolerance/preference tanpa kebingungan?
- Apakah alasan menu `BLOCKED` atau `REQUIRES_VERIFICATION` dapat dipahami?
- Apakah customer menerima istilah “lolos pemeriksaan berdasarkan data” dan tidak menganggapnya jaminan medis?
- Apakah waktu pengisian passport, pemilihan menu, dan checkout dapat diselesaikan tanpa bantuan operator?

### Pengelola/Admin

- Apakah recipe dan ingredient evidence dapat dimasukkan serta diverifikasi dengan cepat?
- Siapa yang berwenang edit recipe dan siapa yang approve verification?
- Apakah admin dapat memahami mengapa menu blocked/requires verification?
- Apakah draft PO, forecast, dan asumsi biaya dapat direview sebelum dikirim?

### Kitchen

- Apakah kitchen ticket menampilkan informasi alergi minimum yang diperlukan tanpa membuka PII berlebihan?
- Apakah data recipe, cross-contact, substitusi, dan perubahan versi dapat diikuti?
- Apakah aturan “no pay, no cook” benar-benar dipatuhi dalam board dan proses kerja?

### Supplier

- Apakah supplier dapat memasukkan unit, pack size, SKU, MOQ, harga, lead time, kapasitas, dan deklarasi alergen tanpa format ambigu?
- Apakah supplier hanya dapat melihat PO dan katalog miliknya?
- Apakah supplier dapat menolak/partial accept dengan alasan yang dapat ditelusuri?

## 3. Validation stages

| Stage | Aktivitas | Evidence | Status label |
|---|---|---|---|
| V0 | Data inventory dan recipe fixture | Source document, verifier, timestamp, version | `Data simulasi` bila belum operational |
| V1 | Adversarial Allergy Guard | Labeled fixture, TP/FP/TN/FN, blocked/requires verification cases | `Test result` |
| V2 | Usability walk-through empat role | Task completion, errors, operator notes | `Pilot observation` |
| V3 | End-to-end technical demo | Order → payment simulator → kitchen → BOM → PO approval | `Demo simulation` |
| V4 | Forecast/inventory backtest | Rolling-origin metrics and stockout comparison | `Backtest`, bukan production impact |
| V5 | Limited operational pilot | Actual consented transactions and incident log | `Pilot actual` hanya jika data benar-benar terkumpul |

## 4. Safety acceptance criteria

- Unknown ingredient/allergen/provenance tidak boleh diperlakukan sebagai bebas risiko.
- Recipe change, ingredient substitution, atau passport change memicu re-evaluation.
- LLM tidak dapat membuat menu baru, mengubah `BLOCKED`, atau mengubah `REQUIRES_VERIFICATION` menjadi eligible.
- Blocked order tidak dapat dibuat melalui API, web, Telegram, atau direct client payload.
- Kitchen hanya melihat/menjalankan paid order yang sudah melewati payment verification.
- Kitchen ticket dan audit log menyimpan versi recipe/safety data yang dipakai saat order.
- Tidak ada klaim recall 100% universal; target recall hanya berlaku terhadap fixture berlabel dan dilaporkan bersama keterbatasannya.

## 5. Metrics

### Safety and quality

- TP, FP, TN, FN per fixture.
- Precision, recall, false-negative count.
- Jumlah `REQUIRES_VERIFICATION` dan waktu penyelesaiannya.
- Jumlah hard-block bypass attempts yang ditolak.
- Recipe verification completeness dan stale verification count.

### Operational

- Waktu memasukkan/verifikasi recipe.
- Waktu dari paid event ke kitchen ticket.
- Duplicate webhook/order rate.
- PO draft review time dan unresolved ingredient count.
- Supplier response time dan fill/partial response bila data tersedia.

### Business, only if data supports it

- Repeat order rate, reorder interval, observed AOV, cancellation reason.
- Stockout rate, fill rate, excess inventory, estimated cost under documented assumptions.
- Win-back conversion hanya dengan treatment/control dan consent.

Tidak ada angka target yang boleh dianggap hasil aktual. Angka dari feedback mentor (250 customer, 3.859 order, 28% Champion, 53,5% revenue, WAPE 28,2%) harus dihitung ulang dari dataset yang provenance-nya cocok sebelum dipakai.

## 6. Forecast and inventory protocol

1. Tentukan forecast origin dan hanya gunakan data yang tersedia sampai origin tersebut.
2. Bandingkan naive, moving average 7 hari, seasonal naive jika data cukup, dan model saat ini.
3. Gunakan rolling-origin temporal backtest; laporkan WAPE/MAE/coverage bila interval tersedia.
4. Hitung BOM dari recipe version; jangan mengarang gramasi.
5. Bandingkan safety stock off/on pada stockout, fill rate, ending inventory, excess, dan biaya estimasi bila input biaya tersedia.
6. Labeli hasil sebagai `Backtest`, bukan penghematan produksi.

## 7. Win-back experiment protocol

- Tentukan eligibility reproducibly dari consent dan segment/risk rule.
- Assign treatment/control sebelum pesan dikirim.
- Catat tanggal assignment, channel, consent, holdout, exposure, reorder window, dan outcome.
- Jangan menyebut uplift/causal impact sebelum periode pengukuran selesai dan control group valid.
- Semua pesan tetap `DRAFT` sampai admin approval.

## 8. Data governance

- Pisahkan fixture/demo, backtest, dan production/pilot data.
- Simpan source ingredient evidence, verifier, timestamp, product/SKU/version.
- Redact PII dari logs, prompt, Langflow retrieval, dan supplier views.
- Simpan audit log untuk passport, recipe, payment, order, ticket, inventory, PO, dan campaign.

## 9. Langflow recovery dan AI proof gate

Validasi pilot tidak boleh menganggap export JSON atau text fallback sebagai bukti Langflow live. Sebelum Chef BOB/admin AI masuk demo terintegrasi:

- Inventaris caller web, API, service, RAG, Telegram, dan fallback beserta endpoint/dependency/source output.
- Buktikan readiness terpisah untuk aplikasi, konektivitas Langflow, eksekusi flow, model, vector retrieval, dan live data.
- Pisahkan `DATA_MODE=live|simulation` dan `AI_MODE=required_langflow|allow_explicit_fallback|disabled`; setiap response membawa request ID, source, dan latency.
- Uji failure terkontrol: Langflow off, wrong flow ID/endpoint, credential invalid, model/vector error, malformed JSON, timeout, dan prompt injection.
- Tunjukkan satu request Chef BOB dan satu admin AI yang benar-benar live bila tersedia; bila tidak, tulis `LIVE NOT VERIFIED`.
- Allergy Guard tetap mengikuti verified BOM → allowed menu IDs → restricted retrieval → structured output → backend post-filter → checkout revalidation. LLM tidak boleh memperluas menu yang eligible.
- Laporan wajib: `LANGFLOW_CONNECTION_AUDIT.md`, `LANGFLOW_RUNTIME_PROOF.md`, dan `LANGFLOW_FAILURE_TEST_REPORT.md`.
