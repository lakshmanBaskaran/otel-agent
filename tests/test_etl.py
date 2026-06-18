"""
tests/test_etl.py — ETL property tests (Phase 1)
Covers scenarios 1-4 from ETL_TEST_SCENARIOS.md.
Requires a loaded database (run etl.py first).
"""
import json
import os
import psycopg2
import pytest

DB_CONN = os.environ["DATABASE_URL"]

@pytest.fixture(scope="module")
def conn():
    c = psycopg2.connect(DB_CONN)
    yield c
    c.close()


@pytest.fixture(scope="module")
def cur(conn):
    return conn.cursor()


# ─── Scenario 1: Lookup row counts ─────────────────────────────────────────────

def test_room_type_lookup_count(cur):
    cur.execute("SELECT COUNT(*) FROM room_type_lookup")
    assert cur.fetchone()[0] == 3

def test_market_code_lookup_count(cur):
    cur.execute("SELECT COUNT(*) FROM market_code_lookup")
    assert cur.fetchone()[0] == 10

def test_market_macro_group_history_count(cur):
    cur.execute("SELECT COUNT(*) FROM market_macro_group_history")
    assert cur.fetchone()[0] == 11

def test_channel_code_lookup_count(cur):
    cur.execute("SELECT COUNT(*) FROM channel_code_lookup")
    assert cur.fetchone()[0] == 4

def test_rate_plan_lookup_has_reference_plans(cur):
    # Reference page has 8 rate plans. ETL backfills additional codes
    # found in reservations but missing from the reference page.
    # We verify the 8 reference plans are present.
    cur.execute("SELECT COUNT(*) FROM rate_plan_lookup")
    count = cur.fetchone()[0]
    assert count >= 8, f"Expected at least 8 rate plans, got {count}"

    expected = {"BOOKBAR", "GROUPBB", "DLY1", "FITBB", "CORP10BB", "PROMO1", "ZEPHYR-CORP-25", "WALKIN"}
    cur.execute("SELECT rate_plan_code FROM rate_plan_lookup")
    actual = set(row[0] for row in cur.fetchall())
    assert expected.issubset(actual), f"Missing reference rate plans: {expected - actual}"


# ─── Scenario 2: Fact-table grain uniqueness ───────────────────────────────────

def test_no_duplicate_reservation_stay_date(cur):
    # Grain: one row per (reservation_id, stay_date). No duplicates.
    cur.execute("""
        SELECT reservation_id, stay_date, COUNT(*)
        FROM reservations_hackathon
        GROUP BY reservation_id, stay_date
        HAVING COUNT(*) > 1
    """)
    dupes = cur.fetchall()
    assert len(dupes) == 0, f"Found {len(dupes)} duplicate (reservation_id, stay_date) pairs: {dupes[:5]}"

def test_unique_constraint_exists(cur):
    # Verify the UNIQUE constraint is in the schema
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.table_constraints
        WHERE table_name = 'reservations_hackathon'
        AND constraint_type = 'UNIQUE'
    """)
    assert cur.fetchone()[0] >= 1, "Missing UNIQUE constraint on reservations_hackathon"


# ─── Scenario 3: Manifest and verify reconciliation ───────────────────────────

def test_manifest_reservation_count(cur):
    manifest_path = os.path.join(os.path.dirname(__file__), "..", "etl", "SCRAPE_MANIFEST.json")
    if not os.path.exists(manifest_path):
        pytest.skip("etl/SCRAPE_MANIFEST.json not found")

    with open(manifest_path) as f:
        manifest = json.load(f)

    cur.execute("SELECT COUNT(DISTINCT reservation_id) FROM reservations_hackathon")
    db_count = cur.fetchone()[0]
    assert manifest["reservation_ids_count"] == db_count, \
        f"Manifest says {manifest['reservation_ids_count']} but DB has {db_count} distinct reservations"

def test_load_manifest_has_entry(cur):
    cur.execute("SELECT COUNT(*) FROM load_manifest")
    assert cur.fetchone()[0] >= 1, "load_manifest should have at least 1 row after ETL"

def test_load_manifest_dataset_revision(cur):
    cur.execute("SELECT dataset_revision FROM load_manifest ORDER BY created_at DESC LIMIT 1")
    row = cur.fetchone()
    assert row is not None, "No load_manifest entry"
    # Should be a non-empty revision string
    assert len(row[0]) > 0, "dataset_revision is empty"


# ─── Scenario 4 (bonus): Stay row expansion ───────────────────────────────────

def test_multi_night_stay_row_expansion(cur):
    # Find a multi-night reservation and verify row count matches nights
    cur.execute("""
        SELECT reservation_id, nights, COUNT(*) as row_count
        FROM reservations_hackathon
        WHERE nights > 1
        GROUP BY reservation_id, nights
        LIMIT 5
    """)
    rows = cur.fetchall()
    assert len(rows) > 0, "No multi-night reservations found"

    for res_id, nights, row_count in rows:
        assert row_count == nights, \
            f"Reservation {res_id}: {nights} nights but {row_count} stay rows"