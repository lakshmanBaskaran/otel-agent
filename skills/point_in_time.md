---
name: point_in_time
description: "Load when the GM asks about historical OTB position, what the book looked like at a past date, forecast accuracy, or as-of analysis. Uses get_as_of_otb (HITL-gated)."
---

# Point-in-Time OTB

## What it does
Rebuilds the book as it looked at a past timestamp. Time travel for the data.

Other tools answer "what's the book now?" This one answers "what did the book look like THEN?"

## When to use it
- **Forecast accuracy** — what did we forecast 30 days ago vs what did we actually get?
- **Pre-event snapshot** — freeze numbers before sending a board report so the audit trail is reproducible
- **Wash diagnosis** — snapshot two dates, the difference minus pickup = cancellation patterns
- **Pace check** — compare snapshots over time to see if pickup is matching expectations

## How it filters
A row is included if all three are true:
- Booking existed by that date (create_datetime <= as_of)
- Booking wasn't cancelled yet (cancellation came after as_of, or never)
- Posted only — provisional rows always excluded

## The clever bit
A row marked "Cancelled" today might have been active in the past. You can't filter on current status — you have to check WHEN the cancellation happened.

## Why HITL-gated
- Expensive query — queries the raw table, not the pre-filtered view
- Easy to misuse — the agent might call this on simple questions where get_otb_summary is the right tool
- Easy to misread — the GM sees an old number and thinks it's current

The gate forces the agent to explain what it's about to do, and the GM confirms or clarifies.

## Don't use this for
- Current OTB questions — use get_otb_summary instead
- Today's timestamp — defeats the purpose
- Vague references like "a while ago" — clarify the date first before running

## The trap
Comparing two snapshots without showing cancellations in that window.

"+€7K" looks like pickup, but if €3K washed during that window, real pickup was €10K. Always show both sides — be transparent with the data.

## Frame every comparison with three things
1. Both timestamps stated explicitly
2. Pickup AND wash for the window
3. Whether the change matches expected pace for the time elapsed

## How this connects to other skills
- OTB position 
- Cancellation patterns 
- Pickup and pace 
- Rate integrity 