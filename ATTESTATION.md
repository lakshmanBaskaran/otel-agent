# ATTESTATION.md (Phase 0)

## Candidate

- Name: Lakshman
- Repository URL: https://github.com/lakshmanBaskaran/otel-agent
- Date: 2026-06-17

---

## Comprehension prompts

### 1. Fact-table grain

In one sentence, what is the grain of `reservations_hackathon`?

> One row per reservation × stay_date

### 2. Revenue columns

Name the two revenue columns and when to use each.

> `daily_room_revenue_before_tax` for room-only questions. `daily_total_revenue_before_tax` for total revenue questions including extras.

### 3. Row vs reservation

Give one example question where counting rows would be wrong.

>  Each row is per stay-date, but one reservation can span multiple nights.

### 4. Schema fields

Is there an `otel_challenge_token` column in the official schema? If so, what is it used for?

> No. There is no `otel_challenge_token` column in the official schema. 
> 
### 5. Default OTB filters

Which `reservation_status` and `financial_status` values are excluded from default OTB?

> `reservation_status = 'Cancelled'` and `financial_status = 'Provisional'` are both excluded from default OTB. 

### 6. Stay date vs property date

When can `property_date` differ from `stay_date`, and which field drives monthly OTB?

> `property_date` is the hotel's business-date attribution and can differ from `stay_date` on night-boundary or audit rows Monthly OTB is always driven by `stay_date`, not `property_date`.

### 7. Point-in-time OTB

How does `as_of_utc` change which cancelled rows are included in `get_as_of_otb`?

> A cancelled row is included in the snapshot if `cancellation_datetime > as_of_utc`  meaning the cancellation hadn't happened yet at the snapshot time. Rows cancelled before `as_of_utc` are excluded. This lets you reconstruct what the book looked like at any past moment.

### 8. Block vs transient

How does `is_block` affect a "group vs transient mix" question?

> `is_block = true` identifies group reservations. I filter on `is_block` rather than market code or macro group, because `is_block` is the fact-table flag and is grain-correct at the stay-date level.

### 9. List pagination

How many reservations does the data site show per list page?

> 100 reservations per list page.

### 10. Pagination completeness

How will you prove you did not miss the last list page during ETL?

> After scraping, I compute the SHA-256 of sorted reservation IDs and compare it against data site. 

### 11. Tool grain

For `get_otb_summary`, what is the difference between `row_count` and `reservation_count`?

> `row_count` is stay-date rows — a 3-night booking contributes 3. `reservation_count` is `COUNT(DISTINCT reservation_id)` — the same booking contributes 1. For "how many bookings" questions, always use `reservation_count`.

### 12. Human-in-the-loop

Why must `get_as_of_otb` be gated behind approval, and what goes wrong if it is not?

> `get_as_of_otb` queries the raw table without the view's pre-filtering, making it the most expensive query in the system. Without HITL, the agent might call it on routine OTB questions that don't need time travel, or the GM might misread a historical snapshot as the current book. The approval gate forces the agent to explain what it's about to do before running.

### 13. Skill vs tool

Name one revenue-manager question that should load a **skill** but call **`get_segment_mix`**, not raw SQL.

> "What's driving July?" — this loads `segment_concentration.md`, which teaches the agent the 6-layer answer pattern (total → top 3 → group vs transient → concentration flag → pickup check). It then calls `get_segment_mix` to pull the numbers. The skill provides the judgment; the tool provides the data.

---

## ETL design (one line)

Describe pagination strategy + idempotency approach + **anchor date** you will
scrape against (must match `/verify` on load day).

> Playwright scrapes the paginated list (100 reservations/page × 3 pages), follows each reservation into its detail page to capture `financial_status`, `property_date`, and per-night stay rows, then truncate-and-reloads into Postgres for idempotency. Anchor date is today's date at scrape time, stored in `SCRAPE_MANIFEST.json` and reconciled against `/verify` before submission.
