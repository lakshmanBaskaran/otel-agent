# Submission checklist

Use this when you consider the build complete. Passing local checks is **necessary
but not sufficient** — we run additional internal review on every submission.

## Before you submit

1. **Repo artifacts** (in your solution repo, not this brief):
   - [ ] `ATTESTATION.md` (from [ATTESTATION.example.md](ATTESTATION.example.md))
   - [ ] `etl/SCRAPE_MANIFEST.json` and `etl/LOAD_PROOF.json`
   - [ ] `tools/METRIC_DEFINITIONS.md` + all five required tools
   - [ ] `tests/test_etl.py` (≥3), `tests/test_tools.py` (≥10), `tests/test_skills.py` (≥5), `tests/test_agent.py` (≥4)
   - [ ] `skills/` (≥6 skills, ≥3 judgment) and `ARCHITECTURE.md` with skill→tool matrix
2. **Fingerprint match:** run `scripts/compute_load_fingerprint.py` and reconcile
   with [https://otel-hackathon-data-site.vercel.app/verify](https://otel-hackathon-data-site.vercel.app/verify)
   on the same scrape day as your manifest `anchor_date`.
3. **Live deploy:**
   - [ ] Hosted Postgres loaded by your ETL (not localhost-only)
   - [ ] Agent UI streams tool/skill calls
   - [ ] `GET /health` returns `db_fingerprint`, `dataset_revision`, `row_hash`,
     and `financial_status_posted_only_rows` matching your `LOAD_PROOF`
   - [ ] Basic auth on the public URL

## What to send

Submit **one message** via the intake channel you were given (form or email — not
GitHub issues on the brief repo):

| Field | Notes |
|-------|-------|
| Solution repo URL | Your own repo; do not fork the brief |
| Live agent URL | Must stay up ≥7 days after submission |
| Basic-auth credentials | **Private intake only** — never in the repo |

## What you will hear back

- **Acknowledgment** when we receive your submission.
- **No** score, rank, rubric feedback, or flag details — evaluation is internal.

## Outbound template (for organizers)

Copy this when inviting candidates:

```
Brief: https://github.com/otel-ai/otel-build-challenge
Data site: https://otel-hackathon-data-site.vercel.app
Submit when done: [your form/email] with repo URL + live URL + basic-auth credentials
```

No second repo. No "reply for pack."
