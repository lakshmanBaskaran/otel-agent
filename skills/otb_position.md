---
name: otb_position
description: "Load when the GM asks about revenue on the books, OTB, how a month is looking, monthly performance, or how we're tracking. Uses get_otb_summary."
---

# Reading the Forward Book

## What OTB really is
On the books = confirmed forward pipeline. Bookings that exist right now for future stay dates, excluding cancellations and provisional rows.

It's the GM's most-asked question: "how are we tracking?"

## OTB alone is meaningless
The amateur mistake: report €30K OTB for July and stop there. That number is useless without context. Is €30K good or bad?

OTB makes sense only when compared:
- **Versus other months** — is July healthier than June? Stronger than August?
- **Versus pace expectation** — at 60 days out, should we be at €30K or €50K?
- **Versus last year same period** — were we at €30K this time last July?

This dataset only supports the first comparison (no historical year, no pace targets). Month-vs-month is the primary lens.

## The three numbers always travel together
Reporting OTB means reporting all three:
- **Room nights** — units of inventory consumed
- **Revenue** — total or room-only depending on question
- **ADR** — revenue divided by room nights

Any one alone misleads. €30K tells you nothing if you don't know whether that's 100 RNs at €300 ADR or 300 RNs at €100 ADR. Same revenue, totally different business.

## The ADR trap
ADR = total_revenue / room_nights, NEVER revenue / row_count.

row_count is stay rows, not bookings. A 3-night booking creates 3 rows but is 1 reservation. Dividing by rows would only be approximately correct if every booking were exactly 1 night with 1 room — they're not.

Always use room_nights (sum of number_of_spaces) as the ADR denominator.

## Reading thin vs healthy
This dataset is small, so absolute thresholds like "under €30K is thin" don't generalize. Use relative comparison instead.

Compute the cross-month average across all future months, then read each month against it:
- Below 50% of average → thin, urgent attention
- 50-80% of average → soft, build pace
- 80-120% of average → healthy
- Over 120% of average → peak, protect rate

The cross-month average self-calibrates to whatever dataset you're in.

## Lead time context
A month 7 days out and a month 90 days out are not comparable. Naturally:
- **Current month** — partially historical, room to grow is short
- **Next 30 days** — pickup window is closing, OTB should be most of final number
- **30-60 days** — heavy pickup window, OTB should be 60-80% of final
- **60-90 days** — building phase
- **90+ days** — early days, OTB is just the floor

A "thin" month 90 days out is normal. A "thin" month 14 days out is an emergency.

## ADR signals
- **ADR rising month-to-month** → mix shifting toward higher-rate segments, or rate strategy holding firm
- **ADR falling month-to-month** → mix shifting toward lower-rate segments (OTA, PROM, group), or discounting to fill volume
- **ADR stable, room nights falling** → demand contraction without rate response. Rate might be correct, market is soft.
- **Room nights stable, ADR falling** → discounting is working — filling rooms but eroding margin. Risky if it becomes habit.
- **Both falling** → trouble. Demand and rate weakening together.
- **Both rising** → ideal. Strong demand at firm rate.

## The hidden risk: high OTB but concentrated
A "healthy" OTB number can hide concentration risk. If August OTB is €40K but 70% comes from one conference group, it's not healthy — it's hostage. Always layer OTB with concentration analysis before declaring a month "looking good."

## The trap: rows are not reservations
This is the single most common hotel data error. get_otb_summary returns both row_count and reservation_count specifically so you can't confuse them.

- **Stay rows** = nights consumed (one per reservation × stay_date)
- **Reservation count** = distinct bookings
- **Room nights** = sum of number_of_spaces (accounts for multi-room bookings)

Never report row_count as "bookings."

## Recommendations summary
- **Thin month < 30 days out** → urgent. Promo rates, push direct, flash discounts on dead dates.
- **Thin month 30-60 days out** → time to build. Corporate sales, group acceptance, marketing spend.
- **Thin month 60+ days out** → wait. Watch pickup over next 2 weeks.
- **Peak month + healthy ADR** → protect rate. Close cheap codes (PROM, OTA discounts).
- **Peak month + weak ADR** → diagnose mix, don't blame demand.
- **High OTB with concentration** → confirm dependencies, request deposits. One cancellation kills the picture.

## How this connects to other skills
- Pickup and pace — OTB is the snapshot, pickup is the velocity. Read together.
- Concentration risk — high OTB without concentration check is a false positive.
- Segment concentration — what's IN the OTB matters as much as how much.
- Rate integrity — ADR signals trace back to rate strategy decisions.
- Channel dependency — OTB mix tells you whether channel strategy is working.