import json
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import psycopg2
from langchain_core.tools import tool

DB_CONN = os.environ["HOTEL_DATABASE_URL"]

LONDON_TZ = ZoneInfo("Europe/London")


def get_conn():
    return psycopg2.connect(DB_CONN)


@tool
def get_otb_summary(stay_month: str, exclude_cancelled: bool = True) -> str:
    """On-the-books summary for a calendar month of stay dates (YYYY-MM).

    Default universe: vw_stay_night_base (Posted, non-cancelled).
    When exclude_cancelled=False, queries reservations_hackathon with only
    financial_status='Posted' filter (includes cancelled rows).

    Grain:
      - row_count: stay-date rows (one per reservation x stay_date)
      - reservation_count: distinct reservation_id
      - room_nights: sum(number_of_spaces) at stay-date grain

    Args:
        stay_month: 'YYYY-MM'
        exclude_cancelled: True excludes Cancelled status (default)

    Returns stay_month, row_count, reservation_count, room_nights,
    room_revenue, total_revenue, exclude_cancelled.
    """
    conn = get_conn()
    cur = conn.cursor()

    if exclude_cancelled:
        cur.execute("""
            SELECT COUNT(*) AS row_count,
                   COUNT(DISTINCT reservation_id) AS reservation_count,
                   COALESCE(SUM(number_of_spaces), 0) AS room_nights,
                   COALESCE(SUM(daily_room_revenue_before_tax), 0) AS room_revenue,
                   COALESCE(SUM(daily_total_revenue_before_tax), 0) AS total_revenue
            FROM vw_stay_night_base
            WHERE TO_CHAR(stay_date, 'YYYY-MM') = %s
        """, (stay_month,))
    else:
        cur.execute("""
            SELECT COUNT(*) AS row_count,
                   COUNT(DISTINCT reservation_id) AS reservation_count,
                   COALESCE(SUM(number_of_spaces), 0) AS room_nights,
                   COALESCE(SUM(daily_room_revenue_before_tax), 0) AS room_revenue,
                   COALESCE(SUM(daily_total_revenue_before_tax), 0) AS total_revenue
            FROM reservations_hackathon
            WHERE TO_CHAR(stay_date, 'YYYY-MM') = %s
              AND financial_status = 'Posted'
        """, (stay_month,))

    row = cur.fetchone()
    conn.close()

    return json.dumps({
        "stay_month": stay_month,
        "row_count": row[0],
        "reservation_count": row[1],
        "room_nights": row[2],
        "room_revenue": float(row[3]),
        "total_revenue": float(row[4]),
        "exclude_cancelled": exclude_cancelled,
    })


@tool
def get_segment_mix(stay_month: str, macro_group: str = "") -> str:
    """Segment mix for a stay month using vw_segment_stay_night.

    Grain:
      - room_nights: sum(number_of_spaces) per segment at stay-date grain
      - total_revenue: sum(daily_total_revenue_before_tax) per segment
      - share_of_room_nights: 0-1, denominator = all segments in filtered scope
      - share_of_revenue: 0-1, same denominator

    If macro_group is set, filters to that effective_macro_group only.
    Shares always sum to 1.0 within the filtered population.

    Args:
        stay_month: 'YYYY-MM'
        macro_group: filter to this macro group, or '' for all

    Returns segments list with market_code, market_name, macro_group,
    room_nights, total_revenue, share_of_room_nights, share_of_revenue,
    plus denominator_room_nights and denominator_revenue.
    """
    conn = get_conn()
    cur = conn.cursor()

    params = [stay_month]
    where_extra = ""
    if macro_group:
        where_extra = "AND effective_macro_group = %s"
        params.append(macro_group)

    cur.execute(f"""
        SELECT market_code, market_name, effective_macro_group,
               SUM(number_of_spaces) AS room_nights,
               SUM(daily_total_revenue_before_tax) AS total_revenue
        FROM vw_segment_stay_night
        WHERE TO_CHAR(stay_date, 'YYYY-MM') = %s {where_extra}
        GROUP BY market_code, market_name, effective_macro_group
        ORDER BY total_revenue DESC
    """, tuple(params))

    rows = cur.fetchall()
    conn.close()

    total_rn = sum(r[3] for r in rows) or 1
    total_rev = sum(float(r[4]) for r in rows) or 1

    segments = []
    for r in rows:
        segments.append({
            "market_code": r[0],
            "market_name": r[1],
            "macro_group": r[2],
            "room_nights": r[3],
            "total_revenue": float(r[4]),
            "share_of_room_nights": round(r[3] / total_rn, 6),
            "share_of_revenue": round(float(r[4]) / total_rev, 6),
        })

    return json.dumps({
        "stay_month": stay_month,
        "macro_group_filter": macro_group or None,
        "denominator_room_nights": total_rn,
        "denominator_revenue": float(total_rev),
        "segments": segments,
    })


