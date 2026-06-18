
import hashlib
import json
import os
from pathlib import Path

import psycopg2
from fastapi import FastAPI, HTTPException

app = FastAPI()

DB_CONN = os.environ.get("HOTEL_DATABASE_URL")


def get_conn():
    return psycopg2.connect(DB_CONN)


def load_proof_data():
    """Read the committed etl/LOAD_PROOF.json if available."""
    proof_path = Path("etl/LOAD_PROOF.json")
    if proof_path.exists():
        with open(proof_path) as f:
            return json.load(f)
    return {}


def compute_live_fingerprint():
    """Recompute the reservation_stay_status_sha256 from the live DB."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        # Same logic as scripts/compute_load_fingerprint.py
        cur.execute("""
            SELECT reservation_id, reservation_status, financial_status,
                   stay_date, number_of_spaces,
                   daily_room_revenue_before_tax, daily_total_revenue_before_tax
            FROM reservations_hackathon
            ORDER BY reservation_id, stay_date
        """)
        rows = cur.fetchall()
        h = hashlib.sha256()
        for row in rows:
            line = "|".join(str(c) if c is not None else "" for c in row)
            h.update(line.encode() + b"\n")
        return h.hexdigest()
    finally:
        conn.close()


def get_dataset_revision():
    """Get the most recent dataset_revision from load_manifest."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT dataset_revision, row_hash
            FROM load_manifest
            ORDER BY scraped_at DESC NULLS LAST
            LIMIT 1
        """)
        row = cur.fetchone()
        return (row[0], row[1]) if row else (None, None)
    finally:
        conn.close()


def get_posted_row_count():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM reservations_hackathon
            WHERE financial_status = 'Posted'
              AND reservation_status != 'Cancelled'
        """)
        return cur.fetchone()[0]
    finally:
        conn.close()


@app.get("/health")
def health():
    """Required by the brief. Reviewer hits this before chat to confirm
    the live DB matches the committed LOAD_PROOF.json."""
    try:
        proof = load_proof_data()
        live_fingerprint = compute_live_fingerprint()
        dataset_rev, row_hash = get_dataset_revision()
        posted_count = get_posted_row_count()

        return {
            "status": "ok",
            "db_fingerprint": live_fingerprint,
            "db_fingerprint_matches_proof": (
                live_fingerprint == proof.get("reservation_stay_status_sha256")
            ),
            "dataset_revision": dataset_rev,
            "row_hash": row_hash,
            "financial_status_posted_only_rows": posted_count,
            "proof_committed_fingerprint": proof.get("reservation_stay_status_sha256", "not_found"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def root():
    return {"message": "Revenue Manager Agent. Chat UI at /chat (separate port).",
            "health": "/health"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("HEALTH_PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)