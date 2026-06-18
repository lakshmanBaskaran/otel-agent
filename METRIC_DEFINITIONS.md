# Metric Definitions

This document defines all business metrics exposed by the Revenue Manager Agent tools.

## Data Scope

Unless otherwise specified, metrics are calculated from `vw_stay_night_base`, which contains:

* `financial_status = 'Posted'`
* `reservation_status <> 'Cancelled'`

Metrics are calculated at the **stay-night grain** (one row per reservation × stay_date).

---

# Core Definitions

## Stay Row

A single reservation for a single stay date.

Example:

| Reservation | Stay Date  |
| ----------- | ---------- |
| R1001       | 2026-07-01 |
| R1001       | 2026-07-02 |
| R1001       | 2026-07-03 |

This reservation contributes:

* 1 reservation
* 3 stay rows

---

## Reservation Count

Number of distinct `reservation_id` values.

Formula:

```sql
COUNT(DISTINCT reservation_id)
```

---

## Room Nights

Total occupied room inventory represented by reservations.

Formula:

```sql
SUM(number_of_spaces)
```

Calculated at stay-night grain.

---

## Room Revenue

Room-only revenue before tax.

Formula:

```sql
SUM(daily_room_revenue_before_tax)
```

---

## Total Revenue

Total revenue before tax including room and ancillary revenue.

Formula:

```sql
SUM(daily_total_revenue_before_tax)
```

---

## ADR (Average Daily Rate)

Average room revenue earned per room night.

Formula:

ADR = Room Revenue / Room Nights

Implemented as:

```python
adr = room_revenue / room_nights
```

ADR uses room revenue, not total revenue.

---

# Tool-Specific Metrics

## OTB (On The Books)

Used by:

* get_otb_summary
* get_as_of_otb

Definition:

Reservations that are currently booked and financially posted.

Default universe:

* financial_status = Posted
* reservation_status <> Cancelled

Metrics returned:

* row_count
* reservation_count
* room_nights
* room_revenue
* total_revenue

---

## Segment Mix

Used by:

* get_segment_mix

Grouping:

* market_code
* market_name
* effective_macro_group

Metrics:

### Share of Room Nights

Formula:

share_of_room_nights = segment_room_nights / total_room_nights

### Share of Revenue

Formula:

share_of_revenue = segment_revenue / total_revenue

Shares sum to 1.0 within the filtered population.

---

## Pickup

Used by:

* get_pickup_delta

Definition:

New business created during a booking window.

Booking window:

```text
[now - booking_window_days, now]
```

based on:

```text
create_datetime
```

Metrics:

* new_reservations
* new_room_nights
* new_total_revenue

Pickup is based on reservation creation date, not stay date.

---

## As-Of OTB

Used by:

* get_as_of_otb

Definition:

Historical point-in-time view of the business known at a specified timestamp.

A reservation is included when:

* create_datetime <= as_of_timestamp
* financial_status = Posted
* reservation was not cancelled before the as-of timestamp

Rule:

```text
reservation_status <> Cancelled
OR cancellation_datetime > as_of_timestamp
```

---

## Block Business

Definition:

```text
is_block = TRUE
```

Examples:

* Group blocks
* Allocated room blocks

---

## Transient Business

Definition:

```text
is_block = FALSE
```

Examples:

* Individual travelers
* OTA bookings
* Walk-ins

---

## Block Share of Room Nights

Formula:

block_room_nights / total_room_nights

---

## Block Share of Revenue

Formula:

block_revenue / total_revenue

---

## Room Type Performance

Used by:

* get_room_type_performance

Grouping:

* space_type
* display_name
* room_class

Metrics:

### Room Nights

```sql
SUM(number_of_spaces)
```

### Total Revenue

```sql
SUM(daily_total_revenue_before_tax)
```

### ADR

```text
room_revenue / room_nights
```

### Rooms in Inventory

Physical inventory from:

```text
room_type_lookup.number_of_rooms
```

---

## Top Companies

Used by:

* get_top_companies

Grouping:

```text
company_name
```

Null values are grouped as:

```text
Transient
```

Metrics:

* total_revenue
* room_nights
* reservation_count

### Share of Revenue

Formula:

company_revenue / total_revenue

### Top N Share

Formula:

sum(share_of_revenue for returned companies)

Represents the revenue concentration of the returned companies.

---

# Revenue Manager Interpretation Notes

* Room Nights are based on `number_of_spaces`.
* ADR uses room revenue only.
* Revenue metrics are before tax.
* Shares are expressed as decimals between 0 and 1.
* Reservation counts and stay-row counts are intentionally different measures.
* Historical point-in-time analysis should use `get_as_of_otb`.
* Current business analysis should use `get_otb_summary`.
