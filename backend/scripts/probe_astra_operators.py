"""Probe kompatibilitas Astra Data API untuk operator yang dipakai backend."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.repositories import astra  # noqa: E402

db = astra.get_database()


def show(name: str, fn) -> None:
    try:
        result = fn()
        if hasattr(result, "__iter__") and not isinstance(result, dict):
            summary = f"{len(list(result))} dokumen"
        elif isinstance(result, dict):
            summary = f"dict({sorted(result)[:4]})"
        else:
            summary = repr(result)
        print(f"OK    {name} -> {summary}")
    except Exception as exc:
        print(f"FAIL  {name} -> {type(exc).__name__}: {str(exc)[:200]}")


show("find_one _id (eq)", lambda: db.get_collection("catering_packages").find_one({"_id": "pkg_full"}))
show("find_one $or", lambda: db.get_collection("catering_packages").find_one({"$or": [{"_id": "pkg_full"}]}))
show("find status $in", lambda: db.get_collection("kitchen_orders").find({"status": {"$in": ["PENDING", "COMPLETED"]}}, limit=5))
show("find created_at range", lambda: db.get_collection("kitchen_orders").find({"created_at": {"$gte": "2020-01-01", "$lt": "2030-01-01"}}, limit=2))
show("count_documents eq", lambda: db.get_collection("kitchen_orders").count_documents({"status": "PENDING"}, upper_bound=100))
show("count_documents $in", lambda: db.get_collection("kitchen_orders").count_documents({"status": {"$in": ["PENDING"]}}, upper_bound=100))
show("update_one eq no match", lambda: db.get_collection("customers").update_one({"_id": "probe_tidak_ada"}, {"$set": {"x": 1}}))
show("update_one upsert", lambda: db.get_collection("customers").update_one({"_id": "probe_upsert_test"}, {"$set": {"x": 1}}, upsert=True))
show("$push", lambda: db.get_collection("customers").update_one({"_id": "probe_upsert_test"}, {"$push": {"arr": 1}}))
show("$set nested path", lambda: db.get_collection("customers").update_one({"_id": "probe_upsert_test"}, {"$set": {"passport.notes": "x"}}))
show("sort + limit", lambda: db.get_collection("kitchen_orders").find({}, sort={"created_at": -1}, limit=3))
show("update_one $or filter", lambda: db.get_collection("customers").update_one({"$or": [{"_id": "probe_upsert_test"}]}, {"$set": {"y": 2}}))
show("count_documents no upper_bound", lambda: db.get_collection("kitchen_orders").count_documents({}))
show("insert_one then delete", lambda: db.get_collection("customers").delete_one({"_id": "probe_upsert_test"}))