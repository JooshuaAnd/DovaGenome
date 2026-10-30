# Phase 3 — Adversarial Allergy Guard Test Report

Status: **PASS untuk boundary deterministik backend; Langflow provider live belum diverifikasi.**

## Scope

Pengujian ini memeriksa bahwa output LLM tidak menjadi sumber keputusan safety dan bahwa
jalur order memakai hasil Allergy Guard yang sama.

| Skenario | Bukti | Hasil |
|---|---|---|
| Prompt injection menyatakan recipe aman/verified | `test_prompt_injection_text_cannot_make_pending_recipe_eligible` | PASS — menu tetap `REQUIRES_VERIFICATION` |
| Balasan LLM menyatakan hari blocked aman | `test_llm_reply_cannot_change_menu_suggestion_safety_decision` | PASS — `suggested_days` berasal dari report deterministik |
| Dietary Passport berubah setelah menu terverifikasi | `test_dietary_passport_change_revalidates_same_verified_menu` | PASS — verdict berubah dari `SAFE` menjadi `BLOCKED` |
| Ingredient tersembunyi di recipe/BOM tidak ada di legacy mapping | `test_verified_hidden_bom_component_enters_allergy_guard` | PASS — canonical allergen masuk ke menu dan menjadi `BLOCKED` |
| Checkout pada recipe belum diverifikasi | `test_order_cannot_persist_when_recipe_requires_verification` | PASS — `ConflictError`, persistence tidak dipanggil |
| Recipe pending tanpa konflik allergen | `test_pending_recipe_is_requires_verification_not_safe` | PASS |
| Konflik allergen kritis pada recipe pending | `test_known_critical_conflict_remains_blocked_even_if_recipe_pending` | PASS |

## Verification commands

- `cd backend; python -m pytest -q` — **43 passed**, 1 cache warning pytest Windows.
- `cd backend; python -m compileall -q app tests` — berhasil.
- Supabase read-only smoke test — `migration_check=true`, 18 menu live terbaca, recipe version live terbaca, dan menu existing tetap `PENDING_VERIFICATION`/unresolved.

## Security boundary yang dibuktikan

- LLM hanya menghasilkan teks untuk konsultasi/saran.
- `safety_service.check_menu` menghitung `BLOCKED`, `REQUIRES_VERIFICATION`, `CAUTION`, atau `SAFE` dari kode alergen, kategori, dan metadata recipe.
- `create_order` menolak `BLOCKED` dan `REQUIRES_VERIFICATION` sebelum persistence.
- Allergen canonical dari recipe component ikut dibaca sehingga ingredient yang tidak ada di `menu_ingredients` tidak hilang dari Allergy Guard.

## Batasan yang masih terbuka

- Test provider Langflow memakai mocked response; belum membuktikan koneksi flow/model/vector live.
- Nested child recipe belum menjadi jalur verifikasi admin; component yang belum resolved tetap ditahan.
- 18 recipe existing di database masih pending dan belum boleh dipresentasikan sebagai menu eligible.

