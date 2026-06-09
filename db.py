import json
import os
from pathlib import Path

import aiosqlite

_download_dir = os.getenv("DOWNLOAD_DIR", "downloads")
_db_dir = os.getenv("DB_DIR", "data")
DB_PATH = os.path.join(_db_dir, "jobs.db")


async def init_db():
    Path(_db_dir).mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        await db.commit()


async def save_job(job: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO jobs (id, data, created_at) VALUES (?, ?, ?)",
            (job["id"], json.dumps(job, ensure_ascii=False), job["created_at"]),
        )
        await db.commit()


async def load_jobs() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT data FROM jobs ORDER BY created_at ASC") as cur:
            rows = await cur.fetchall()
    return [json.loads(row[0]) for row in rows]