@tool
def get_pickup_delta(booking_window_days: int, future_stay_from: str) -> str:
    """Booking pace / pickup for future stays.

    booking_window_days: reservations whose create_datetime falls in the window
      [start_of_day_london(now - days), now] converted to UTC.
    future_stay_from: ISO date; only stay_date >= this date.

    Uses create_datetime for the booking window — not stay_date.

    Grain:
      - new_reservations: distinct reservation_id created in the window
      - new_room_nights: sum(number_of_spaces) for those stay rows
      - new_total_revenue: sum(daily_total_revenue_before_tax)

    Args:
        booking_window_days: days back from now
        future_stay_from: 'YYYY-MM-DD', only stays on or after this date

    Returns booking_window_days, future_stay_from, new_reservations,
    new_room_nights, new_total_revenue, by_segment.
    """
    conn = get_conn()
    cur = conn.cursor()

    now_london = datetime.now(LONDON_TZ)
    window_start_london = (now_london - timedelta(days=booking_window_days)).replace(
        hour=0, minute=0, second=0, microsecond=0)
    window_start_utc = window_start_london.astimezone(timezone.utc)

    cur.execute("""
        SELECT COUNT(DISTINCT reservation_id) AS new_reservations,
               COALESCE(SUM(number_of_spaces), 0) AS new_room_nights,
               COALESCE(SUM(daily_total_revenue_before_tax), 0) AS new_total_revenue
        FROM vw_stay_night_base
        WHERE create_datetime >= %s
          AND stay_date >= %s::date
    """, (window_start_utc, future_stay_from))

    row = cur.fetchone()
    new_res, new_rn, new_rev = row[0], row[1], float(row[2])

    cur.execute("""
        SELECT v.market_code,
               COALESCE(SUM(v.number_of_spaces), 0) AS room_nights,
               COALESCE(SUM(v.daily_total_revenue_before_tax), 0) AS revenue
        FROM vw_stay_night_base v
        WHERE v.create_datetime >= %s
          AND v.stay_date >= %s::date
        GROUP BY v.market_code
        ORDER BY revenue DESC
        LIMIT 5
    """, (window_start_utc, future_stay_from))

    by_segment = []
    for r in cur.fetchall():
        by_segment.append({
            "market_code": r[0],
            "room_nights": r[1],
            "total_revenue": float(r[2]),
        })

    conn.close()

    return json.dumps({
        "booking_window_days": booking_window_days,
        "future_stay_from": future_stay_from,
        "window_start_utc": window_start_utc.isoformat(),
        "new_reservations": new_res,
        "new_room_nights": new_rn,
        "new_total_revenue": new_rev,
        "by_segment": by_segment,
    })


