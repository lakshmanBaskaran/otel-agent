---
name: channel_dependency
description: "Load when the GM asks about OTA, Booking.com, Expedia, direct bookings, channel mix, commission costs, or rate parity. Uses get_segment_mix to pull the OTA market_code share."
---

# Channel Dependency

## What it tells you
Every booking comes through a channel, and the channel decides how much commission we pay, how much control we have over the guest (their email, their data), how likely they are to cancel, and whether we can rebook them next year.

If we lean too hard on one channel, we're fragile. If that channel raises commissions, changes their algorithm, or has an outage, we bleed.

## The four channels in this dataset
- WEB — direct website (or OTA traffic flowing through it)
- REC — reception, phone
- EMA — email booking
- WAL — walk-in

Direct channels have zero commission unless the booking is OTA-mediated. The actual OTA detection lives in market_code, not channel_code — that's why I call get_segment_mix and look for market_code='OTA'.

## Why OTA is the enemy
- We pay 15-25% commission. A €200 room becomes €150-€170 in our pocket.
- We don't own the guest. Booking.com has their email, not us.
- We can't upsell them other products of the hotel.
- We can't market to them next year — they belong to the OTA's database.
- They cancel more. OTA flexible rates have higher wash rates.

Every OTA booking is a tax on the business.

## Why direct is the goal
- Zero commission
- We own the guest data
- Upsell potential at booking, check-in, and during stay
- Loyalty and repeat-booker potential
- Lower cancellation rate — direct bookers are more committed

## The thresholds I watch
These are room-night percentages, not revenue.

- Under 15% OTA → healthy. OTA is filling shoulder demand we wouldn't have filled directly.
- 15-25% → watch zone. Commission starts to eat.
- 25-40% → dependency forming. The direct funnel is weakening.
- Over 40% → addiction. We're paying to rent out our own rooms.

If revenue share is lower than room-night share (say OTA is 25% of RNs but 18% of revenue), that's OTA undercutting our rate — even worse.

## Signals to watch
- **Rate parity divergence** — if our direct rate is €200 and OTA shows €180 for the same room, guests will book through OTA every time and we pay commission for bookings we'd have gotten anyway.
- **Rising OTA share month-over-month** — the direct funnel is leaking. Check website conversion, marketing spend, brand visibility.
- **OTA cancellation rate spike** — our OTA traffic is shopping-shoppers, not bookers. They're holding inventory while comparing.
- **OTA pickup outpacing direct** — we're acquiring expensive customers. Sustainable for a week, dangerous for a quarter.

## Recommendations by pattern
- **High OTA share + low BAR bookings** — direct pricing isn't competitive. Drop BAR by 5% or run a "book direct" campaign with a perk like free breakfast or late checkout.
- **High OTA share + rate parity broken** — renegotiate OTA contracts to enforce parity, or pull off the worst-offending OTA temporarily.
- **Rising OTA share trend** — audit the direct funnel: website speed, mobile UX, booking widget conversion. The leak is usually here.
- **OTA cancellation spike** — move OTA distribution to non-refundable rates only. Trade flexibility for commitment.

## The trap
Low OTA share isn't automatic success. If OTA is 8% but total RNs are also low, that's no business — not winning at distribution. Always cross-check OTA share against absolute volume.

And don't try to kill OTA entirely. OTA is a cost-of-acquisition channel that fills shoulder demand we wouldn't fill ourselves. Going from 12% OTA to 0% by pulling off Booking.com usually loses 8-10% of total revenue with no direct backfill. The question is never "should we use OTA?" — it's "are we leaning on it too hard?"

## How this connects to other skills
- Cancellation patterns — OTA cancels more, so the recommendations here affect cancellation rate
- Segment concentration — OTA sits inside macro_group=Retail
- Rate integrity — parity issues drive OTA dependency
- Pickup analysis — pickup channel mix tells you which way the trend is moving