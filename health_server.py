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
    proof_path = Path("etl/LOAD_PROOF.json")
    if proof_path.exists():
        with open(proof_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def compute_live_fingerprint():
    """
    Must match scripts/compute_load_fingerprint.py exactly.
    """

    conn = get_conn()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT reservation_id,
                   stay_date::text,
                   financial_status
            FROM reservations_hackathon
            ORDER BY reservation_id,
                     stay_date,
                     financial_status
            """
        )

        rows = cur.fetchall()

        lines = [
            f"{reservation_id}|{stay_date}|{financial_status}"
            for reservation_id, stay_date, financial_status in rows
        ]

        payload = "\n".join(lines).encode("utf-8")

        return hashlib.sha256(payload).hexdigest()

    finally:
        conn.close()


def get_dataset_revision():
    conn = get_conn()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT dataset_revision,
                   row_hash
            FROM load_manifest
            ORDER BY load_id DESC
            LIMIT 1
            """
        )

        row = cur.fetchone()

        return (row[0], row[1]) if row else (None, None)

    finally:
        conn.close()


def get_posted_row_count():
    conn = get_conn()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT COUNT(*)
            FROM reservations_hackathon
            WHERE reservation_status <> 'Cancelled'
              AND financial_status = 'Posted'
            """
        )

        return cur.fetchone()[0]

    finally:
        conn.close()


@app.get("/health")
def health():
    try:
        proof = load_proof_data()

        live_fingerprint = compute_live_fingerprint()

        dataset_revision, row_hash = get_dataset_revision()

        posted_count = get_posted_row_count()

        return {
            "status": "ok",
            "db_fingerprint": live_fingerprint,
            "db_fingerprint_matches_proof": (
                live_fingerprint
                == proof.get("reservation_stay_status_sha256")
            ),
            "dataset_revision": dataset_revision,
            "row_hash": row_hash,
            "financial_status_posted_only_rows": posted_count,
            "proof_committed_fingerprint": proof.get(
                "reservation_stay_status_sha256",
                "not_found",
            ),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def root():
    return {
        "message": "Revenue Manager Agent",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("HEALTH_PORT", 8001))

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
    )