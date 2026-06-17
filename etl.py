import asyncio
import hashlib
import json
import os
import re
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import execute_values
from playwright.async_api import async_playwright

DB_CONN = os.environ.get("DATABASE_URL",
    "postgresql://neondb_owner:npg_frN6GqcsOBi9@ep-noisy-frost-abppfjnj.eu-west-2.aws.neon.tech/neondb?sslmode=require")
BASE_URL = "https://otel-hackathon-data-site.vercel.app"

KNOWN_FIELDS = [
    "arrival_date", "departure_date", "nights", "reservation_status",
    "create_datetime", "cancellation_datetime", "guest_country",
    "is_block", "is_walk_in", "number_of_spaces", "space_type",
    "market_code", "channel_code", "source_name", "rate_plan_code",
    "commercial_rate_code", "adr_room", "lead_time",
    "company_name", "travel_agent_name"
]


# ─── EXTRACT ───────────────────────────────────────────────────────────────────

async def scrape_dataset_revision(page):
    await page.goto(f"{BASE_URL}/reference", timeout=60000)
    await page.wait_for_load_state("networkidle", timeout=60000)
    await page.wait_for_timeout(2000)
    text = await page.evaluate("() => document.body.innerText")
    match = re.search(r'Dataset revision\s+([\d.]+)', text)
    return match.group(1) if match else "unknown"


async def scrape_reference_tab(page, tab_name):
    await page.evaluate(f"""
        () => {{
            const buttons = Array.from(document.querySelectorAll('button, a, [role="tab"]'));
            const btn = buttons.find(b => b.innerText.trim().toLowerCase() === '{tab_name.lower()}');
            if (btn) {{ btn.click(); return true; }}
            return false;
        }}
    """)
    await page.wait_for_timeout(1500)
    return await page.evaluate("""
        () => {
            const tables = document.querySelectorAll('table');
            if (!tables.length) return [];
            const table = tables[tables.length - 1];
            const ths = Array.from(table.querySelectorAll('th'));
            const headers = ths.map(th => th.innerText.trim().toLowerCase());
            const result = [];
            for (const tr of table.querySelectorAll('tr')) {
                const tds = Array.from(tr.querySelectorAll('td'));
                if (tds.length === 0) continue;
                const row = {};
                for (let j = 0; j < headers.length && j < tds.length; j++) {
                    row[headers[j]] = tds[j].innerText.trim();
                }
                result.push(row);
            }
            return result;
        }
    """)


async def scrape_reference(page):
    await page.goto(f"{BASE_URL}/reference", timeout=60000)
    await page.wait_for_load_state("networkidle", timeout=60000)
    await page.wait_for_timeout(2000)
    room_types = await scrape_reference_tab(page, "Room types")
    market_codes = await scrape_reference_tab(page, "Markets")
    channel_codes = await scrape_reference_tab(page, "Channels")
    rate_plans = await scrape_reference_tab(page, "Rate plans")
    macro_history = await scrape_reference_tab(page, "Macro history")
    print(f"  Room types: {len(room_types)}, Markets: {len(market_codes)}, "
          f"Channels: {len(channel_codes)}, Rate plans: {len(rate_plans)}, "
          f"Macro history: {len(macro_history)}")
    return room_types, market_codes, channel_codes, rate_plans, macro_history


async def scrape_reservation_ids(page):
    ids = []
    current_page = 1
    pages_scraped = 0
    await page.goto(f"{BASE_URL}/reservations", timeout=60000)
    await page.wait_for_load_state("networkidle", timeout=60000)
    await page.wait_for_timeout(3000)
    while True:
        links = await page.query_selector_all("a[href*='/reservations/']")
        page_ids = []
        for link in links:
            href = await link.get_attribute("href")
            if href:
                res_id = href.split("/reservations/")[-1].strip("/")
                if res_id and res_id not in ids:
                    page_ids.append(res_id)
        if not page_ids:
            break
        ids.extend(page_ids)
        pages_scraped += 1
        print(f"  Page {current_page}: {len(page_ids)} reservations (total: {len(ids)})")
        next_clicked = await page.evaluate("""
            () => {
                const allLinks = Array.from(document.querySelectorAll('a, button'));
                const next = allLinks.find(el => el.innerText && el.innerText.includes('Next'));
                if (next) { next.click(); return true; }
                return false;
            }
        """)
        if not next_clicked:
            break
        await page.wait_for_load_state("networkidle", timeout=60000)
        await page.wait_for_timeout(3000)
        current_page += 1
    return ids, pages_scraped


