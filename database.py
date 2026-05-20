import sqlite3
import json
from datetime import datetime
from pathlib import Path
from config import DB_PATH


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                title           TEXT NOT NULL,
                company         TEXT NOT NULL,
                location        TEXT,
                url             TEXT UNIQUE,
                description     TEXT,
                salary_range    TEXT,
                job_type        TEXT,
                skills          TEXT,
                fit_score       INTEGER,
                fit_notes       TEXT,
                source          TEXT,
                discovered_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS applications (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id          INTEGER NOT NULL REFERENCES jobs(id),
                status          TEXT NOT NULL DEFAULT 'saved',
                applied_at      TIMESTAMP,
                last_updated    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes           TEXT,
                cover_letter    TEXT,
                tailored_resume TEXT
            );
        """)


def save_job(job: dict) -> int:
    with get_conn() as conn:
        skills = json.dumps(job.get("skills", []))
        try:
            cur = conn.execute(
                """INSERT INTO jobs (title, company, location, url, description,
                   salary_range, job_type, skills, fit_score, fit_notes, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job.get("title"), job.get("company"), job.get("location"),
                    job.get("url"), job.get("description"), job.get("salary_range"),
                    job.get("job_type"), skills, job.get("fit_score"),
                    job.get("fit_notes"), job.get("source"),
                ),
            )
            return cur.lastrowid
        except sqlite3.IntegrityError:
            row = conn.execute("SELECT id FROM jobs WHERE url = ?", (job.get("url"),)).fetchone()
            return row["id"] if row else -1


def get_job(job_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row:
            d = dict(row)
            d["skills"] = json.loads(d.get("skills") or "[]")
            return d
    return None


def list_jobs(min_score: int = 0) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE fit_score >= ? ORDER BY fit_score DESC, discovered_at DESC",
            (min_score,),
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["skills"] = json.loads(d.get("skills") or "[]")
            result.append(d)
        return result


def create_application(job_id: int) -> int:
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM applications WHERE job_id = ?", (job_id,)
        ).fetchone()
        if existing:
            return existing["id"]
        cur = conn.execute(
            "INSERT INTO applications (job_id, status) VALUES (?, 'saved')", (job_id,)
        )
        return cur.lastrowid


def update_application(job_id: int, **kwargs):
    kwargs["last_updated"] = datetime.now().isoformat()
    if "status" in kwargs and kwargs["status"] == "applied":
        kwargs.setdefault("applied_at", datetime.now().isoformat())

    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [job_id]
    with get_conn() as conn:
        conn.execute(
            f"UPDATE applications SET {fields} WHERE job_id = ?", values
        )


def list_applications() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT a.*, j.title, j.company, j.location, j.fit_score, j.url
               FROM applications a JOIN jobs j ON a.job_id = j.id
               ORDER BY a.last_updated DESC"""
        ).fetchall()
        return [dict(row) for row in rows]


def get_application(job_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT a.*, j.title, j.company, j.location, j.description, j.fit_score, j.url
               FROM applications a JOIN jobs j ON a.job_id = j.id
               WHERE a.job_id = ?""",
            (job_id,),
        ).fetchone()
        return dict(row) if row else None
