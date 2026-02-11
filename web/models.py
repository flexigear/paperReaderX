"""SQLite database models and CRUD operations using aiosqlite."""

import aiosqlite
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "papers.db"


def new_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def init_db():
    """Create tables if they don't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS papers (
                id          TEXT PRIMARY KEY,
                title       TEXT,
                authors     TEXT,
                filename    TEXT,
                pdf_path    TEXT,
                fingerprint TEXT UNIQUE,
                text        TEXT,
                page_count  INTEGER,
                created_at  TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id          TEXT PRIMARY KEY,
                paper_id    TEXT REFERENCES papers(id),
                lang        TEXT,
                content     TEXT DEFAULT '',
                status      TEXT DEFAULT 'pending',
                created_at  TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id          TEXT PRIMARY KEY,
                paper_id    TEXT REFERENCES papers(id),
                role        TEXT,
                content     TEXT,
                created_at  TEXT
            )
        """)
        await db.commit()


def _connect():
    """Return a new aiosqlite connection context manager."""
    db = aiosqlite.connect(DB_PATH)
    return db


# --- Papers ---

async def find_paper_by_fingerprint(fingerprint: str) -> dict | None:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM papers WHERE fingerprint = ?", (fingerprint,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def insert_paper(paper: dict) -> None:
    async with _connect() as db:
        await db.execute(
            """INSERT INTO papers (id, title, authors, filename, pdf_path,
               fingerprint, text, page_count, created_at)
               VALUES (:id, :title, :authors, :filename, :pdf_path,
               :fingerprint, :text, :page_count, :created_at)""",
            paper,
        )
        await db.commit()


async def list_papers() -> list[dict]:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, title, authors, filename, page_count, created_at FROM papers ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        papers = [dict(r) for r in rows]
        for p in papers:
            c2 = await db.execute(
                "SELECT lang, status FROM results WHERE paper_id = ?", (p["id"],)
            )
            result_rows = await c2.fetchall()
            p["results"] = {r["lang"]: r["status"] for r in result_rows}
        return papers


async def get_paper(paper_id: str) -> dict | None:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM papers WHERE id = ?", (paper_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


# --- Results ---

async def create_result(paper_id: str, lang: str) -> str:
    rid = new_id()
    async with _connect() as db:
        await db.execute(
            """INSERT INTO results (id, paper_id, lang, content, status, created_at)
               VALUES (?, ?, ?, '', 'pending', ?)""",
            (rid, paper_id, lang, now_iso()),
        )
        await db.commit()
    return rid


async def get_result(paper_id: str, lang: str) -> dict | None:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM results WHERE paper_id = ? AND lang = ?",
            (paper_id, lang),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_result_status(result_id: str, status: str) -> None:
    async with _connect() as db:
        await db.execute(
            "UPDATE results SET status = ? WHERE id = ?", (status, result_id)
        )
        await db.commit()


async def append_result_content(result_id: str, chunk: str) -> None:
    async with _connect() as db:
        await db.execute(
            "UPDATE results SET content = content || ? WHERE id = ?",
            (chunk, result_id),
        )
        await db.commit()


async def get_result_content(result_id: str) -> str:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT content FROM results WHERE id = ?", (result_id,)
        )
        row = await cursor.fetchone()
        return row["content"] if row else ""


# --- Chat Messages ---

async def add_chat_message(paper_id: str, role: str, content: str) -> str:
    mid = new_id()
    async with _connect() as db:
        await db.execute(
            """INSERT INTO chat_messages (id, paper_id, role, content, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (mid, paper_id, role, content, now_iso()),
        )
        await db.commit()
    return mid


async def get_chat_history(paper_id: str) -> list[dict]:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT role, content FROM chat_messages WHERE paper_id = ? ORDER BY created_at",
            (paper_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