async def scrape_reservation_detail(page, res_id):
    await page.goto(f"{BASE_URL}/reservations/{res_id}", timeout=60000)
    await page.wait_for_load_state("networkidle", timeout=60000)
    await page.wait_for_timeout(2000)
    page_text = await page.evaluate("() => document.body.innerText")
    lines = [line.strip() for line in page_text.split("\n") if line.strip()]

    res_fields = {"reservation_id": res_id}
    for i, line in enumerate(lines):
        if line.lower() in KNOWN_FIELDS and i + 1 < len(lines):
            value = lines[i + 1]
            if value.lower() in KNOWN_FIELDS:
                res_fields[line.lower()] = None
            elif value in ("\u2014", "-", ""):
                res_fields[line.lower()] = None
            else:
                res_fields[line.lower()] = value

    stay_rows = await page.evaluate("""
        () => {
            const tables = document.querySelectorAll('table');
            if (!tables.length) return [];
            const table = tables[tables.length - 1];
            const ths = Array.from(table.querySelectorAll('th'));
            const headers = ths.map(th => th.innerText.trim().toLowerCase().replace(/ /g, '_'));
            const result = [];
            for (const tr of table.querySelectorAll('tr')) {
                const tds = Array.from(tr.querySelectorAll('td'));
                if (tds.length === 0) continue;
                const row = {};
                for (let j = 0; j < headers.length && j < tds.length; j++) {
                    row[headers[j]] = tds[j].innerText.trim();
                }
                result.push(row);
            }
            return result;
        }
    """)

    combined = []
    for stay_row in stay_rows:
        combined.append({**res_fields, **stay_row})
    return combined


# ─── TRANSFORM ─────────────────────────────────────────────────────────────────

def safe_int(val, default=0):
    try: return int(val) if val not in (None, "", "\u2014") else default
    except (ValueError, TypeError): return default

def safe_float(val, default=0.0):
    try: return float(val) if val not in (None, "", "\u2014") else default
    except (ValueError, TypeError): return default

def safe_nullable(val):
    if val in (None, "", "\u2014", "-"): return None
    return str(val).strip()

def safe_str(val, default=""):
    if val in (None, "", "\u2014", "-"): return default
    return str(val).strip()

def transform_row(raw):
    return {
        "reservation_id": safe_str(raw.get("reservation_id")),
        "arrival_date": safe_nullable(raw.get("arrival_date")),
        "departure_date": safe_nullable(raw.get("departure_date")),
        "stay_date": safe_nullable(raw.get("stay_date")),
        "property_date": safe_nullable(raw.get("property_date")),
        "reservation_status": safe_str(raw.get("reservation_status")),
        "financial_status": safe_str(raw.get("financial_status"), "Posted"),
        "create_datetime": safe_nullable(raw.get("create_datetime")),
        "cancellation_datetime": safe_nullable(raw.get("cancellation_datetime")),
        "guest_country": safe_nullable(raw.get("guest_country")),
        "is_block": str(raw.get("is_block", "false")).lower() == "true",
        "is_walk_in": str(raw.get("is_walk_in", "false")).lower() == "true",
        "number_of_spaces": safe_int(raw.get("number_of_spaces"), 1),
        "space_type": safe_str(raw.get("space_type")),
        "market_code": safe_str(raw.get("market_code")),
        "channel_code": safe_str(raw.get("channel_code")),
        "source_name": safe_str(raw.get("source_name")),
        "rate_plan_code": safe_str(raw.get("rate_plan_code")),
        "daily_room_revenue_before_tax": safe_float(raw.get("daily_room_revenue_before_tax")),
        "daily_total_revenue_before_tax": safe_float(raw.get("daily_total_revenue_before_tax")),
        "nights": safe_int(raw.get("nights"), 1),
        "adr_room": safe_float(raw.get("adr_room")),
        "lead_time": safe_int(raw.get("lead_time")),
        "company_name": safe_nullable(raw.get("company_name")),
        "travel_agent_name": safe_nullable(raw.get("travel_agent_name")),
    }


