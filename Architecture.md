# ARCHITECTURE.md

## 1. ETL boundary

### Why Playwright

The brief mentioned Playwright from the start, but the first attempt used BeautifulSoup with `requests` — the thinking was that static HTML parsing would be faster and simpler. It wasn't. The data site is client-rendered JavaScript: a plain HTTP request returns an empty shell with no reservation data in it. BeautifulSoup had nothing to parse.

Switched to Playwright, which drives a real Chromium browser and waits for JavaScript to finish rendering before extracting content. Two `wait_for_load_state("networkidle")` calls — one after page navigation and one after detail page load — ensure the DOM is fully populated before extraction runs.

### Why page.evaluate() for detail pages

The first Playwright implementation still used BeautifulSoup to parse the rendered HTML. The detail page is a key-value grid (not a table), and BeautifulSoup's `find_next_sibling()` approach was unreliable — it picked up wrong sibling elements, producing revenue figures 2× the correct value and cancelled counts 3× off.

Rewrote `scrape_reservation_detail` to use `page.evaluate()` — JavaScript running directly inside the live browser DOM. This is more reliable because it queries the exact rendered element tree rather than a serialised HTML string. BeautifulSoup is still used for the reference and list pages, which are simpler table structures.

### Why page.evaluate() for pagination

The "Next →" button contains a Unicode arrow character. BeautifulSoup couldn't find it in the rendered HTML. Attempts to navigate via `?page=2` URL parameter also failed — the site manages pagination through client-side state and ignores URL params. The fix was `page.evaluate()` to find and click the Next button via JavaScript in the live DOM.

### Docker → Neon

Started with a local Docker Postgres. Hit `scram-sha-256` authentication failures that persisted through multiple pg_hba.conf edits. Switched to Neon (eu-west-2) — faster to set up, no auth configuration needed, and the deployment needs a hosted DB anyway. Not a planned architectural choice; a forced one that turned out to be the right one.

### Truncate-and-reload

Initial load strategy was upsert with `ON CONFLICT DO UPDATE`. This ran into two problems: `reservation_stay_id` is `GENERATED ALWAYS` in the schema, so inserting scraped IDs required `OVERRIDING SYSTEM VALUE`; and the same composite key (`reservation_id × stay_date`) could appear twice in the same batch before the upsert could resolve it, causing `CardinalityViolation`. Switched to truncate-and-reload: drop all rows, assign fresh sequential IDs, insert clean. The dataset is small enough (~531 rows) that a full reload takes under 5 seconds and removes all conflict resolution complexity.

### Anchor date

The data site regenerates its dataset daily from today's date. What counts as a "future" stay shifts every day. If you scrape on Monday and submit on Wednesday, your LOAD_PROOF fingerprint won't match the site's `/verify` page because the dataset changed between scrape and submission. ETL must be re-run on the day of submission. The anchor date (today's date at scrape time) is recorded in `etl/SCRAPE_MANIFEST.json` and the SHA-256 fingerprint of sorted reservation rows is stored in `etl/LOAD_PROOF.json` for cross-checking.

### property_date vs stay_date

During verification, found exactly 3 rows where `property_date != stay_date`. These are night-boundary or audit attribution rows where the hotel's accounting system assigns the revenue to a different business date than the physical stay night. All monthly OTB aggregations use `stay_date` — the consistent business grain — not `property_date`. The 3 mismatches are documented and tested in `test_property_date_mismatch_count`.

---

## 2. Database and views

### Neon Postgres

The brief specifies a hosted Postgres for deployment. Started with the Docker instance from the brief's `docker-compose.yml` but hit persistent authentication failures (`scram-sha-256` auth refusing connections despite correct credentials and pg_hba.conf edits). Switched to Neon (eu-west-2) — took two minutes to set up and eliminated the auth complexity. The DB stays on Neon for deployment; there was no reason to maintain two separate databases.

Connection via `HOTEL_DATABASE_URL` environment variable. The name is deliberate — using `DATABASE_URL` activates Chainlit's built-in data layer (session persistence, user history), which we don't want. Renaming to `HOTEL_DATABASE_URL` keeps Chainlit stateless and avoids the `asyncpg` dependency that caused deployment errors.

### Why views (brief requirement)