@tool
def get_as_of_otb(stay_month: str, as_of_utc: str) -> str:
    """Point-in-time on-the-books for a stay month as known at as_of_utc.

    Include a stay row when:
      - create_datetime <= as_of_utc
      - AND (reservation_status <> 'Cancelled' OR cancellation_datetime > as_of_utc)
      - AND financial_status = 'Posted'

    This queries reservations_hackathon directly (not the view) because
    the view's default filters don't apply to point-in-time logic.

    Grain:
      - row_count: stay-date rows matching criteria
      - reservation_count: distinct reservation_id
      - room_nights: sum(number_of_spaces)

    HITL-gated: this tool requires human approval before execution.

    Args:
        stay_month: 'YYYY-MM'
        as_of_utc: ISO timestamp in UTC (e.g. '2026-05-01T12:00:00Z')

    Returns same shape as get_otb_summary plus as_of_utc echo.
    """
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*) AS row_count,
               COUNT(DISTINCT reservation_id) AS reservation_count,
               COALESCE(SUM(number_of_spaces), 0) AS room_nights,
               COALESCE(SUM(daily_room_revenue_before_tax), 0) AS room_revenue,
               COALESCE(SUM(daily_total_revenue_before_tax), 0) AS total_revenue
        FROM reservations_hackathon
        WHERE TO_CHAR(stay_date, 'YYYY-MM') = %s
          AND create_datetime <= %s::timestamptz
          AND (reservation_status <> 'Cancelled' OR cancellation_datetime > %s::timestamptz)
          AND financial_status = 'Posted'
    """, (stay_month, as_of_utc, as_of_utc))

    row = cur.fetchone()
    conn.close()

    return json.dumps({
        "stay_month": stay_month,
        "as_of_utc": as_of_utc,
        "row_count": row[0],
        "reservation_count": row[1],
        "room_nights": row[2],
        "room_revenue": float(row[3]),
        "total_revenue": float(row[4]),
    })


@tool
def get_block_vs_transient_mix(stay_month: str) -> str:
    """Block vs transient mix for a stay month using vw_stay_night_base.

    Block = is_block = true. Transient = everything else.

    Grain:
      - room_nights: sum(number_of_spaces) at stay-date grain
      - total_revenue: sum(daily_total_revenue_before_tax)
      - shares: 0-1, block + transient = 1.0

    Args:
        stay_month: 'YYYY-MM'

    Returns block_room_nights, transient_room_nights, block_total_revenue,
    transient_total_revenue, block_share_of_room_nights, block_share_of_revenue,
    top_companies (top 3 by revenue), top3_company_revenue_share.
    """
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT is_block,
               COALESCE(SUM(number_of_spaces), 0) AS room_nights,
               COALESCE(SUM(daily_total_revenue_before_tax), 0) AS total_revenue
        FROM vw_stay_night_base
        WHERE TO_CHAR(stay_date, 'YYYY-MM') = %s
        GROUP BY is_block
    """, (stay_month,))

    block_rn, block_rev = 0, 0.0
    trans_rn, trans_rev = 0, 0.0
    for row in cur.fetchall():
        if row[0]:
            block_rn, block_rev = row[1], float(row[2])
        else:
            trans_rn, trans_rev = row[1], float(row[2])

    total_rn = block_rn + trans_rn or 1
    total_rev = block_rev + trans_rev or 1.0

    cur.execute("""
        SELECT COALESCE(company_name, 'Transient') AS company,
               COALESCE(SUM(daily_total_revenue_before_tax), 0) AS revenue
        FROM vw_stay_night_base
        WHERE TO_CHAR(stay_date, 'YYYY-MM') = %s
        GROUP BY company_name
        ORDER BY revenue DESC
        LIMIT 3
    """, (stay_month,))

    top_companies = []
    top3_rev = 0.0
    for row in cur.fetchall():
        top_companies.append({"company_name": row[0], "total_revenue": float(row[1])})
        top3_rev += float(row[1])

    conn.close()

    return json.dumps({
        "stay_month": stay_month,
        "block_room_nights": block_rn,
        "transient_room_nights": trans_rn,
        "block_total_revenue": block_rev,
        "transient_total_revenue": trans_rev,
        "block_share_of_room_nights": round(block_rn / total_rn, 6),
        "block_share_of_revenue": round(block_rev / total_rev, 6),
        "top_companies": top_companies,
        "top3_company_revenue_share": round(top3_rev / total_rev, 6),
    })


