"""
Perbaikan katalog DovaGenome di Astra DB.

1. Backup 8 dokumen fixture uji ke backup_junk_catalog_YYYYMMDD_HHMMSS.json
2. Hapus dokumen fixture tersebut
3. Jalankan seed_catering_data.py untuk memulihkan katalog kanonik
4. Migrasikan selected_allergen yang terpengaruh prefiks ganda (alg_alg_*)

Jalankan: python repair_catalog.py --yes
Tanpa --yess, hanya menampilkan rencana (tidak menulis apa pun).
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

import data as D  # noqa: E402
import seed_catering_data as S  # noqa: E402

COLLECTIONS = {
    "catering_packages": "pkg_",
    "allergen_definitions": "alg_",
    "catering_menus": "menu_",
}
APPLY = "--yes" in sys.argv

db = D.connect_db()
if db is None:
    raise SystemExit("Koneksi Astra DB gagal. Cek ASTRA_DB_API_ENDPOINT & token di .env")

# ── 1. Kumpulkan dokumen fixture (yang _id-nya bukan kanonik) ──────────────
junk: dict[str, list] = {}
for col, prefix in COLLECTIONS.items():
    junk[col] = [
        d for d in db.get_collection(col).find({})
        if not str(d.get("_id", "")).startswith(prefix)
    ]

total = sum(len(v) for v in junk.values())
print(f"Dokumen fixture ditemukan: {total}")
for col, docs in junk.items():
    for d in docs:
        ident = d.get("code") or d.get("kode") or d.get("hari") or d.get("nama") or "?"
        print(f"  {col:22s} _id={str(d.get('_id'))[:26]:26s} ident={ident}")

if not total:
    print("\nTidak ada dokumen fixture. Katalog sudah bersih.")
else:
    # ── 2. Backup ───────────────────────────────────────────────────────────
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"backup_junk_catalog_{stamp}.json"
    payload = {
        "created_at": datetime.datetime.now().isoformat(),
        "reason": "Dokumen fixture dari skrip pengujian; katalog kanonik dipulihkan "
                  "dari seed_catering_data.py",
        "collections": {
            col: [{k: (str(v) if k == "_id" else v) for k, v in d.items()} for d in docs]
            for col, docs in junk.items()
        },
    }
    with open(backup_file, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, default=str)
    print(f"\nBackup ditulis: {backup_file}")
    if not APPLY:
        print("Mode rencana. Jalankan ulang dengan --yes untuk menerapkan.")
        raise SystemExit(0)

    # ── 3. Hapus fixture ─────────────────────────────────────────────────────
    for col, docs in junk.items():
        for d in docs:
            db.get_collection(col).delete_one({"_id": d["_id"]})
        print(f"  dihapus {len(docs)} dokumen dari {col}")

    # ── 4. Pulihkan katalog kanonik ─────────────────────────────────────────
    print("\nMenjalankan seed_catering_data.seed_data() ...")
    S.seed_data()

# ── 5. Verifikasi katalog ─────────────────────────────────────────────────
print("\n=== VERIFIKASI ===")
ok = True
expect = {"catering_packages": 3, "allergen_definitions": 6, "catering_menus": 6}
for col, want in expect.items():
    docs = list(db.get_collection(col).find({}))
    junk_left = [d for d in docs if not str(d.get("_id", "")).startswith(COLLECTIONS[col])]
    status = "OK" if len(docs) == want and not junk_left else "PERIKSA"
    ok &= status == "OK"
    print(f"  {status:7s} {col:22s} {len(docs)} dokumen (harusnya {want}), sisa fixture={len(junk_left)}")

menus = list(db.get_collection("catering_menus").find({}))
with_bahan = [m for m in menus if m.get("bahan_detail")]
print(f"  {'OK' if with_bahan else 'PERIKSA':7s} menu dengan bahan_detail: {len(with_bahan)}/{len(menus)}")

# ── 6. Migrasi prefiks ganda pada pesanan ────────────────────────────────
print("\n=== MIGRASI selected_allergens ===")
fixed = 0
for o in db.get_collection("kitchen_orders").find({}):
    sel = o.get("selected_allergens")
    if not isinstance(sel, list) or not any(str(s).startswith("alg_alg_") for s in sel):
        continue
    clean, seen = [], set()
    for s in sel:
        code = str(s)
        while code.startswith("alg_alg_"):
            code = code[len("alg_"):]
        if code and code not in seen:
            seen.add(code)
            clean.append(code)
    print(f"  {o.get('order_id')} ({o.get('customer_name')})")
    print(f"    lama : {sel}")
    print(f"    baru : {clean}")
    if APPLY:
        db.get_collection("kitchen_orders").update_one(
            {"_id": o["_id"]},
            {"$set": {"selected_allergens": clean}},
        )
    fixed += 1
print(f"  pesanan diperbaiki: {fixed}" + ("" if APPLY else " (mode rencana)"))

print("\n" + ("SELESAI ✅" if ok else "PERLU PERIKSA ⚠️"))
