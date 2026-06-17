---
name: segment_concentration
description: "Load when the GM asks what's driving a month, segment mix, market breakdown, who's contributing revenue, or which segments dominate. Uses get_segment_mix and get_block_vs_transient_mix."
---

# Segment Concentration

## What segment mix tells you
The breakdown of revenue by market code. Which source is giving what amount of revenue to the hotel. Use get_segment_mix with the stay_month — the tool returns shares that sum to 1.0, so share_of_revenue and share_of_room_nights are the comparison numbers.

## Macro groups matter more than individual codes
Look at the macro groups first — Retail, Corporate, MICE, Leisure Group. Individual codes (OTA, BAR, PROM, CNI, etc.) only matter once you understand the high-level picture.

Use the macro_group filter on get_segment_mix to isolate a single group when needed.

## What a healthy mix looks like
A relatively even share across the macro groups. No single segment should be dominating. If one segment's share_of_revenue is over 35%, that month has concentration risk.

## Red flags
- Any single segment taking an outsized share compared to the others
- Corporate barely present → missing stable base business for midweek
- BAR is tiny → direct retail pricing isn't competitive
- OTA is the largest segment → rate erosion and commission bleed
- MICE dominant with one company driving it → group concentration risk

## How to answer "what's driving July?"
This is the classic GM question. Answer in layers:

1. Total revenue and room nights for the month (get_otb_summary)
2. Top 3 segments by revenue share (get_segment_mix)
3. Group vs transient split (get_block_vs_transient_mix)
4. Flag any outsized concentration
5. Be transparent — check all the data before reaching a conclusion
6. Check pickup — is the dominant segment still growing?

Don't skip layers. Going straight to "MICE is 50%" without the total context loses the GM.

## Recommendations
- **Over-concentrated in group** → "If X cancels we lose €Y. Backfill plan needed."
- **Weak corporate** → "Sales team should target more corporate accounts for midweek."
- **Strong BAR ADR vs OTA** → "Shift mix toward direct. Each booking saved is commission saved."
- **OTA dominant** → "Channel funnel is leaking — see channel_dependency skill."
- **MICE-heavy, one company driving it** → confirm deposit, secure attached F&B
- **Diversified mix but soft volume** → demand problem, not concentration problem

## The trap
A "healthy" macro mix can hide single-account concentration inside one segment. If MICE is 25% of the month but it's all one conference, the macro group looks fine while the account risk is severe. Always cross-check segment analysis with concentration_risk for the full picture.

## How this connects to other skills
- Concentration risk — segment mix is the first layer, account concentration is the second
- Group block management — when MICE is dominant, those mechanics apply
- Channel dependency — OTA share in retail mix triggers channel analysis
- Rate integrity — segment ADR comparison reveals rate strategy effectiveness
- Pickup and pace — pickup by segment shows where momentum lives