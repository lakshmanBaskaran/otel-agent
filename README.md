# Hotel Hackathon Dataset
## Revenue Manager Agent Challenge

## Quick start

```bash
docker compose up
```

This starts Postgres on port `5432` with:

- database: `hotel_hackathon`
- user: `hackathon`
- password: `hackathon`

Connection string:

```
postgresql://hackathon:hackathon@localhost:5432/hotel_hackathon
```

### Files
- `schema.sql` - creates the tables
- `seed.sql` - loads lookup data and the reservation dataset
- `docker-compose.yml` - boots a local Postgres instance

---

## 1. What this dataset is for

This dataset is designed for a hackathon challenge where teams build a **Revenue Manager Agent for a hotel General Manager (GM)**.

Build a **Revenue Manager Agent for a Hotel General Manager**.

Using reservation data, detect what is changing in future business - pickup, cancellations, segment mix, and emerging risks or opportunities - and turn it into clear commercial judgment.

Show the GM what matters most, why it matters, and what action they should take next.

The agent should handle natural-language business questions such as:

- What revenue is on the books by month?
- What is driving July?
- Are we too dependent on OTA?
- How much business was cancelled in June?
- Which room type has the highest ADR?
- How much group business do we have?
- What changed in the last 7 days for future stays?

The agent should be able to:
1. understand the question,
2. query the dataset correctly,
3. return the answer in plain English,
4. explain the main drivers,
5. show numbers clearly,
6. mention assumptions or caveats when needed.

---

## 2. Important business context

This dataset comes from a hotel reservations context, but it has been simplified for the hackathon.

You do **not** need to know hotel industry jargon in advance. This guide explains the business concepts and table meanings.

### Core idea
A hotel sells rooms for specific stay dates.

A reservation might be:
- created long before arrival,
- cancelled before arrival,
- direct or OTA,
- transient or group,
- one room or multiple rooms.

This dataset is designed to help a GM understand:
- business on the books,
- booking pace,
- segment mix,
- room type mix,
- cancellations,
- concentration risk,
- group vs transient demand.

---

## 3. Dataset overview

The dataset currently contains:

- **4 tables**
- **455 rows** in the main fact table: `reservations_hackathon`
- lookup tables for room types, market segments, and channels

### Tables
- `public.reservations_hackathon`
- `public.room_type_lookup`
- `public.market_code_lookup`
- `public.channel_code_lookup`

---

## 4. The most important concept: table grain

### `reservations_hackathon` is **not** one row per reservation

It is:

**one row per reservation x stay_date**

That means:
- if a reservation stays 3 nights, it creates 3 rows
- if a reservation has multiple rooms, `number_of_spaces` tells you how many rooms are attached
- counting rows is **not** the same as counting reservations

This is the single most important thing to understand.

### Example
A guest books 2 rooms for 3 nights.

That creates:
- 3 rows in `reservations_hackathon`
- each row has `number_of_spaces = 2`

So:
- **reservation count** = 1
- **stay rows** = 3
- **room nights** = 6

---

## 5. Business concepts

### Reservation
A hotel booking.

### Stay date
The actual night being stayed.

### Arrival date
The date the guest checks in.

### Departure date
The date the guest checks out.

### Booking date
When the reservation was created. In this dataset, that is `create_datetime`.

### OTB / On-the-books
Business that currently exists in the reservation data for future stay dates.

### ADR
Average Daily Rate. In simplified terms, revenue per room night.

### Room nights
How many rooms are occupied across nights.  
Example:
- 1 room for 3 nights = 3 room nights
- 2 rooms for 3 nights = 6 room nights

### OTA
Online Travel Agency, such as Booking.com or Expedia.

### Direct
Business that comes directly through the hotel’s own website / reservations / walk-ins.

### Group business
Reservations tied to a conference, corporate group, event, or similar multi-room booking.

### Transient business
Normal individual bookings, usually not group blocks.

### Lead time
Days between booking creation and arrival date.

---

## 6. Table reference

## 6.1 `public.reservations_hackathon`

This is the main fact table.  
Almost all GM questions will be answered primarily from this table.

### Row grain
**One row per reservation x stay_date**

### Columns

#### `reservation_stay_id`
- Type: `bigint`
- Primary key
- Unique row identifier for this table

