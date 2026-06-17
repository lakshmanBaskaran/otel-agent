---
name: cancellation_patterns
description: "Load when the GM asks about cancellations, cancelled bookings, lost business, cancellation rate, or wash. Pairs get_otb_summary (exclude_cancelled=False) with get_pickup_delta to show net position."
---

# Cancellation Patterns

## What it tells you
Cancellations are lost revenue, but more importantly they're a signal. Maybe something is wrong with our rate policy, guest experience, or demand strength.

A hotel with 5% cancellation rate has tight policies and committed bookers. A hotel at 20% is risky — could be guest commitment, loose policies, or bad hospitality. Everything contributes.

## The single most important rule
Never show gross cancellations. Always show net position.

"Lost €5K to cancellations, but picked up €8K in new bookings. Net is +€3K."

The GM doesn't care that we lost €5K. They care that the book grew by €3K. This is the mistake a lot of analysts make — they lead with the €5K and watch the GM panic for no reason.

Pair every cancellation answer with get_pickup_delta for the same window.

## The two-universe problem
Default OTB (vw_stay_night_base) excludes cancelled AND provisional rows. That's correct for "what's on the books," wrong for cancellation analysis.

When the question is about cancellations, flip the switch — get_otb_summary with exclude_cancelled=False includes cancelled rows. Compare against the default to find the cancelled population. Provisional stays excluded either way — they're tentative holds, not committed business that someone cancelled.

## The thresholds I watch (room-night ratio)
- Under 8% → normal noise, no action needed
- 8-15% → starting to bleed, find the source segment
- 15-25% → policy problem, rate plans are too flexible
- Over 25% → emergency, we're booking phantom business

Room nights, not revenue. Revenue can mask volume problems.

## Where the wash hides
- **OTA flexible rates** — zero cost to the guest, they hold inventory while shopping. If OTA is 20% of bookings but 40% of cancellations, the policy is the leak.
- **Group blocks** — these don't cancel outright, they shrink. A 30-room block becomes 25, then 22. Check block room nights week over week, not just cancellation count.
- **Long lead time bookings** — anything booked 60+ days out is higher risk. Plans change. Bookings under 14 days almost never cancel.
- **Corporate negotiated rates** — companies sometimes overbook for events and release rooms back. Less risky than OTA but worth watching.

## Recommendations by pattern
- **High OTA cancellations** → push non-refundable rates with a 10-15% discount as the trade-off
- **Group block shrinking** → tighter attrition clauses, deposit requirements
- **One month over-exposed** → overbooking buffer of 5-8% to absorb expected wash
- **Rising trend month-over-month** → rate strategy is wrong, not operations
- **Cancellations stable but pickup falling** → demand problem, not policy problem

The last one is the most important diagnostic. Separating policy issues from demand issues is what makes an RM useful.

## The trap
When the GM panics about a cancellation number, the first three questions are always:
1. What's the same-window pickup?
2. What's the net?
3. Is the rate accelerating or stable?

Only after those three do I bring up segment patterns. Otherwise I'm feeding the panic instead of solving it.

## How this connects to other skills
- Channel dependency — OTA cancels more, ties to commission analysis
- Group block management — block wash mechanics live there
- Pickup and pace — net position calculation requires pickup data
- Rate integrity — flexible rates drive cancellations; policy questions trace back here