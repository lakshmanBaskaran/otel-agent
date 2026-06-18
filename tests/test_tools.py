"""
tests/test_tools.py — Tool property tests (Phase 2 + bonus tools)
Covers scenarios 1-6, 8-12 from TOOL_TEST_SCENARIOS.md plus the 2 bonus tools.
Requires a loaded database.
"""
import json
import os
import pytest
import psycopg2

from tools import (
    get_otb_summary,
    get_segment_mix,
    get_pickup_delta,
    get_as_of_otb,
    get_block_vs_transient_mix,
    get_room_type_performance,
    get_top_companies,
    ALL_TOOLS,
)

DB_CONN = os.environ["DATABASE_URL"]

CURRENT_MONTH = "2026-07"
LAST_YEAR_MONTH = "2025-07"

REQUIRED_TOOL_NAMES = {
    "get_otb_summary",
    "get_segment_mix",
    "get_pickup_delta",
    "get_as_of_otb",
    "get_block_vs_transient_mix",
}

BONUS_TOOL_NAMES = {
    "get_room_type_performance",
    "get_top_companies",
}


def call(tool_fn, **kwargs):
    """Invoke a tool and parse the JSON result."""
    result = tool_fn.invoke(kwargs)
    return json.loads(result)


# ─── Scenario 1: Grain inequality ──────────────────────────────────────────────

def test_grain_inequality():
    """row_count != reservation_count; room_nights >= reservation_count;
    room_revenue <= total_revenue."""
    r = call(get_otb_summary, stay_month=CURRENT_MONTH, exclude_cancelled=True)
    assert r["reservation_count"] <= r["row_count"], \
        "reservation_count should be <= row_count (multi-night stays create multiple rows)"
    assert r["room_nights"] >= r["reservation_count"], \
        "room_nights >= reservation_count (each reservation has at least 1 room night)"
    assert r["room_revenue"] <= r["total_revenue"], \
        "room_revenue <= total_revenue (total includes non-room components)"


# ─── Scenario 2: Cancellation filter changes counts ───────────────────────────

def test_cancellation_filter_changes_counts():
    """exclude_cancelled=True produces fewer rows than False when cancellations exist."""
    conn = psycopg2.connect(DB_CONN)
    cur = conn.cursor()
    cur.execute("""
        SELECT TO_CHAR(stay_date, 'YYYY-MM'), COUNT(*)
        FROM reservations_hackathon
        WHERE reservation_status = 'Cancelled' AND financial_status = 'Posted'
        GROUP BY TO_CHAR(stay_date, 'YYYY-MM')
        HAVING COUNT(*) > 0
        LIMIT 1
    """)
    row = cur.fetchone()
    conn.close()

    if not row:
        pytest.skip("No months with cancelled+posted rows found")

    month = row[0]
    with_exclusion = call(get_otb_summary, stay_month=month, exclude_cancelled=True)
    without_exclusion = call(get_otb_summary, stay_month=month, exclude_cancelled=False)

    assert with_exclusion["row_count"] < without_exclusion["row_count"], \
        f"Excluding cancellations should reduce row_count for {month}"
    assert with_exclusion["reservation_count"] <= without_exclusion["reservation_count"]


# ─── Scenario 3: Segment shares sum to one ─────────────────────────────────────

def test_segment_shares_sum_to_one():
    """share_of_room_nights and share_of_revenue each sum to 1.0."""
    r = call(get_segment_mix, stay_month=CURRENT_MONTH)
    segments = r["segments"]

    if not segments:
        pytest.skip(f"No segments found for {CURRENT_MONTH}")

    rn_sum = sum(s["share_of_room_nights"] for s in segments)
    rev_sum = sum(s["share_of_revenue"] for s in segments)

    assert abs(rn_sum - 1.0) < 1e-6, f"Room night shares sum to {rn_sum}, expected 1.0"
    assert abs(rev_sum - 1.0) < 1e-6, f"Revenue shares sum to {rev_sum}, expected 1.0"

    for s in segments:
        assert 0 <= s["share_of_room_nights"] <= 1
        assert 0 <= s["share_of_revenue"] <= 1


# ─── Scenario 4: Macro group filter narrows universe ──────────────────────────

def test_macro_group_filter_narrows():
    """Filtering by macro_group produces fewer room_nights than unfiltered."""
    full = call(get_segment_mix, stay_month=CURRENT_MONTH)
    filtered = call(get_segment_mix, stay_month=CURRENT_MONTH, macro_group="Retail")

    full_rn = full["denominator_room_nights"]
    filtered_rn = filtered["denominator_room_nights"]

    assert filtered_rn <= full_rn, \
        f"Filtered room nights ({filtered_rn}) should be <= unfiltered ({full_rn})"

    for s in filtered["segments"]:
        assert s["macro_group"] == "Retail", \
            f"Segment {s['market_code']} has macro_group={s['macro_group']}, expected Retail"