@tool
def get_room_type_performance(stay_month: str = "") -> str:
    """Room type performance — ADR, room nights, revenue per room type.

    Grain:
      - room_nights: sum(number_of_spaces) per room_type at stay-date grain
      - total_revenue: sum(daily_total_revenue_before_tax) per room_type
      - adr: total_revenue / room_nights (room ADR per type)
      - rooms_in_inventory: physical rooms from room_type_lookup

    Args:
        stay_month: 'YYYY-MM' to filter to one month, or '' for all future stays

    Returns room_types list with space_type, display_name, room_class,
    room_nights, total_revenue, adr, rooms_in_inventory.
    """
    conn = get_conn()
    cur = conn.cursor()

    if stay_month:
        cur.execute("""
            SELECT v.space_type, rt.display_name, rt.room_class, rt.number_of_rooms,
                   SUM(v.number_of_spaces) AS room_nights,
                   SUM(v.daily_room_revenue_before_tax) AS room_revenue,
                   SUM(v.daily_total_revenue_before_tax) AS total_revenue
            FROM vw_stay_night_base v
            LEFT JOIN room_type_lookup rt ON v.space_type = rt.space_type
            WHERE TO_CHAR(v.stay_date, 'YYYY-MM') = %s
            GROUP BY v.space_type, rt.display_name, rt.room_class, rt.number_of_rooms
            ORDER BY total_revenue DESC
        """, (stay_month,))
    else:
        cur.execute("""
            SELECT v.space_type, rt.display_name, rt.room_class, rt.number_of_rooms,
                   SUM(v.number_of_spaces) AS room_nights,
                   SUM(v.daily_room_revenue_before_tax) AS room_revenue,
                   SUM(v.daily_total_revenue_before_tax) AS total_revenue
            FROM vw_stay_night_base v
            LEFT JOIN room_type_lookup rt ON v.space_type = rt.space_type
            WHERE v.stay_date >= CURRENT_DATE
            GROUP BY v.space_type, rt.display_name, rt.room_class, rt.number_of_rooms
            ORDER BY total_revenue DESC
        """)

    room_types = []
    for r in cur.fetchall():
        rn = r[4] or 0
        rev = float(r[6] or 0)
        adr = round(float(r[5] or 0) / rn, 2) if rn else 0.0
        room_types.append({
            "space_type": r[0],
            "display_name": r[1],
            "room_class": r[2],
            "rooms_in_inventory": r[3],
            "room_nights": rn,
            "total_revenue": rev,
            "adr": adr,
        })

    conn.close()
    return json.dumps({
        "stay_month": stay_month or "all_future",
        "room_types": room_types,
    })


@tool
def get_top_companies(limit: int = 5, stay_month: str = "") -> str:
    """Top companies by revenue across future stays or a single month.

    Grain:
      - total_revenue: sum(daily_total_revenue_before_tax) per company
      - room_nights: sum(number_of_spaces) per company
      - reservation_count: distinct reservation_id per company
      - share_of_revenue: 0-1, denominator = total revenue in scope (incl. transient)

    Null company_name is bucketed as 'Transient'.

    Args:
        limit: number of top companies to return (default 5, max 20)
        stay_month: 'YYYY-MM' for single month, or '' for all future stays

    Returns companies list with company_name, total_revenue, room_nights,
    reservation_count, share_of_revenue. Also returns top_n_share (sum of returned
    companies' share) and denominator_revenue.
    """
    conn = get_conn()
    cur = conn.cursor()
    limit = max(1, min(int(limit), 20))

    if stay_month:
        params = (stay_month,)
        where = "WHERE TO_CHAR(stay_date, 'YYYY-MM') = %s"
    else:
        params = ()
        where = "WHERE stay_date >= CURRENT_DATE"

    cur.execute(f"""
        SELECT COALESCE(company_name, 'Transient') AS company,
               SUM(daily_total_revenue_before_tax) AS revenue,
               SUM(number_of_spaces) AS room_nights,
               COUNT(DISTINCT reservation_id) AS reservation_count
        FROM vw_stay_night_base
        {where}
        GROUP BY company_name
        ORDER BY revenue DESC NULLS LAST
        LIMIT %s
    """, params + (limit,))

    rows = cur.fetchall()

    cur.execute(f"""
        SELECT SUM(daily_total_revenue_before_tax)
        FROM vw_stay_night_base
        {where}
    """, params)
    total_rev = float(cur.fetchone()[0] or 1)

    companies = []
    top_n_share = 0.0
    for r in rows:
        rev = float(r[1] or 0)
        share = rev / total_rev if total_rev else 0
        top_n_share += share
        companies.append({
            "company_name": r[0],
            "total_revenue": rev,
            "room_nights": r[2],
            "reservation_count": r[3],
            "share_of_revenue": round(share, 6),
        })

    conn.close()
    return json.dumps({
        "stay_month": stay_month or "all_future",
        "limit": limit,
        "denominator_revenue": total_rev,
        "top_n_share": round(top_n_share, 6),
        "companies": companies,
    })

ALL_TOOLS = [
    get_otb_summary,
    get_segment_mix,
    get_pickup_delta,
    get_as_of_otb,
    get_block_vs_transient_mix,
    get_room_type_performance,
    get_top_companies,
]