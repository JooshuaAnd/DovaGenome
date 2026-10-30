# Phase 15 — Isolated acceptance demo

Status: **contract demo implemented; live acceptance remains gated**.

Run from the repository root:

```powershell
python backend/scripts/run_phase_acceptance_demo.py
```

The command produces a deterministic JSON report with `data_mode=SIMULATED`.
It reconciles:

- verified recipe BOM × 100 portions;
- planned grams vs actual weighed grams and closing stock;
- supplier PO quantity and price;
- posted goods receipt with internal lot barcode;
- weekly invoice expected amount vs submitted amount;
- manual payment boundary and delivery status path.

It does not write to Supabase, create an order, send a supplier message, or
claim payment/delivery success. The live gates are emitted in the report so a
demo cannot be mistaken for production evidence.

Latest local verification: backend suite **222 passed**, backend compile passed,
and frontend production build passed. The demo remains `SIMULATED`; it is not a
claim that the pending Supabase extensions, payment provider, Telegram worker,
or delivery provider are live.