The brief requires `vw_stay_night_base` and `vw_segment_stay_night` from `sql/VIEWS.example.sql`. The views create a semantic layer between tools and raw tables — instead of each tool re-implementing the same cancellation and provisional filters, the view enforces them once and all tools query the view. A tool querying raw `reservations_hackathon` would need to remember to exclude `reservation_status = 'Cancelled'` and `financial_status = 'Provisional'` on every call. The view makes correct behaviour the default.

### vw_stay_night_base

Default OTB universe: `reservation_status != 'Cancelled'` AND `financial_status = 'Posted'`. This is the brief's Appendix A definition of the GM briefing universe. Five of the seven tools query this view. The exception is `get_as_of_otb`, which queries raw `reservations_hackathon` directly — point-in-time logic requires comparing `cancellation_datetime` against an arbitrary timestamp, which the view's static filter can't express.

### vw_segment_stay_night

Extends `vw_stay_night_base` with effective macro group via a LATERAL join on `market_macro_group_history`. The brief notes that PROM (Promotional Retail) gets reclassified mid-year in the history table. A static join on `market_code_lookup.macro_group` would assign PROM the wrong macro group for stays after the reclassification date. The LATERAL join on `stay_date BETWEEN valid_from AND valid_to` handles this correctly — segment mix analysis always uses the macro group that was valid on the actual stay date. `COALESCE(h.macro_group, m.macro_group)` falls back to the lookup table's static group if no history row matches.

---

## 3. Tool layer

I initially built 9 tools against a shared `metrics.py` module, but when the brief updated mid-challenge with a stricter spec I had to drop everything and rewrite from scratch. The new spec required exactly five tools with exact names, exact signatures, and exact view dependencies. I kept two bonus tools on top — `get_room_type_performance` and `get_top_companies` — since the brief's example questions implied them.

### What each tool does

**`get_otb_summary(stay_month, exclude_cancelled=True)`**
The main OTB snapshot for a calendar month. Takes a month in `YYYY-MM` format. By default queries `vw_stay_night_base` which pre-filters to Posted non-cancelled rows — that's the standard GM briefing universe. If `exclude_cancelled=False` is passed, it queries `reservations_hackathon` directly with only the provisional filter removed, so cancelled rows come through. Returns `row_count` (stay-date rows), `reservation_count` (distinct reservation IDs), `room_nights` (sum of `number_of_spaces`), `room_revenue`, and `total_revenue`. The grain distinction matters — a 3-night booking creates 3 rows but 1 reservation and 3 room nights.

**`get_segment_mix(stay_month, macro_group="")`**
Breaks down the month by market segment using `vw_segment_stay_night`. This view does the effective macro group join via LATERAL — it picks the correct macro group from `market_macro_group_history` based on `stay_date`, not the static value in `market_code_lookup`. This matters because PROM gets reclassified mid-year. The `macro_group` parameter lets you filter to a single macro group (e.g. "Retail" or "MICE") and the shares recalculate within that filtered population. Returns each segment's `market_code`, `market_name`, `macro_group`, `room_nights`, `total_revenue`, `share_of_room_nights`, and `share_of_revenue`. Shares always sum to 1.0 within the scope.

**`get_pickup_delta(booking_window_days, future_stay_from)`**
Booking pace — how much new business was created in the last N days for stays from a given date forward. Uses `create_datetime` for the booking window, not `stay_date`. The window start is calculated as midnight Europe/London time N days ago, then converted to UTC before querying — per the brief's Appendix B. Returns `new_reservations`, `new_room_nights`, `new_total_revenue`, and a `by_segment` breakdown of the top 5 market codes by revenue within the window. Also echoes back `window_start_utc` so the GM can see the exact boundary used.

**`get_as_of_otb(stay_month, as_of_utc)`**
Point-in-time OTB — what did the book look like at a past timestamp. Queries `reservations_hackathon` directly, not the view, because the view's static `reservation_status != 'Cancelled'` filter would exclude too much. The logic is: include a row if `create_datetime <= as_of_utc` AND either the reservation was never cancelled OR `cancellation_datetime > as_of_utc`. This means a reservation that was cancelled after the snapshot date still counts — it was on the books at that point. Returns the same shape as `get_otb_summary` plus the `as_of_utc` echoed back. HITL-gated via `interrupt_on={"get_as_of_otb": True}` — the GM must approve before it runs.

