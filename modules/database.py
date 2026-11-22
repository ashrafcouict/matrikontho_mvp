
import csv
import io
import json
import sqlite3
from datetime import datetime
from pathlib import Path


DB_PATH = Path("data") / "matrikontho.db"


def _get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    return connection


def init_db():
    """Create the assessment table if it does not already exist."""
    with _get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                patient_name TEXT,
                pregnancy_status TEXT,
                gestational_weeks INTEGER,
                transcript TEXT,
                extraction_method TEXT,
                extraction_json TEXT,
                risk_level TEXT,
                reasons TEXT,
                recommendation TEXT,
                advice TEXT,
                referral_sms TEXT
            )
            """
        )


def save_assessment(
    transcript,
    extraction,
    result,
    advice=None,
    sms=None,
    gestational_weeks=None,
    pregnancy_status=None,
    patient_name=None,
):
    """Save one assessment and return its database ID."""
    extraction = extraction if isinstance(extraction, dict) else {}
    result = result if isinstance(result, dict) else {}

    advice_text = (
        "\n".join(advice)
        if isinstance(advice, list)
        else str(advice or "")
    )

    reasons = result.get("reasons", [])

    with _get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO assessments (
                created_at,
                patient_name,
                pregnancy_status,
                gestational_weeks,
                transcript,
                extraction_method,
                extraction_json,
                risk_level,
                reasons,
                recommendation,
                advice,
                referral_sms
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(timespec="seconds"),
                patient_name,
                pregnancy_status,
                gestational_weeks,
                transcript or "",
                extraction.get("extraction_method", "unknown"),
                json.dumps(extraction, ensure_ascii=False),
                result.get("risk_level", "UNKNOWN"),
                json.dumps(reasons, ensure_ascii=False),
                result.get("recommendation", ""),
                advice_text,
                sms or "",
            ),
        )

        return cursor.lastrowid


def list_assessments(limit=200):
    """Return recent assessments as dictionaries for the dashboard."""
    with _get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                created_at,
                patient_name,
                pregnancy_status,
                gestational_weeks,
                transcript,
                extraction_method,
                risk_level,
                reasons,
                recommendation,
                advice,
                referral_sms
            FROM assessments
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()

    records = []

    for row in rows:
        record = dict(row)

        try:
            record["reasons"] = json.loads(record["reasons"] or "[]")
        except json.JSONDecodeError:
            record["reasons"] = []

        records.append(record)

    return records


def export_csv():
    """Return all assessment records as CSV text."""
    with _get_connection() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM assessments
            ORDER BY id DESC
            """
        ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)

    if rows:
        writer.writerow(rows[0].keys())

        for row in rows:
            writer.writerow([row[key] for key in row.keys()])
    else:
        writer.writerow(["No assessment records"])

    return output.getvalue()
