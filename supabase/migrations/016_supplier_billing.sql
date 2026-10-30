-- Phase 7: supplier invoices, three-way match, and manual payable records.
-- QR_ILLUSTRATIVE is intentionally a reference method, never a live transfer.

BEGIN;

CREATE TABLE IF NOT EXISTS supplier_invoices (
    supplier_invoice_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supplier_id        TEXT NOT NULL REFERENCES suppliers(supplier_id),
    invoice_number     TEXT NOT NULL,
    payment_terms      TEXT NOT NULL CHECK (payment_terms IN ('PAY_ON_DELIVERY', 'WEEKLY_INVOICE')),
    period_start       DATE,
    period_end         DATE,
    due_date           DATE NOT NULL,
    amount             NUMERIC(14, 2) NOT NULL CHECK (amount > 0),
    expected_amount    NUMERIC(14, 2) NOT NULL CHECK (expected_amount >= 0),
    currency           TEXT NOT NULL DEFAULT 'IDR',
    match_status       TEXT NOT NULL DEFAULT 'REQUIRES_REVIEW'
                       CHECK (match_status IN ('MATCHED', 'REQUIRES_REVIEW')),
    status             TEXT NOT NULL DEFAULT 'SUBMITTED'
                       CHECK (status IN ('SUBMITTED', 'APPROVED', 'REJECTED', 'PARTIALLY_PAID', 'PAID')),
    idempotency_key    TEXT NOT NULL UNIQUE,
    notes              TEXT NOT NULL DEFAULT '',
    submitted_by       TEXT NOT NULL REFERENCES customers(customer_id),
    verified_by        TEXT REFERENCES customers(customer_id),
    verified_at        TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (supplier_id, invoice_number),
    CHECK (period_end IS NULL OR period_start IS NULL OR period_end >= period_start)
);

CREATE INDEX IF NOT EXISTS idx_supplier_invoices_supplier_status
    ON supplier_invoices (supplier_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS supplier_invoice_pos (
    supplier_invoice_id UUID NOT NULL REFERENCES supplier_invoices(supplier_invoice_id) ON DELETE CASCADE,
    po_id              TEXT NOT NULL REFERENCES purchase_orders(po_id),
    expected_amount    NUMERIC(14, 2) NOT NULL CHECK (expected_amount >= 0),
    PRIMARY KEY (supplier_invoice_id, po_id),
    UNIQUE (po_id)
);

CREATE TABLE IF NOT EXISTS supplier_payment_records (
    supplier_payment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supplier_invoice_id UUID NOT NULL REFERENCES supplier_invoices(supplier_invoice_id),
    amount              NUMERIC(14, 2) NOT NULL CHECK (amount > 0),
    payment_method      TEXT NOT NULL CHECK (payment_method IN ('MANUAL', 'QR_ILLUSTRATIVE')),
    payment_reference   TEXT NOT NULL DEFAULT '',
    idempotency_key     TEXT NOT NULL UNIQUE,
    recorded_by         TEXT NOT NULL REFERENCES customers(customer_id),
    paid_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes               TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_supplier_payment_invoice
    ON supplier_payment_records (supplier_invoice_id, paid_at DESC);

COMMIT;