**`get_block_vs_transient_mix(stay_month)`**
Splits the month into group (`is_block=true`) and transient (`is_block=false`) using `vw_stay_night_base`. Returns `block_room_nights`, `transient_room_nights`, `block_total_revenue`, `transient_total_revenue`, `block_share_of_room_nights`, `block_share_of_revenue`, and the top 3 companies by revenue with their combined share. The `is_block` flag is the correct grain-level group identifier — not market code, not macro group.

**`get_room_type_performance(stay_month="")` *(bonus)***
ADR, room nights, and revenue broken down by room type. Joins to `room_type_lookup` for the display name, room class, and physical inventory count. If no month is passed, returns all future stays. ADR here is `daily_room_revenue_before_tax / room_nights` — room ADR per type, not total revenue.

**`get_top_companies(limit=5, stay_month="")` *(bonus)***
Top accounts by total revenue. NULL `company_name` is bucketed as 'Transient' so individual leisure guests are visible as a group. Returns `company_name`, `total_revenue`, `room_nights`, `reservation_count`, and `share_of_revenue` against the total in scope. Also returns `top_n_share` — the combined share of the returned companies — which is the concentration signal.

### Why no run_sql

The brief calls a single `run_sql` tool a fail. A model writing arbitrary SQL will silently get grain wrong, forget to exclude cancellations, or pick the wrong date field. Every tool has the business rules hardcoded and tested.

### Why tools return numbers, not judgments

I deliberately kept thresholds out of the tools. A threshold hardcoded in a tool can't reason about context. A skill can. The tools return raw metrics — the skills teach the agent what those numbers mean and what to recommend.

See `tools/METRIC_DEFINITIONS.md` for formal grain definitions.

---

## 4. Deep Agents wiring

### Model and system prompt

The agent runs on `claude-sonnet-4-6`. The system prompt sets a revenue manager persona — it tells the agent to lead with the headline, show the key numbers, explain what's driving them, flag risks, and end with a specific recommendation. It also injects today's date so the agent never defaults to a past year when the GM mentions a month without a year. The data rules are in the prompt too — room nights are always `SUM(number_of_spaces)`, reservation count is always `COUNT(DISTINCT reservation_id)`, never `COUNT(*)`.

### Subagents

The brief required a subagent for segment mix or block mix work. I built two.

The **segment-analyst** handles everything about what's driving the business — which segments are contributing, how the OTA split looks, group vs transient, company concentration. It has `get_segment_mix`, `get_block_vs_transient_mix`, `get_top_companies`, and `get_otb_summary` as context. When the GM asks "what's driving July?" or "are we too dependent on OTA?", the main agent delegates to segment-analyst.

The **demand-analyst** handles booking momentum — what changed recently, how fast we're picking up, which months have weak pace. It has `get_pickup_delta` and `get_otb_summary` for context. When the GM asks "what changed in the last 7 days?" or "how is August pacing?", it goes to demand-analyst.

I originally had a Risk Analyst subagent instead of a Segment Analyst — the idea was that risk questions like cancellations and concentration risk would go to a defensive-thinking subagent. But the brief update was explicit: segment mix or block mix must route through a subagent. So I rebuilt around that. The risk analysis now lives in the skills rather than a dedicated subagent.

### Skills

10 skill files in `skills/`. Each is a `SKILL.md` with YAML frontmatter. Deep Agents loads them on demand via progressive disclosure — the agent reads the skill when the question type matches the description, not upfront on every message. The skills encode judgment: thresholds, what those thresholds mean for this hotel, what to recommend. The tools return numbers. The skills teach the agent how to interpret them. (Details in Section 5.)

### Memory

`MemorySaver` checkpointer added to `create_deep_agent`. This was necessary for the HITL flow — without a checkpointer, `Command(resume=...)` has nothing to resume into and throws an error. It also keeps multi-turn conversation state so the GM can ask "what about August?" as a follow-up without restating context. `memory/AGENTS.md` holds hotel-level context that persists across turns — room types, currency, GM preferences.

### Human-in-the-loop