#### `reservation_id`
- Type: `text`
- Reservation identifier
- Multiple rows can share the same `reservation_id` if the reservation spans multiple nights

#### `arrival_date`
- Type: `date`
- Guest check-in date

#### `departure_date`
- Type: `date`
- Guest check-out date
- The guest stays up to, but not including, this date

#### `stay_date`
- Type: `date`
- The specific night represented by this row
- This is the most important date for revenue-on-stay analysis

#### `reservation_status`
- Type: `text`
- Example values include:
  - `Reserved`
  - `Cancelled`
- Use this carefully in analysis
- Many business questions should exclude cancelled reservations unless explicitly asked

#### `create_datetime`
- Type: `timestamptz`
- When the reservation was created
- Use this for:
  - booking pace
  - pickup analysis
  - “as of” views
  - “what changed recently?”

#### `cancellation_datetime`
- Type: `timestamptz`, nullable
- When the reservation was cancelled
- Only populated for cancelled reservations

#### `guest_country`
- Type: `text`, nullable
- Guest country code / nationality grouping
- Can be used for mix analysis

#### `is_block`
- Type: `boolean`
- Whether this booking is treated as a block / group-style reservation

#### `is_walk_in`
- Type: `boolean`
- Whether the booking was a walk-in

#### `number_of_spaces`
- Type: `integer`
- Number of rooms on this reservation for that stay date
- In hotel language, “spaces” here effectively means rooms
- Important for room-night calculations

#### `space_type`
- Type: `text`
- Room type code
- Join to `room_type_lookup`

#### `market_code`
- Type: `text`
- Market / segment code
- Join to `market_code_lookup`

#### `channel_code`
- Type: `text`
- Booking channel code
- Join to `channel_code_lookup`

#### `source_name`
- Type: `text`
- Human-readable booking source
- Examples:
  - Booking.com
  - Expedia
  - Brand website
  - OCC Central Reservations
  - Walk-in

#### `rate_plan_code`
- Type: `text`
- Rate code / pricing plan attached to the booking
- Examples:
  - `BOOKBAR`
  - `GROUPBB`
  - `DLY1`
  - `FITBB`
- Useful for pricing / commercial analysis, but not required for all questions

#### `daily_room_revenue_before_tax`
- Type: `numeric`
- Room revenue for this row’s stay date before tax
- Use this when the question is specifically about room revenue

#### `daily_total_revenue_before_tax`
- Type: `numeric`
- Total revenue for this row’s stay date before tax
- Includes room revenue and potentially package / breakfast effects in the synthetic dataset
- Use this for broader revenue questions

#### `nights`
- Type: `integer`
- Length of stay of the reservation
- Repeated on each stay-date row belonging to the same reservation

#### `adr_room`
- Type: `numeric`
- Room ADR for the reservation
- Repeated across the stay rows of the reservation

#### `lead_time`
- Type: `integer`
- Number of days between booking creation and arrival
- Useful for pickup and booking-window analysis

#### `company_name`
- Type: `text`, nullable
- Company associated with the reservation, especially for corporate / group business

#### `travel_agent_name`
- Type: `text`, nullable
- Travel agent name when relevant

---

## 6.2 `public.room_type_lookup`

Lookup table for room type codes.

### Grain
One row per room type code.

### Columns

#### `space_type`
- Type: `text`
- Primary key
- Join key from `reservations_hackathon.space_type`

#### `room_class`
- Type: `text`
- Broad class of room
- Example:
  - Standard
  - Executive

#### `display_name`
- Type: `text`
- Human-friendly room type name

#### `number_of_rooms`
- Type: `integer`
- Number of physical rooms of this type in the hotel
- Useful context for supply / mix analysis

---

## 6.3 `public.market_code_lookup`

Lookup table for business segment / market codes.

### Grain
One row per market code.

### Columns

#### `market_code`
- Type: `text`
- Primary key
- Join key from `reservations_hackathon.market_code`

#### `market_name`
- Type: `text`
- Human-readable segment name

#### `macro_group`
- Type: `text`
- Broader grouping of the segment
- Examples:
  - Retail
  - Corporate
  - MICE
  - Leisure
  - Leisure Group

#### `description`
- Type: `text`
- Plain-English description of the market code