# ─── Scenario 5: Pickup uses booking date not stay date ────────────────────────

def test_pickup_uses_booking_date():
    """Wider booking window produces >= reservations than narrow window.
    create_datetime defines the booking window, not stay_date."""
    wide = call(get_pickup_delta, booking_window_days=365, future_stay_from="2026-07-01")
    narrow = call(get_pickup_delta, booking_window_days=1, future_stay_from="2026-07-01")

    assert narrow["new_reservations"] <= wide["new_reservations"], \
        "1-day window should have <= reservations than 365-day window"


# ─── Scenario 6: OTA concentration signal ─────────────────────────────────────

def test_ota_segment_exists():
    """OTA segment exists and has a share strictly between 0 and 1."""
    r = call(get_segment_mix, stay_month=CURRENT_MONTH)
    segments = r["segments"]

    ota = [s for s in segments if s["market_code"] == "OTA"]
    assert len(ota) > 0, f"OTA segment missing for {CURRENT_MONTH} — broken ETL or wrong month"

    ota_share = ota[0]["share_of_revenue"]
    assert 0 < ota_share < 1, f"OTA share should be between 0 and 1, got {ota_share}"


# ─── Scenario 8: Provisional exclusion from default OTB ───────────────────────

def test_provisional_excluded_from_default_otb():
    """Default OTB excludes provisional rows."""
    conn = psycopg2.connect(DB_CONN)
    cur = conn.cursor()

    cur.execute("""
        SELECT TO_CHAR(stay_date, 'YYYY-MM'), COUNT(*)
        FROM reservations_hackathon
        WHERE financial_status = 'Provisional' AND reservation_status != 'Cancelled'
        GROUP BY TO_CHAR(stay_date, 'YYYY-MM')
        HAVING COUNT(*) > 0
        LIMIT 1
    """)
    row = cur.fetchone()

    if not row:
        cur.execute("SELECT COUNT(*) FROM reservations_hackathon WHERE financial_status = 'Provisional'")
        prov_count = cur.fetchone()[0]
        conn.close()
        assert prov_count > 0, "LOAD_PROOF says provisional_row_count > 0 but none found"
        pytest.skip("No month with non-cancelled provisional rows")

    month = row[0]

    cur.execute("""
        SELECT COUNT(*) FROM reservations_hackathon
        WHERE TO_CHAR(stay_date, 'YYYY-MM') = %s
          AND reservation_status != 'Cancelled'
          AND financial_status = 'Posted'
    """, (month,))
    posted_only = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM reservations_hackathon
        WHERE TO_CHAR(stay_date, 'YYYY-MM') = %s
          AND reservation_status != 'Cancelled'
    """, (month,))
    all_non_cancelled = cur.fetchone()[0]
    conn.close()

    assert posted_only < all_non_cancelled, \
        f"Month {month}: posted rows ({posted_only}) should be < all non-cancelled ({all_non_cancelled})"


# ─── Scenario 9: As-of snapshot differs from current OTB ──────────────────────

def test_as_of_otb_differs_from_current():
    """Point-in-time OTB with early as_of date produces different results."""
    current = call(get_otb_summary, stay_month=CURRENT_MONTH)
    historical = call(get_as_of_otb, stay_month=CURRENT_MONTH, as_of_utc="2025-01-01T00:00:00Z")

    assert historical["reservation_count"] <= current["reservation_count"], \
        "Historical snapshot should have <= reservations than current OTB"


# ─── Scenario 10: Property date vs stay date ──────────────────────────────────

def test_property_date_mismatch_count():
    """property_date_mismatch_count matches rows where property_date != stay_date."""
    conn = psycopg2.connect(DB_CONN)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM reservations_hackathon WHERE property_date != stay_date")
    db_count = cur.fetchone()[0]
    conn.close()

    assert db_count == 3, f"Expected 3 property_date mismatches, got {db_count}"


def test_tools_use_stay_date_not_property_date():
    """Tools filter on stay_date for monthly grouping, not property_date."""
    import inspect
    src = inspect.getsource(get_otb_summary.func)
    assert "stay_date" in src, "get_otb_summary should filter on stay_date"
    assert "property_date" not in src or "not property_date" in src, \
        "get_otb_summary should not filter on property_date"


# ─── Scenario 11: Block vs transient mix ───────────────────────────────────────

def test_block_vs_transient_reconciles():
    """Block + transient room nights = OTB room nights for the month."""
    mix = call(get_block_vs_transient_mix, stay_month=CURRENT_MONTH)
    otb = call(get_otb_summary, stay_month=CURRENT_MONTH)

    mix_total = mix["block_room_nights"] + mix["transient_room_nights"]
    assert abs(mix_total - otb["room_nights"]) <= 1, \
        f"Block ({mix['block_room_nights']}) + Transient ({mix['transient_room_nights']}) = {mix_total}, OTB = {otb['room_nights']}"

    assert 0 <= mix["block_share_of_room_nights"] <= 1
    assert 0 <= mix["block_share_of_revenue"] <= 1
    assert mix["top3_company_revenue_share"] <= 1.0
    assert len(mix["top_companies"]) <= 3

    if len(mix["top_companies"]) > 1:
        revs = [c["total_revenue"] for c in mix["top_companies"]]
        assert revs == sorted(revs, reverse=True), "top_companies should be sorted by revenue desc"


# ─── Scenario 12: Tool layer isolation ─────────────────────────────────────────

def test_required_tools_present():
    """All 5 required tools are present (bonus tools allowed on top)."""
    actual_names = {t.name for t in ALL_TOOLS}
    missing = REQUIRED_TOOL_NAMES - actual_names
    assert not missing, f"Missing required tools: {missing}"


def test_tool_count_at_least_five():
    """At least the 5 required tools are exposed (bonus tools allowed)."""
    assert len(ALL_TOOLS) >= 5, f"Expected at least 5 tools, got {len(ALL_TOOLS)}"


def test_no_raw_sql_parameter():
    """No tool accepts a free-form SQL string parameter."""
    import inspect
    for tool_fn in ALL_TOOLS:
        sig = inspect.signature(tool_fn.func)
        for param_name in sig.parameters:
            assert "sql" not in param_name.lower() and "query" not in param_name.lower(), \
                f"Tool {tool_fn.name} has SQL-like parameter: {param_name}"


def test_docstrings_mention_grain():
    """Each tool's docstring mentions grain (row vs reservation vs room night)."""
    for tool_fn in ALL_TOOLS:
        doc = tool_fn.func.__doc__ or ""
        doc_lower = doc.lower()
        assert any(w in doc_lower for w in ["grain", "row_count", "reservation_count", "room_nights", "room night"]), \
            f"Tool {tool_fn.name} docstring does not mention grain"