`get_as_of_otb` is gated via `interrupt_on={"get_as_of_otb": True}`. It's the only tool that does a full raw table scan without the view's pre-filtering — it's the most compute-heavy query in the system. More importantly, a point-in-time snapshot looks identical to current OTB in the chat if the GM doesn't notice the `as_of_utc` timestamp. The gate forces the agent to tell the GM exactly what it's about to run and get explicit approval before it runs.

The Chainlit implementation of HITL went through several iterations. The first attempt used `Command(resume=...)` from LangGraph to resume the interrupted graph — this worked for the interrupt gate but Deep Agents treated the resume command as a new incoming message, which cancelled the in-flight tool call and caused the tool to run twice with no final synthesis. The final solution bypasses the resume entirely: on approval, the tool is called directly from Python, the raw result is passed to a fresh agent instance with a new thread ID for synthesis. This avoids the interrupt gate on the synthesis call entirely.

A session lock (`processing` flag in `cl.user_session`) prevents race conditions — Render's free tier is slow enough that a user could send a second message before the first response completes, which would cancel the first tool call mid-execution.

### Planning

Built into Deep Agents by default. The agent decomposes multi-part questions into steps before calling tools. When the GM asks "what's driving July and how did we book lately?", the agent creates a plan — get OTB summary, delegate segment mix to segment-analyst, delegate pickup to demand-analyst, synthesize — rather than firing one tool and stopping.

---

## 5. Skill → tool routing matrix and threshold calibration

| Skill | Primary tool(s) | Judgment |
|---|---|---|
| `otb_position` | `get_otb_summary` | ✅ Relative thresholds, 5 ADR scenarios |
| `pickup_and_pace` | `get_pickup_delta` + `get_otb_summary` | ✅ Pickup ADR vs OTB ADR signal, 5 volume scenarios |
| `segment_concentration` | `get_segment_mix` + `get_block_vs_transient_mix` | ✅ 6-layer answer pattern, 35% concentration flag |
| `channel_dependency` | `get_segment_mix` | ✅ OTA thresholds 15/25/40%, rate parity divergence |
| `concentration_risk` | `get_block_vs_transient_mix` | ✅ Top-3 share 30/50/70%, account vs block risk |
| `cancellation_patterns` | `get_otb_summary` + `get_pickup_delta` | ✅ Cancellation rate 8/15/25%, NET position principle |
| `group_block_management` | `get_block_vs_transient_mix` | ✅ Block share 30/50/70%, displacement reasoning |
| `rate_integrity` | `get_otb_summary` + `get_pickup_delta` | ✅ Hold vs flex decision framework |
| `point_in_time` | `get_as_of_otb` | ✅ HITL rationale, 4 use cases, trap warnings |
| `CHALLENGE_SKILL` | All tools | Version pin: `otel-rm-v2` |

### The biggest challenge — relative vs absolute thresholds

This was honestly the hardest part of the whole project. The brief says the thresholds are deliberately not given — discovering what an experienced revenue manager actually knows and encoding it is the challenge. So the first question we had to answer was: do we use absolute thresholds or relative ones?

The problem with absolute thresholds is that they dont scale. If I say "OTB is thin if room nights are below 100" — that makes no sense for a 200 room hotel vs a 50 room hotel. Grand Harbour has 3 room types from the lookup table but we dont actually know the full inventory size from the data alone. So any absolute number we put in a skill would be wrong as soon as the hotel changes size, or gets seasonal patterns we havnt seen yet.

The problem with purely relative thresholds is that they can miss real problems. If every month is bad, comparing bad to bad still looks fine relatively.

The decision we landed on was a hybrid approach — use relative thresholds as the primary signal and absolute industry heuristics as the secondary guard rail. So for OTB position, the primary question is "how does this month compare to the cross-month average?" and the secondary question is "does the absolute ADR look reasonable for a mid-market hotel in this region?" If both signals agree, the agent is confident. If they disagree, the agent flags the discrepancy and says both things.

For each skill the calibration went like this:

**`otb_position`** — the threshold problem here is "what counts as thin?" We couldn't use room nights as an absolute because we dont know the hotel's total inventory. So the skill uses the cross-month average of room nights as the baseline and flags anything more than 20% below that average as thin. The ADR bands (€180-200 healthy, below €180 concerning) are industry heuristics for a mid-market European city hotel — defensible but not derived from this hotel's own history.

