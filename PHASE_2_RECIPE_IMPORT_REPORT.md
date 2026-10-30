# Phase 2 — AI recipe intake and nutrition preview

Status: **implemented locally; operator verification and migrations remain gated**.

- Admin can upload PDF, XLSX, CSV, TXT, or Markdown recipe material.
- Backend bounds the file at 10 MB and extracted text at 120,000 characters,
  records SHA-256/file metadata when migration 013 is available, and sends the
  bounded text to the AI draft service.
- The AI response is still a draft. Applying it creates unverified recipe
  components; it cannot mark a recipe or ingredient safe.
- Nutrition preview uses verified per-100g composition evidence and the
  deterministic 4/4/9 energy formula. Missing/unsupported evidence returns
  `UNAVAILABLE` with warnings rather than invented values.
- `pypdf` is declared in `backend/requirements.txt`; the local environment
  used for tests did not have it installed, so PDF parsing must be rechecked
  after dependency installation.