# ─── LOAD ──────────────────────────────────────────────────────────────────────

def load_lookups(conn, room_types, market_codes, channel_codes, rate_plans, macro_history):
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE reservations_hackathon RESTART IDENTITY CASCADE")
    cur.execute("DELETE FROM market_macro_group_history")
    cur.execute("DELETE FROM rate_plan_lookup")
    cur.execute("DELETE FROM market_code_lookup")
    cur.execute("DELETE FROM channel_code_lookup")
    cur.execute("DELETE FROM room_type_lookup")

    execute_values(cur, """
        INSERT INTO room_type_lookup (space_type, room_class, display_name, number_of_rooms)
        VALUES %s
    """, [(r["space_type"], r["room_class"], r["display_name"],
           int(r["number_of_rooms"])) for r in room_types])

    execute_values(cur, """
        INSERT INTO market_code_lookup (market_code, market_name, macro_group, description)
        VALUES %s
    """, [(r["market_code"], r["market_name"], r["macro_group"],
           r.get("description", "")) for r in market_codes])

    execute_values(cur, """
        INSERT INTO channel_code_lookup (channel_code, channel_name, channel_group)
        VALUES %s
    """, [(r["channel_code"], r["channel_name"], r["channel_group"]) for r in channel_codes])

    execute_values(cur, """
        INSERT INTO rate_plan_lookup (rate_plan_code, plan_family, is_commissionable)
        VALUES %s
    """, [(r["rate_plan_code"], r["plan_family"],
           r["is_commissionable"].lower() == "true") for r in rate_plans])

    for r in macro_history:
        valid_to = None if r.get("valid_to", "\u2014") in ("\u2014", "", "-", None) else r["valid_to"]
        cur.execute("""
            INSERT INTO market_macro_group_history (market_code, valid_from, valid_to, macro_group)
            VALUES (%s, %s, %s, %s)
        """, (r["market_code"], r["valid_from"], valid_to, r["macro_group"]))

    conn.commit()
    print(f"  Lookups: {len(room_types)} rooms, {len(market_codes)} markets, "
          f"{len(channel_codes)} channels, {len(rate_plans)} rate plans, "
          f"{len(macro_history)} macro history")


def backfill_missing_rate_plans(conn, rows):
    """Insert any rate_plan_codes found in reservations but missing from lookup."""
    cur = conn.cursor()
    all_codes = set(r["rate_plan_code"] for r in rows if r["rate_plan_code"])
    cur.execute("SELECT rate_plan_code FROM rate_plan_lookup")
    existing = set(row[0] for row in cur.fetchall())
    missing = all_codes - existing
    if missing:
        print(f"  Backfilling {len(missing)} missing rate plans: {missing}")
        for code in missing:
            cur.execute("""
                INSERT INTO rate_plan_lookup (rate_plan_code, plan_family, is_commissionable)
                VALUES (%s, 'Unknown', false) ON CONFLICT DO NOTHING
            """, (code,))
        conn.commit()