**`channel_dependency`** — OTA thresholds at 15/25/40% came from thinking about commission math. A typical OTA charges 15-20% commission. At 15% OTA share the commission drag is manageable. At 25% you're looking at meaningful margin erosion. At 40% you've built structural dependency that is very hard to unwind. These numbers don't change based on hotel size — they're percentage of mix, so they scale automatically. This is one of the skills where absolute percentage thresholds actually make sense.

**`concentration_risk`** — top-3 share at 30/50/70% was the hardest to calibrate. A 30-room boutique hotel will naturally have higher top-3 concentration than a 300-room conference hotel just because of volume. We decided to keep it as percentage thresholds anyway because the risk logic is the same regardless of size — if 3 accounts control 70% of your revenue and one cancels, the month collapses. The absolute room count doesnt change that risk.

**`cancellation_patterns`** — 8/15/25% cancellation rate bands are industry consensus for flexible-rate OTA-heavy portfolios. The more important judgment here wasnt the threshold — it was the NET position principle. We spent a lot of time on this. A raw cancellation count is almost meaningless. If you have 10 cancellations but 20 new bookings in the same window, you're growing. If you have 3 cancellations and 1 new booking, you're bleeding. The skill teaches the agent to always compute net position before calling anything alarming.

**`group_block_management`** — block share at 30/50/70% is where we thought hardest about scalability. For a small hotel, even 30% block share means very few actual room nights locked into group contracts. For a large conference hotel, 30% block might be totally normal. The skill hedges this by telling the agent to always state the absolute room night count alongside the percentage — "65% block = 86 room nights in one contract" tells the GM something absolute that the percentage alone doesn't.

**`rate_integrity`** — the hold vs flex decision is inherently contextual. There is no absolute threshold for "hold rate." Instead the skill teaches a decision framework: what is the days-to-arrival (urgency), what is the pickup ADR vs OTB ADR (quality of incoming demand), and what is the month's position relative to average (how much room to move). The skill uses all three signals together rather than any single threshold.

### Scalability thinking

We thought a lot about what happens if Grand Harbour grows — more rooms, more months of history, different mix profile. The skills are designed to stay valid as the hotel scales because:

1. Most thresholds are percentages not absolute counts, so they scale with hotel size automatically
2. Where absolute numbers are used (like ADR bands), they're framed as "for a mid-market European city hotel" so the GM knows they need recalibrating for a different property
3. The relative threshold approach (cross-month average as baseline) means the skill learns from the hotel's own patterns over time — a summer-heavy hotel will automatically have different monthly baselines than an even-distribution hotel
4. The skills explicitly tell the agent to state the absolute number alongside every percentage so the GM can sanity check the math

The one thing that doesnt scale well is the 6-layer answer pattern in `segment_concentration` — it was calibrated for a hotel with a limited market code set. A 500-room conference hotel with 25 market codes would need a different breakdown structure. We flagged this in the skill as a known limitation.

OTB questions → `otb_position`. Pickup questions → `pickup_and_pace`. Mix questions → `segment_concentration`. Channel → `channel_dependency`. Group → `group_block_management` + `concentration_risk`. Historical → `point_in_time`.

---

## 6. Agent tests

The test suite has four files. `test_etl.py` verifies scrape completeness and fingerprint match. `test_tools.py` has 20 tests covering grain correctness (reservation count vs row count), cancellation filter behaviour, segment share arithmetic summing to 1.0, pickup window boundaries, and point-in-time inclusion logic. `test_skills.py` has structural tests — checks that threshold numbers are present in skill files, that tool names referenced in skills actually exist in `tools.py`, that the `otel-rm-v2` version pin is in `CHALLENGE_SKILL.md`. `test_agent.py` inspects the agent's source configuration — HITL present on `get_as_of_otb`, subagent routing correct, both subagents have the right tools assigned.

The skill and agent tests deliberately use no live LLM calls. Everything is static file inspection or graph introspection. This means they run in CI in under 10 seconds and dont burn API credits.

---

## 7. Deployment topology

```
Render (free tier)
├── Chainlit UI        :8000   (main port, public)
│   └── /health endpoint       (mounted on Chainlit's FastAPI app)
└── Health server      :8001   (secondary, internal)

Neon Postgres (eu-west-2) ← both servers read from same DB
```