### Included market codes
- `OTA` = Online Travel Agency
- `BAR` = Best Available Retail
- `PROM` = Promotional Retail
- `FIT` = Free Independent Traveller
- `CSR` = Corporate Negotiated
- `CNR` = Corporate Room Nights
- `CNI` = Conference / Incentive Group
- `CGR` = Corporate Group
- `EVEN` = Event Demand
- `SMERF` = SMERF Group

---

## 6.4 `public.channel_code_lookup`

Lookup table for booking channels.

### Grain
One row per channel code.

### Columns

#### `channel_code`
- Type: `text`
- Primary key
- Join key from `reservations_hackathon.channel_code`

#### `channel_name`
- Type: `text`
- Human-readable channel name

#### `channel_group`
- Type: `text`
- Broad grouping of the channel
- Examples:
  - Digital
  - Direct
  - Offline

### Included channel codes
- `WEB`
- `REC`
- `EMA`
- `WAL`

---

## 7. Relationship diagram

### Main joins

#### Room type
`reservations_hackathon.space_type = room_type_lookup.space_type`

#### Market segment
`reservations_hackathon.market_code = market_code_lookup.market_code`

#### Channel
`reservations_hackathon.channel_code = channel_code_lookup.channel_code`

---

## 8. Common pitfalls

## 8.1 Do not confuse rows with reservations
Counting rows is not the same as counting bookings. Think about what the correct approach is.

---

## 8.2 Do not confuse reservations with room nights

A reservation can cover multiple rooms. Make sure your room-night calculation accounts for this.

---

## 8.3 Be careful with cancelled bookings

Think about whether cancelled reservations should be included or excluded depending on the question being asked.

---

## 8.4 Know which date you are using

The dataset has multiple date fields. Make sure you use the right one for the question. Using the wrong date can produce a logically wrong answer even if the SQL runs.

---

## 8.5 Know which revenue field you need

There are two revenue columns in the dataset. Understand what each one represents and choose the right one for the question.

---

## 9. Business definitions and semantic clarity

A strong solution will define business metrics explicitly instead of improvising them every time. Your agent should have clear, consistent definitions for concepts like reservation count, room nights, revenue, ADR, and segment groupings.

How you define and group these is part of the challenge.

---

## 10. Why a semantic layer is a strong idea

Direct natural-language to SQL can be error-prone.

A strong team may create a semantic layer that defines:

* business metrics,
* default filters,
* dimension mappings,
* standard business rules.

This is powerful because it reduces common mistakes like:

* counting rows instead of reservations,
* mixing room revenue and total revenue,
* forgetting cancelled rows,
* confusing stay date and booking date.

A semantic layer is **not required**, but it is a strong differentiator and should score well if implemented clearly.

---

## 11. Example questions

These are the kinds of questions the Revenue Manager agent should handle.

### Examples

* What revenue is on the books by month?
* Which segments are driving July?
* How much of July is group business?
* Are we too dependent on OTA?
* What changed in the last 7 days for future stays?
* Which room type is generating the highest ADR?
* How much business was cancelled in June?
* What share of our future business is corporate?
* Which companies are contributing the most revenue?
* Is our business concentrated in a few large bookings?

---

## 12. Answer style

A good answer is not just raw SQL output. A weak answer names a single metric. A strong answer explains the drivers, quantifies the key numbers, highlights risks or opportunities, and speaks in language a GM would trust.

Think: what would a sharp revenue manager say in a morning briefing?

---

## 13. Final advice for teams

1. Decide whether the question is about stay date or booking date.
2. Be explicit about whether cancelled reservations are included.
3. Prefer clear business definitions for metrics like bookings, room nights, and revenue.
4. Return answers in plain English, not just raw query output.
5. When there is ambiguity, state your assumption.

---

## 14. Quick reference

### Main fact table

`reservations_hackathon`

### Lookup tables

* `room_type_lookup`
* `market_code_lookup`
* `channel_code_lookup`

---

## 15. Dataset shape

* `room_type_lookup`: 3 rows
* `market_code_lookup`: 10 rows
* `channel_code_lookup`: 4 rows
* `reservations_hackathon`: 455 rows

---

## 16. Challenge objective

Build a **Revenue Manager Agent for a Hotel General Manager** that uses reservation data to detect what is changing in future business, turn it into clear commercial judgment, and recommend what action to take next.
