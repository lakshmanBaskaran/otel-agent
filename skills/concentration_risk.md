---
name: concentration_risk
description: "Load when the GM asks about concentration risk, dependency on large bookings, whether business is diversified, top accounts, or whether a few bookings dominate revenue. Uses get_block_vs_transient_mix."
---

# Concentration Risk

## What it tells you
How much of our revenue depends on a small number of bookings, accounts, or segments. Opposite is diversification.

A hotel where top 3 accounts amount to 25% of revenue is healthy. A hotel where top 3 customers contribute 70% of revenue is one phone call away from disaster.

The GM should care about this because forecasts only matter if the underlying bookings are stable. A "great month" where 70% of revenue comes from a single account isn't a great month — it's a hostage situation.

## Two different concentration risks (don't conflate them)
**Account concentration** — top 3 customers' share of revenue. Risk: one customer pulls out, we lose 20-30% of the month.

**Block concentration** — group business as share of total, measured by block_share_of_revenue. Risk: groups cancel or shrink, we lose anchor business.

These measure different things:
- A hotel can have 50% block share spread across 10 small groups → low account risk, moderate block risk
- A hotel can have 50% transient share but all from one corporate account → high account risk, low block risk
- The dangerous combination is both high — heavy group AND concentrated in one account

## The thresholds I watch

**Account concentration (top 3 share of revenue):**
- Under 30% → healthy, well-diversified
- 30-50% → watch zone, identify the top accounts
- 50-70% → exposed, need backfill plans
- Over 70% → severe, the month is hostage to a few clients

**Block concentration (block share of revenue):**
- Under 30% → transient-heavy, normal city hotel
- 30-50% → balanced mix
- 50-70% → group-dependent, vulnerable to wash
- Over 70% → conference hotel mode, very high risk if any block shrinks

## Where concentration matters most
**Quiet months** — concentration risk is amplified. If OTB is already thin and 60% is one account, that account cancelling flatlines the month.

**Peak months** — matters less because there's time to backfill. 70% top-3 with 30 days of lead time and strong transient pickup gives options.

**Last-minute months** — critical. If current month is 60% one account with 10 days left, no time to backfill if they cancel.

## Always quantify the exposure
Don't just say "concentration is high." Say what the loss looks like in numbers.

**Weak:** "August has high concentration risk."
**Strong:** "If TechSummit cancels, we lose 30 RNs and €27K — roughly 40% of August. We have 25 days of pickup runway to backfill."

The GM needs the dollar amount and the time runway. That's what makes the risk actionable.

## Recommendations by pattern
- **High top-3 + high block** → confirm commitments now, request deposits, lock in attrition clauses before lead time runs out
- **High top-3 + corporate transient** → diversification push, sales team targets new accounts in adjacent industries
- **High block share spread across many groups** → group risk pooled, OK for now but watch attrition clauses
- **One group dominating a month** → run get_as_of_otb to see how this account's commitment has changed over time. Growing or shrinking?
- **Low concentration + low volume** → focus on ADR, not volume. Diversification is healthy; demand isn't.

## The trap
Concentration is not automatically bad. Group business is valuable — predictable, books early, fills the calendar. The GM's job isn't to eliminate concentration. It's to:
1. Know who the hotel depends on
2. Understand what they need so they don't leave
3. Have a plan if they cancel

A skill that says "high concentration is bad, diversify" is useless. A skill that says "here's the exposure, here's the runway, here's the action" is what makes the agent useful.

## The honest limit
get_block_vs_transient_mix returns top 3 companies — account concentration is capped at top 3. For this dataset that's enough; the data is small and concentrated enough that top 3 captures the risk picture.

## How this connects to other skills
- Group block management — block share threshold lives there in detail
- Cancellation patterns — concentrated accounts cancelling = bigger NET hit
- OTB position — concentration matters more in thin months
- Pickup and pace — backfill runway is the pickup question