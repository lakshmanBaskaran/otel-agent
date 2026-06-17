---
name: rate_integrity
description: "Load when the GM asks about rate strategy, discounting, when to hold rate or flex, promo decisions, or pricing pressure. Uses get_otb_summary and get_pickup_delta."
---

# Rate Integrity

## What it means
Not discounting unless you have to. Holding rate as long as possible. Once you flex, every booking locks in at the lower rate — you can't un-discount.

## Three factors in the decision
1. **Demand strength** — peak, healthy, soft, or thin? (get_otb_summary)
2. **Days to arrival** — far-out has time, near-term doesn't
3. **Pickup trend** — accelerating or fading? (get_pickup_delta)

Consider the season too. Off-peak months tolerate softer rates; peak months should hold harder.

## Hold rate when
- Peak month + strong pickup
- Pickup ADR coming in above OTB ADR
- Direct channels still active
- Near arrival with healthy fill

## Flex when
- Thin month + close to arrival
- Pickup stalled for 2+ weeks
- Cancellations not being replaced
- Distressed inventory

## The asymmetry
Holding too long costs you a few empty rooms. Discounting too early costs you margin on every booking that follows. Holding is the safer error.

Be proactive — diagnose the situation from the data before reaching for the promo button.

## Common patterns
- Peak month strong → close discount codes, push BAR
- Healthy month, mid-term → hold rate, don't act
- Shoulder month, soft → selective promo, never blanket
- Near-term distressed → flash promo with strict end date
- Far-out thin (60+ days) → don't discount yet, watch pickup

## The trap
Discounting too early. Once a promo opens, every booking books at that rate until you close it. The "early discount" myth assumes you can reclaim rate later — you usually can't.

## Diagnostic checks before flexing
1. Is pickup ADR actually below OTB ADR, or just volume soft?
2. Is the segment mix already shifting toward discount channels?
3. What's the cancellation pace — am I losing rate AND volume together?

## Recommendations
- Strong demand → hold or raise rate, close cheap codes
- Soft demand, far-out → wait and watch, don't act yet
- Soft demand, near-term → selective promo with time limit
- Distressed near-term → flash discount, strict end date
- Don't discount 60+ days out without data justifying it

## How this connects to other skills
- Pickup and pace — pickup ADR vs OTB ADR is the core rate integrity signal
- Channel dependency — rate parity drives OTA pressure
- OTB position — demand context dictates rate posture
- Cancellation patterns — flexible rates drive wash