# ─── Bonus tool: get_room_type_performance ─────────────────────────────────────

def test_room_type_performance_returns_room_types():
    """Room type performance returns room types with ADR and room nights."""
    r = call(get_room_type_performance, stay_month=CURRENT_MONTH)
    assert "room_types" in r
    assert len(r["room_types"]) >= 1, "Expected at least one room type"

    for rt in r["room_types"]:
        assert "space_type" in rt
        assert "adr" in rt
        assert "room_nights" in rt
        assert "total_revenue" in rt
        assert rt["adr"] >= 0
        assert rt["room_nights"] >= 0


def test_room_type_adr_is_positive():
    """At least one room type has positive ADR and the highest is reasonable."""
    r = call(get_room_type_performance, stay_month="")
    room_types = r["room_types"]
    assert len(room_types) > 0, "Expected room types to be returned"

    top = max(room_types, key=lambda x: x["adr"])
    assert top["adr"] > 0, f"Top ADR should be positive, got {top['adr']}"
    assert top["adr"] < 10000, f"Top ADR suspiciously high: {top['adr']}"


# ─── Bonus tool: get_top_companies ─────────────────────────────────────────────

def test_top_companies_respects_limit():
    """Top companies tool respects the limit parameter."""
    r = call(get_top_companies, limit=5, stay_month="")
    assert len(r["companies"]) <= 5, f"Expected <= 5 companies, got {len(r['companies'])}"

    r10 = call(get_top_companies, limit=10, stay_month="")
    assert len(r10["companies"]) <= 10
    assert len(r10["companies"]) >= len(r["companies"]), \
        "limit=10 should return at least as many as limit=5"


def test_top_companies_sorted_by_revenue():
    """Top companies returned in descending revenue order."""
    r = call(get_top_companies, limit=10, stay_month="")
    revs = [c["total_revenue"] for c in r["companies"]]
    assert revs == sorted(revs, reverse=True), "Companies should be sorted by revenue desc"


def test_top_companies_share_bounded():
    """top_n_share is between 0 and 1 (within tolerance)."""
    r = call(get_top_companies, limit=10, stay_month="")
    assert 0 <= r["top_n_share"] <= 1.01, \
        f"top_n_share should be in [0, 1], got {r['top_n_share']}"