def load_reservations(conn, rows):
    cur = conn.cursor()
    valid = [r for r in rows if r["arrival_date"] and r["stay_date"] and r["reservation_id"]]
    skipped = len(rows) - len(valid)
    if skipped:
        print(f"  Skipped {skipped} rows with missing fields")

    backfill_missing_rate_plans(conn, valid)

    execute_values(cur, """
        INSERT INTO reservations_hackathon (
            reservation_id, arrival_date, departure_date, stay_date, property_date,
            reservation_status, financial_status, create_datetime, cancellation_datetime,
            guest_country, is_block, is_walk_in, number_of_spaces, space_type,
            market_code, channel_code, source_name, rate_plan_code,
            daily_room_revenue_before_tax, daily_total_revenue_before_tax,
            nights, adr_room, lead_time, company_name, travel_agent_name
        ) VALUES %s
    """, [(
        r["reservation_id"], r["arrival_date"], r["departure_date"],
        r["stay_date"], r["property_date"] or r["stay_date"],
        r["reservation_status"], r["financial_status"],
        r["create_datetime"], r["cancellation_datetime"],
        r["guest_country"], r["is_block"], r["is_walk_in"],
        r["number_of_spaces"], r["space_type"],
        r["market_code"], r["channel_code"], r["source_name"], r["rate_plan_code"],
        r["daily_room_revenue_before_tax"], r["daily_total_revenue_before_tax"],
        r["nights"], r["adr_room"], r["lead_time"],
        r["company_name"], r["travel_agent_name"]
    ) for r in valid])

    conn.commit()
    print(f"  Loaded {len(valid)} reservation rows")


def insert_load_manifest(conn, dataset_revision, row_hash):
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO load_manifest (dataset_revision, scraped_at, source_url, row_hash)
        VALUES (%s, %s, %s, %s)
    """, (dataset_revision, datetime.now(timezone.utc), BASE_URL, row_hash))
    conn.commit()


def create_views(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE OR REPLACE VIEW public.vw_stay_night_base AS
        SELECT r.* FROM public.reservations_hackathon r
        WHERE r.reservation_status <> 'Cancelled' AND r.financial_status = 'Posted'
    """)
    cur.execute("""
        CREATE OR REPLACE VIEW public.vw_segment_stay_night AS
        SELECT b.*, COALESCE(h.macro_group, m.macro_group) AS effective_macro_group, m.market_name
        FROM public.vw_stay_night_base b
        JOIN public.market_code_lookup m ON m.market_code = b.market_code
        LEFT JOIN LATERAL (
            SELECT h.macro_group FROM public.market_macro_group_history h
            WHERE h.market_code = b.market_code AND b.stay_date >= h.valid_from
            AND (h.valid_to IS NULL OR b.stay_date < h.valid_to)
            ORDER BY h.valid_from DESC LIMIT 1
        ) h ON TRUE
    """)
    conn.commit()
    print("  Views created")


# ─── MANIFEST ──────────────────────────────────────────────────────────────────