`GET /health` returns `status`, `dataset_revision`, `row_hash`, `financial_status_posted_only_rows`, and `proof_committed_fingerprint` from the committed `etl/LOAD_PROOF.json`. The health endpoint is mounted directly on Chainlit's FastAPI app so it's accessible on the main port — Render only exposes one public port and the health server on 8001 is internal only.

API keys live in Render environment variables, never committed to git. `.env` is gitignored. The variable is named `HOTEL_DATABASE_URL` not `DATABASE_URL` — using the standard name activates Chainlit's built-in data layer which we dont want.

---

## 8. Threshold calibration note

All numeric thresholds in the skills are industry-consensus heuristics calibrated to mid-market hotel revenue management practice, not derived from Grand Harbour's own historical data — we only have one anchor date's worth of data, which is not enough to derive statistically reliable baselines. The thresholds are defensible starting points. The right long-term approach is to recalibrate them against 12+ months of this hotel's own patterns once that data is available. The skills are written to make this recalibration easy — all threshold values are explicitly stated in the skill text, so changing them is a one-line edit per skill.

---

## 9. Token and latency optimisation

After deploying to Render and running a full evaluation through LangSmith, I found two problems that werent visible from local testing.

The first was context accumulation. The evaluation script was running all 20 test questions on the same LangGraph thread. By question 10 the agent was seeing 41 messages of prior conversation before answering — which meant tokens were growing from 24k on question 1 to 226k on the morning briefing question. The fix was simple: each eval question now gets its own thread via `make_config(f"eval-{idx}")`. In the Chainlit UI each browser session already gets its own thread, so followup questions like "what about August?" still retain context within a session, but a new login starts fresh.

The second problem was worse and took longer to find. The Deep Agents task planner was spinning up a subagent task layer for almost every question — even simple single-tool ones like "which companies contribute most revenue?" That question only needs `get_top_companies` — one tool call. But the trace showed: AI writes task description → task agent executes tools → task result returned → main AI synthesizes. That's 3 LLM calls for a one-tool question, which is why segment mix questions were hitting 40-53k tokens when they should be 3-10k.

The fix was to change the system prompt from vague delegation rules to a specific routing table:

```
| OTA dependency / channel mix  | get_segment_mix            |
| Block vs transient             | get_block_vs_transient_mix |
| Top companies / concentration  | get_top_companies          |
| Pickup / pace / what changed   | get_pickup_delta           |
```

And the key instruction: "Call tools DIRECTLY. Do NOT delegate to subagents except for morning briefing." The subagents are now reserved only for morning briefings where true parallel analysis is needed. Everything else the supervisor handles directly.

Results after optimisation, measured across 20 eval questions:

| Question type | Before | After | Target |
|---|---|---|---|
| Segment mix | 40-53k tokens, 60-75s | 24-25k tokens, 14-18s | 3-10k tokens |
| Pickup analysis | 40-60k tokens, 60s+ | 23-24k tokens, 10-15s | 5-15k tokens |
| OTB summary | 24k tokens, 20s | 24k tokens, 11-20s | 2-8k tokens |
| Morning briefing | 226k tokens, 100s+ | 55k tokens, 58s | 10-25k tokens |

20/20 passing. Average latency dropped from 57.5s to 24.1s. Still some overhead from the skill loading system prompt which adds a fixed ~20k tokens per call — thats a Deep Agents framework cost, not something we can optimise without changing the framework.

The morning briefing is still 58s because it genuinely uses both subagents and does multiple tool calls. That's acceptable — a morning briefing is a complex question that deserves a thorough answer.

---

## 10. Out of scope

- **MCP server** — optional per brief; deprioritised in favour of deeper skills and correct tool correctness.
- **`run_sql` tool** — deliberately excluded; handing the model arbitrary SQL loses grain correctness and cancellation discipline.
- **Chainlit data layer** — disabled; agent uses `MemorySaver` checkpointer instead of a persistent DB-backed session store. `DATABASE_URL` renamed to `HOTEL_DATABASE_URL` to prevent Chainlit activating its data layer automatically.
- **Streaming tool calls** — agent uses `invoke()` not `astream()`; tool steps shown post-completion rather than live-streamed.
