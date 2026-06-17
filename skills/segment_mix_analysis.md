---
name: segment_concentration
description: "Load when the GM asks what's driving a month, segment mix, who's contributing revenue, retail vs corporate vs group composition, or market breakdown. Uses get_segment_mix and get_block_vs_transient_mix."
---

# Segment Concentration

## Why segment mix matters
Revenue is a blend of different guest types. Each has different booking behavior, rate sensitivity, and cancellation risk. A healthy hotel has a diversified mix. Over-reliance on any single segment is a risk.

## How to analyze
1. Call get_segment_mix for the specific month to see the breakdown
2. Call get_block_vs_transient_mix for the high-level group vs transient split
3. Compare across months — does the mix shift significantly?

## The segment hierarchy (macro groups)
- **Retail** — OTA, BAR, PROM, FIT. Individual guests, price-sensitive, higher cancellation
- **Corporate** — CSR, CNR. Negotiated rates, stable demand, lower cancellation
- **MICE** — CNI (conference/incentive), CGR (corporate group). Large blocks, high revenue but concentrated risk
- **Leisure/Event** — EVEN, SMERF. Event-driven, can be large but one-time

## What a healthy mix looks like
- No single segment over 30% of revenue (diversification)
- Corporate base of 15-25% provides stability
- Retail (OTA + BAR + PROM) at 25-35% for rate integrity
- Group (MICE + SMERF) at 20-30% for volume — but watch concentration

## What to flag
- **Any segment over 35% of a single month** → concentration risk for that month
- **Corporate under 10%** → missing stable base business
- **SMERF or CNI over 30%** → a few group cancellations could devastate that month
- **OTA is the largest segment** → rate erosion and commission bleed
- **BAR is tiny** → direct retail pricing isn't working

## How to answer "what's driving July?"
This is a classic question. Answer in layers:
1. Total revenue and room nights for the month
2. Top 3 segments by revenue with share percentages
3. Group vs transient split
4. ADR by segment — who's paying the best rate?
5. Flag any segment with outsized concentration
6. Check pickup — is the dominant segment still growing?

Be transparent. Check all the layers before reaching a conclusion.

## Recommendations
- **Over-concentrated in group** → "If X cancels we lose €Y. Backfill: activate OTA promo rates 30 days out as insurance."
- **Weak corporate** → "Sales team should target 3-5 mid-week corporate accounts to stabilize the base."
- **Strong BAR ADR vs OTA** → "BAR guests are paying €X ADR vs €Y OTA. Every booking shifted from OTA to direct saves the commission delta per room night."
- **MICE-heavy with one dominant account** → confirm deposit, secure attached F&B revenue
- **Diversified mix, soft volume** → demand problem not concentration problem

## The trap
A "healthy" mix at the macro level can hide single-account concentration inside one segment. If MICE is 25% of the month but it's all one conference, the macro group looks fine while account concentration is severe. Always layer segment analysis with concentration_risk for the full picture.

## How this connects to other skills
- Concentration risk — segment mix is the first layer, account concentration is the second
- Group block management — when group is the dominant segment, those mechanics apply
- Channel dependency — OTA share in retail mix triggers channel analysis
- Rate integrity — segment ADR comparison reveals rate strategy effectiveness
- Pickup and pace — pickup by segment shows where momentum lives