def generate_scrape_manifest(res_ids, pages_scraped, anchor_date):
    sorted_ids = sorted(res_ids)
    ids_text = "\n".join(sorted_ids)
    sha256 = hashlib.sha256(ids_text.encode("utf-8")).hexdigest()
    manifest = {
        "anchor_date": anchor_date,
        "pages_scraped": pages_scraped,
        "reservation_ids_count": len(sorted_ids),
        "reservation_ids_sha256": sha256,
    }
    os.makedirs("etl", exist_ok=True)
    with open("etl/SCRAPE_MANIFEST.json", "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"  SCRAPE_MANIFEST.json saved ({len(sorted_ids)} IDs, SHA: {sha256[:16]}...)")
    return sha256


# ─── VERIFY ────────────────────────────────────────────────────────────────────

def verify(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM reservations_hackathon")
    total_rows = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT reservation_id) FROM reservations_hackathon")
    total_res = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT reservation_id) FROM reservations_hackathon WHERE reservation_status = 'Cancelled'")
    cancelled = cur.fetchone()[0]
    cur.execute("""
            SELECT COUNT(*), SUM(number_of_spaces),
                   SUM(daily_room_revenue_before_tax), SUM(daily_total_revenue_before_tax)
            FROM reservations_hackathon
            WHERE reservation_status != 'Cancelled'
              AND financial_status = 'Posted'
              AND stay_date >= CURRENT_DATE
        """)
    r = cur.fetchone()
    posted_rows, posted_rn = r[0] or 0, r[1] or 0
    posted_room_rev, posted_total_rev = r[2] or 0, r[3] or 0
    cur.execute("SELECT COUNT(*) FROM reservations_hackathon WHERE financial_status = 'Provisional'")
    provisional = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM reservations_hackathon WHERE property_date != stay_date")
    prop_mismatch = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM room_type_lookup")
    rt = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM rate_plan_lookup")
    rp = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM market_code_lookup")
    mc = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM market_macro_group_history")
    mh = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM channel_code_lookup")
    cc = cur.fetchone()[0]

    print(f"\n{'='*60}")
    print(f"VERIFICATION")
    print(f"{'='*60}")
    print(f"total_reservations           : {total_res:>8}")
    print(f"total_stay_rows              : {total_rows:>8}")
    print(f"cancelled_reservations       : {cancelled:>8}")
    print(f"posted_stay_rows             : {posted_rows:>8}")
    print(f"posted_otb_room_nights       : {posted_rn:>8}")
    print(f"posted_room_revenue          : {posted_room_rev:>12,.2f}")
    print(f"posted_total_revenue         : {posted_total_rev:>12,.2f}")
    print(f"provisional_row_count        : {provisional:>8}")
    print(f"property_date_mismatch       : {prop_mismatch:>8}")
    print(f"room_type_lookup             : {rt:>8}")
    print(f"rate_plan_lookup             : {rp:>8}")
    print(f"market_code_lookup           : {mc:>8}")
    print(f"market_macro_group_history   : {mh:>8}")
    print(f"channel_code_lookup          : {cc:>8}")
    print(f"{'='*60}\n")


# ─── MAIN ──────────────────────────────────────────────────────────────────────

async def main():
    anchor_date = datetime.now().strftime("%Y-%m-%d")
    print(f"ETL started — anchor date: {anchor_date}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print("\n1. Getting dataset revision...")
        dataset_revision = await scrape_dataset_revision(page)
        print(f"  Revision: {dataset_revision}")

        print("\n2. Scraping reference tables...")
        room_types, market_codes, channel_codes, rate_plans, macro_history = await scrape_reference(page)

        print("\n3. Scraping reservation list...")
        res_ids, pages_scraped = await scrape_reservation_ids(page)
        print(f"  Total: {len(res_ids)} IDs across {pages_scraped} pages")

        print(f"\n4. Scraping {len(res_ids)} reservation details...")
        all_rows = []
        for i, res_id in enumerate(res_ids):
            try:
                rows = await scrape_reservation_detail(page, res_id)
                all_rows.extend([transform_row(r) for r in rows])
            except Exception as e:
                print(f"  ERROR on {res_id}: {e}")
            if (i + 1) % 50 == 0:
                print(f"  {i+1}/{len(res_ids)} done ({len(all_rows)} rows)")
        await browser.close()

    print(f"\nTotal rows scraped: {len(all_rows)}")

    seen = {}
    for r in all_rows:
        key = (r["reservation_id"], r["stay_date"])
        if r["reservation_id"] and r["stay_date"]:
            seen[key] = r
    deduped = list(seen.values())
    print(f"After dedup: {len(deduped)} unique rows")

    row_hash = hashlib.sha256(
        json.dumps(sorted(r["reservation_id"] + "|" + str(r["stay_date"]) for r in deduped)).encode()
    ).hexdigest()

    print("\n5. Generating SCRAPE_MANIFEST.json...")
    generate_scrape_manifest(res_ids, pages_scraped, anchor_date)

    print("\n6. Loading to database...")
    conn = psycopg2.connect(DB_CONN)
    load_lookups(conn, room_types, market_codes, channel_codes, rate_plans, macro_history)
    load_reservations(conn, deduped)
    insert_load_manifest(conn, dataset_revision, row_hash)

    print("\n7. Creating views...")
    create_views(conn)

    print("\n8. Verification...")
    verify(conn)
    conn.close()
    print("ETL complete.")


if __name__ == "__main__":
    asyncio.run(main())