"""
Nightly backup — the thing that was missing entirely.

The old system kept 40 snapshots per file on the SAME disk as the live data,
so a disk failure took both. This writes a single consistent copy of the
database somewhere else, using SQLite's own backup API so it is safe to run
while people are working.

Point BHUMIJO_BACKUP_DIR at a different disk or a network drive.
"""

from __future__ import annotations

import gzip
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from ..config import get_logger, settings
from ..database.connection import get_connection

log = get_logger("jobs.backup")

KEEP_DAILY = 30


def run(destination: Path | None = None) -> Path:
    destination = destination or settings.backup_dir
    destination.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = destination / f"bhumijo_{stamp}.db"

    # A live-safe copy: SQLite handles the locking for us.
    source = get_connection()
    backup_conn = sqlite3.connect(target)
    try:
        source.backup(backup_conn)
    finally:
        backup_conn.close()

    compressed = target.with_suffix(".db.gz")
    with target.open("rb") as raw, gzip.open(compressed, "wb") as gz:
        shutil.copyfileobj(raw, gz)
    target.unlink()

    log.info("backup written: %s (%.1f KB)", compressed.name, compressed.stat().st_size / 1024)
    prune(destination)
    return compressed


def prune(destination: Path, keep: int = KEEP_DAILY) -> int:
    files = sorted(destination.glob("bhumijo_*.db.gz"), key=lambda p: p.stat().st_mtime)
    removed = 0
    while len(files) > keep:
        old = files.pop(0)
        try:
            old.unlink()
            removed += 1
        except OSError as exc:
            log.warning("could not remove old backup %s: %s", old.name, exc)
    if removed:
        log.info("pruned %d old backup(s)", removed)
    return removed


def verify_destination() -> tuple[bool, str]:
    """
    Warn if backups are being written to the same disk as the live data —
    which would repeat the exact weakness this job exists to fix.
    """
    try:
        backup_dir = settings.backup_dir.resolve()
        data_dir = settings.data_dir.resolve()
        backup_dir.mkdir(parents=True, exist_ok=True)

        if backup_dir.drive or data_dir.drive:
            # Windows: compare the drive letter.
            same = backup_dir.drive.lower() == data_dir.drive.lower()
        else:
            # Linux/macOS: compare the filesystem the paths actually live on.
            same = backup_dir.stat().st_dev == data_dir.stat().st_dev
    except OSError as exc:
        return True, f"could not check the backup destination: {exc}"
    if same:
        return False, (
            f"backups are going to {settings.backup_dir}, which is the same disk "
            f"as the live data. Set BHUMIJO_BACKUP_DIR to another disk."
        )
    return True, "backup destination is on a different disk"


if __name__ == "__main__":
    ok, message = verify_destination()
    if not ok:
        log.warning(message)
    run()
