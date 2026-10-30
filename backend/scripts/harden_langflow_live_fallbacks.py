"""Harden embedded LIVE Langflow transforms against missing-data defaults."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
FLOW_PATH = ROOT / "langflow" / "Dova_Kitchen_Chef_BOB_LIVE.json"


def _node(payload: dict[str, Any], fragment: str) -> dict[str, Any]:
    matches = [
        node
        for node in payload["data"]["nodes"]
        if fragment in str(node.get("data", {}).get("node", {}).get("display_name", ""))
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one LIVE node for {fragment!r}, found {len(matches)}.")
    return matches[0]["data"]["node"]


def _replace_once(code: str, old: str, new: str, *, label: str) -> str:
    count = code.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one replacement for {label}, found {count}.")
    return code.replace(old, new, 1)


def _set_code(node: dict[str, Any], code: str) -> None:
    node["template"]["code"]["value"] = code
    metadata = node.setdefault("metadata", {})
    metadata["code_hash"] = "dova-live-fail-closed-" + hashlib.sha256(code.encode()).hexdigest()[:12]


STRICT_ORDER_BLOCK = '''        cid = required_order_value(o, "customer_id")
        order_id = required_order_value(o, "order_id")
        order_date = required_order_value(o, "order_date")
        quantity = required_order_value(o, "quantity")
        total = required_order_value(o, "total")
        menu = required_order_value(o, "menu")
        customer_name = required_order_value(o, "customer_name")
        if isinstance(quantity, bool) or not isinstance(quantity, (int, float)) or quantity < 0:
            raise ValueError("LIVE order memiliki quantity invalid; CRM/RFM ditahan.")
        if isinstance(total, bool) or not isinstance(total, (int, float)) or total < 0:
            raise ValueError("LIVE order memiliki total invalid; CRM/RFM ditahan.")
        if not str(customer_name).strip() or not str(menu).strip():
            raise ValueError("LIVE order memiliki customer/menu kosong; CRM/RFM ditahan.")
        key = str(order_id)
        t = tmp[cid][key]
        t["qty"] += quantity
        t["total"] += total
        t["date"] = to_date(order_date)
        names[cid] = str(customer_name)
'''


STRICT_MENU_QTY_BLOCK = '''    for o in orders:
        cid = required_order_value(o, "customer_id")
        menu = required_order_value(o, "menu")
        quantity = required_order_value(o, "quantity")
        if isinstance(quantity, bool) or not isinstance(quantity, (int, float)) or quantity < 0:
            raise ValueError("LIVE order memiliki quantity invalid; CRM ditahan.")
        menu_qty[cid][menu] += quantity
'''


def harden_customer_node(node: dict[str, Any]) -> None:
    code = node["template"]["code"]["value"]
    helper = '''def required_order_value(order, field):
    if field not in order or order[field] is None:
        raise ValueError(f"LIVE order kehilangan {field}; CRM/RFM ditahan.")
    return order[field]

'''
    code = _replace_once(code, "def group_orders(orders):", helper + "def group_orders(orders):", label="order helper")
    old_block = '''        cid = o["customer_id"]
        key = o.get("order_id") or str(o["order_date"])
        t = tmp[cid][key]
        t["qty"] += o.get("quantity", 1)
        t["total"] += o.get("total", 0)
        t["date"] = to_date(o["order_date"])
        if o.get("customer_name"):
            names[cid] = o["customer_name"]
'''
    code = _replace_once(code, old_block, STRICT_ORDER_BLOCK, label="order defaults")
    if "menu_qty" in code:
        old_menu = '''    for o in orders:
        menu_qty[o["customer_id"]][o["menu"]] += o.get("quantity", 1)
'''
        code = _replace_once(code, old_menu, STRICT_MENU_QTY_BLOCK, label="menu quantity default")
    if "names.get(cid, cid)" in code:
        code = _replace_once(code, '"customer_name": names.get(cid, cid),', '"customer_name": names[cid],', label="customer name default")
    if "today = to_date(today) if today else date.today()" in code:
        code = _replace_once(
            code,
            "    today = to_date(today) if today else date.today()",
            '    if today is None:\n        raise ValueError("LIVE context kehilangan today; RFM ditahan.")\n    today = to_date(today)',
            label="RFM today default",
        )
    _set_code(node, code)


INVENTORY_FUNCTION = '''def compute_shortage(forecast, bom, stock, low_buffer=0.2):
    if not isinstance(forecast, dict) or not isinstance(bom, dict) or not isinstance(stock, dict):
        raise ValueError("LIVE inventory membutuhkan forecast, BOM, dan stock object.")
    forecast_items = forecast.get("items")
    if not isinstance(forecast_items, list):
        raise ValueError("LIVE inventory kehilangan forecast items; inventory ditahan.")
    need = defaultdict(float)
    no_bom = []
    missing_stock = []
    for it in forecast_items:
        if not isinstance(it, dict) or not it.get("menu") or "forecast_portions" not in it:
            raise ValueError("LIVE forecast item tidak lengkap; inventory ditahan.")
        portions = it["forecast_portions"]
        if isinstance(portions, bool) or not isinstance(portions, (int, float)) or portions < 0:
            raise ValueError("LIVE forecast portions invalid; inventory ditahan.")
        recipe = bom.get(it["menu"])
        if recipe is None:
            no_bom.append(it["menu"])
            continue
        if not isinstance(recipe, dict):
            raise ValueError("LIVE BOM memiliki shape invalid; inventory ditahan.")
        for ing, grams in recipe.items():
            if isinstance(grams, bool) or not isinstance(grams, (int, float)) or grams < 0:
                raise ValueError("LIVE BOM memiliki quantity invalid; inventory ditahan.")
            need[ing] += portions * grams
    rows = []
    for ing, required in need.items():
        if ing not in stock:
            missing_stock.append(ing)
            continue
        have = stock[ing]
        if isinstance(have, bool) or not isinstance(have, (int, float)) or have < 0:
            raise ValueError("LIVE stock memiliki quantity invalid; inventory ditahan.")
        short = max(0.0, required - have)
        status = "SHORTAGE" if short > 0 else ("LOW_STOCK" if have < required * (1 + low_buffer) else "AVAILABLE")
        rows.append({"ingredient": ing, "need_g": round(required), "stock_g": round(have),
                     "shortage_g": round(short), "shortage_kg": round(short / 1000, 3),
                     "status": status})
    rows.sort(key=lambda r: -r["shortage_g"])
    return {"horizon_days": forecast.get("horizon_days"), "forecast_status": forecast.get("status"),
            "ingredients": rows, "menu_without_bom": no_bom,
            "ingredient_without_stock": missing_stock}


'''


SUPPLIER_FUNCTION = '''def rank_suppliers_and_draft_po(inventory, suppliers, max_lead_days=None,
                                w_price=0.6, w_lead=0.4):
    if not isinstance(inventory, dict) or not isinstance(suppliers, list):
        raise ValueError("LIVE supplier ranking membutuhkan inventory/supplier object yang valid.")
    lines, unresolved = [], []
    for row in inventory.get("ingredients", []):
        if row.get("status") != "SHORTAGE":
            continue
        ingredient = str(row.get("ingredient") or "").strip()
        shortage = row.get("shortage_kg")
        if not ingredient or isinstance(shortage, bool) or not isinstance(shortage, (int, float)) or shortage < 0:
            raise ValueError("LIVE shortage row invalid; supplier ranking ditahan.")
        cands = []
        for supplier in suppliers:
            if not isinstance(supplier, dict):
                raise ValueError("LIVE supplier row invalid; supplier ranking ditahan.")
            required = ("name", "ingredient", "price_per_kg", "moq_kg", "lead_time_days", "capacity_kg")
            if any(field not in supplier or supplier[field] is None for field in required):
                continue
            price = supplier["price_per_kg"]
            moq = supplier["moq_kg"]
            lead = supplier["lead_time_days"]
            capacity = supplier["capacity_kg"]
            if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in (price, moq, lead, capacity)):
                raise ValueError("LIVE supplier numeric field invalid; supplier ranking ditahan.")
            if price <= 0 or moq < 0 or lead < 0 or capacity < 0:
                raise ValueError("LIVE supplier numeric field out of range; supplier ranking ditahan.")
            if str(supplier["ingredient"]).lower() != ingredient.lower():
                continue
            qty = max(shortage, moq)
            if qty > capacity:
                continue
            if max_lead_days is not None and lead > max_lead_days:
                continue
            cands.append((supplier, qty))
        if not cands:
            unresolved.append({"ingredient": ingredient, "shortage_kg": shortage,
                               "status": "NO_ELIGIBLE_SUPPLIER"})
            continue
        prices = [supplier["price_per_kg"] for supplier, _ in cands]
        leads = [supplier["lead_time_days"] for supplier, _ in cands]

        def norm(value, lo, hi):
            return 0.0 if hi == lo else (value - lo) / (hi - lo)

        scored = sorted(
            [(w_price * norm(supplier["price_per_kg"], min(prices), max(prices))
              + w_lead * norm(supplier["lead_time_days"], min(leads), max(leads)), supplier, qty)
             for supplier, qty in cands], key=lambda item: item[0])
        score, best, qty = scored[0]
        lines.append({
            "ingredient": ingredient, "supplier": best["name"], "qty_kg": round(qty, 2),
            "unit_price": best["price_per_kg"], "est_total": round(qty * best["price_per_kg"]),
            "lead_time_days": best["lead_time_days"], "score": round(score, 3),
            "alternatives": [{"supplier": supplier["name"], "score": round(sc, 3)} for sc, supplier, _ in scored[1:]],
        })
    by_sup = defaultdict(list)
    for line in lines:
        by_sup[line["supplier"]].append(line)
    pos = [{"supplier": supplier, "lines": lines, "est_total": sum(line["est_total"] for line in lines),
            "status": "DRAFT_PENDING_ADMIN_APPROVAL"} for supplier, lines in by_sup.items()]
    return {"purchase_orders": pos, "unresolved": unresolved,
            "note": "PO hanya draft. Wajib disetujui admin sebelum dikirim ke supplier."}


'''


MARKETING_FUNCTION = '''def draft_marketing(rfm_rows, profiles):
    if not isinstance(rfm_rows, list) or not isinstance(profiles, dict):
        raise ValueError("LIVE marketing membutuhkan RFM/profile object yang valid.")
    out = []
    for row in rfm_rows:
        if not isinstance(row, dict) or row.get("segment") not in ("AT_RISK", "CHURNED"):
            continue
        customer_id = str(row.get("customer_id") or "").strip()
        profile = profiles.get(customer_id)
        favorite = profile.get("favorite_menu") if isinstance(profile, dict) else None
        name = row.get("customer_name")
        if not customer_id or not favorite or not name:
            out.append({"customer_id": customer_id, "segment": row.get("segment"),
                        "status": "DRAFT_BLOCKED", "reason": "PROFILE_FIELD_MISSING"})
            continue
        if row["segment"] == "AT_RISK":
            action = "RETENTION_OFFER"
            message = (f"Halo {name}! Sudah {row['recency_days']} hari sejak pesanan terakhirmu. "
                       f"Minggu ini {favorite} siap diantar lagi, ada penawaran khusus untuk kamu.")
        else:
            action = "WIN_BACK"
            message = (f"Halo {name}, kami kangen! Sudah beberapa minggu kamu belum menikmati {favorite}. "
                       f"Ada promo comeback khusus untuk kamu minggu ini.")
        out.append({"customer_id": customer_id, "segment": row["segment"], "action": action,
                    "favorite_menu": favorite, "message": message, "status": "DRAFT_NOT_SENT"})
    return out


'''


def _replace_function(code: str, start: str, end: str, replacement: str, label: str) -> str:
    begin = code.find(start)
    finish = code.find(end, begin)
    if begin < 0 or finish < 0:
        raise RuntimeError(f"Could not locate {label} boundaries.")
    return code[:begin] + replacement + code[finish:]


def main() -> None:
    payload = json.loads(FLOW_PATH.read_text(encoding="utf-8"))
    original_shape = (len(payload["data"]["nodes"]), len(payload["data"]["edges"]))

    harden_customer_node(_node(payload, "CRM Profile"))
    harden_customer_node(_node(payload, "RFM Segment"))

    inventory = _node(payload, "Inventory & BOM")
    inventory_code = inventory["template"]["code"]["value"]
    inventory_code = _replace_function(inventory_code, "def compute_shortage", "def load_state", INVENTORY_FUNCTION, "inventory compute_shortage")
    _set_code(inventory, inventory_code)

    supplier = _node(payload, "Supplier Ranking")
    supplier_code = supplier["template"]["code"]["value"]
    supplier_code = _replace_function(supplier_code, "def rank_suppliers_and_draft_po", "def load_state", SUPPLIER_FUNCTION, "supplier ranking")
    _set_code(supplier, supplier_code)

    marketing = _node(payload, "Marketing Draft")
    marketing_code = marketing["template"]["code"]["value"]
    marketing_code = _replace_function(marketing_code, "def draft_marketing", "def load_state", MARKETING_FUNCTION, "marketing draft")
    _set_code(marketing, marketing_code)

    context = _node(payload, "Live FastAPI Context")
    context_code = context["template"]["code"]["value"]
    old_counts = '''        counts = state.get("counts") or {}
        self.status = (
            "live: "
            f"menus={counts.get('menus', 0)}, "
            f"orders={counts.get('orders', 0)}, "
            f"customers={counts.get('customers', 0)}"
        )
'''
    new_counts = '''        counts = state.get("counts")
        if not isinstance(counts, dict):
            raise ValueError("FastAPI live context kehilangan counts; flow dihentikan.")
        for field in ("menus", "customers", "orders", "order_items", "stock_items", "suppliers"):
            value = counts.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"FastAPI live context memiliki counts.{field} invalid; flow dihentikan.")
        self.status = (
            "live: "
            f"menus={counts['menus']}, "
            f"orders={counts['orders']}, "
            f"customers={counts['customers']}"
        )
'''
    context_code = _replace_once(context_code, old_counts, new_counts, label="context count defaults")
    _set_code(context, context_code)

    if (len(payload["data"]["nodes"]), len(payload["data"]["edges"])) != original_shape:
        raise RuntimeError("Hardening changed graph shape unexpectedly.")
    FLOW_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"hardened={FLOW_PATH} nodes={original_shape[0]} edges={original_shape[1]}")


if __name__ == "__main__":
    main()

