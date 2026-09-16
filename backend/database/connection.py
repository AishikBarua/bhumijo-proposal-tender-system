"""
The only place that opens a database connection.

SQLite is used in WAL mode with foreign keys on and a busy timeout, which is
what makes two people saving at the same moment safe rather than a coin toss.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from ..config import get_logger, settings

log = get_logger("database.connection")

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

_local = threading.local()


def _configure(conn: sqlite3.Connection) -> None:
    conn.row_factory = sqlite3.Row

    # WAL is what lets one person read while another writes, so it is the
    # mode we want. It relies on shared-memory locking, which network drives
    # and some mounted folders do not support — there, fall back to the older
    # journal rather than refusing to start.
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.OperationalError:
        log.warning(
            "this drive does not support WAL — falling back to the older "
            "journal mode. Two people writing at the exact same moment will "
            "queue rather than run side by side. If the database is on a "
            "network share, moving it to a local disk restores WAL."
        )
        conn.execute("PRAGMA journal_mode = DELETE")

    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")


class StorageUnavailable(Exception):
    """The data folder cannot hold a database — said plainly, not as a stack trace."""


def get_connection() -> sqlite3.Connection:
    """One connection per thread, reused."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        settings.ensure_dirs()
        try:
            conn = sqlite3.connect(settings.database_path, check_same_thread=False)
            _configure(conn)
            # sqlite3.connect() succeeds on almost anything; the first WRITE is
            # what fails on an unsupported drive. Find out now, so the problem
            # is reported here in plain words rather than as a stack trace
            # halfway through a migration.
            conn.execute("CREATE TABLE IF NOT EXISTS _write_probe (x INTEGER)")
            conn.execute("DROP TABLE IF EXISTS _write_probe")
            conn.commit()
        except sqlite3.OperationalError as exc:
            raise StorageUnavailable(
                f"Could not open the database at {settings.database_path}.\n"
                f"  {exc}\n\n"
                f"This usually means the folder is on a drive that does not "
                f"support the file locking a database needs — a network share, "
                f"a synced folder (OneDrive, Dropbox, Google Drive), or a "
                f"virtual mount.\n"
                f"Set BHUMIJO_DATA_DIR in .env to a folder on a local disk."
            ) from exc
        _local.conn = conn
    return conn


def close_connection() -> None:
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """
    Everything inside either happens completely or not at all.

    This is the guarantee the JSONL files could never give: a half-written
    save is impossible.
    """
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()


# --- migrations -------------------------------------------------------

def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename   TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()


def applied_migrations(conn: sqlite3.Connection) -> set[str]:
    _ensure_migrations_table(conn)
    rows = conn.execute("SELECT filename FROM schema_migrations").fetchall()
    return {row["filename"] for row in rows}


def run_migrations() -> list[str]:
    """Apply every .sql file in migrations/ that has not run yet, in order."""
    conn = get_connection()
    done = applied_migrations(conn)
    applied: list[str] = []

    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.name in done:
            continue
        log.info("applying migration %s", path.name)
        conn.executescript(path.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO schema_migrations (filename) VALUES (?)", (path.name,))
        conn.commit()
        applied.append(path.name)

    if applied:
        log.info("applied %d migration(s)", len(applied))
    else:
        log.info("database schema already up to date")
    return applied


def database_exists() -> bool:
    return settings.database_path.exists() and settings.database_path.stat().st_size > 0
