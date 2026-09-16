#!/usr/bin/env python3
"""
One-off migration: the JSONL/JSON files -> the database.

Rules this script obeys:
  * It never touches the source files. They are opened read-only.
  * Counts in must equal counts out, or it fails loudly.
  * Every original string is preserved beside its cleaned value.
  * Anything it could not read confidently is REPORTED, never guessed
    silently — see the review file it writes at the end.
  * It is re-runnable: --reset rebuilds from scratch.

Usage:
    python -m backend.migrate                 # migrate into the database
    python -m backend.migrate --reset         # wipe and rebuild first
    python -m backend.migrate --dry-run       # read and report, write nothing
    python -m backend.migrate --source PATH   # override the legacy folder
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from .config import get_logger, settings
from .database.audit_log import Actor
from .database.category_mapping import SHORTLIST, map_category
from .database.connection import (StorageUnavailable, get_connection,
                                  run_migrations, transaction)
from .database.repositories import reference_repo
from .models import client as client_model
from .models import grant as grant_model
from .models import proposal as proposal_model
from .models.enums import Entity

log = get_logger("migrate")

MIGRATOR = Actor(username="migration")

ENTITY_FOLDERS = {e.folder_name: e.value for e in Entity}
ENTITY_FOLDERS["Other"] = ""


class MigrationError(Exception):
    pass


# --- reading the old files -------------------------------------------

def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    items = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError as exc:
            log.error("%s line %d is not valid JSON: %s", path.name, lineno, exc)
            raise MigrationError(f"{path}:{lineno} is not valid JSON") from exc
    return items


def read_legacy(source: Path) -> dict[str, list[dict]]:
    proposals: list[dict] = []
    for folder in sorted((source / "proposals").glob("*")):
        if not folder.is_dir():
            continue
        rows = read_jsonl(folder / "proposals.jsonl")
        log.info("  %-22s %3d proposals", folder.name, len(rows))
        proposals.extend(rows)

    grants = read_jsonl(source / "Hitlist" / "programs.jsonl")
    log.info("  %-22s %3d grant programmes", "Hitlist", len(grants))

    clients_file = source / "clients" / "clients.json"
    clients: list[dict] = []
    if clients_file.exists():
        payload = json.loads(clients_file.read_text(encoding="utf-8"))
        clients = payload.get("clients", [])
    log.info("  %-22s %3d clients", "clients", len(clients))

    return {"proposals": proposals, "grants": grants, "clients": clients}


# --- duplicate ids ----------------------------------------------------
# The JSONL files had no unique constraint, so the same id could appear
# twice and nothing would complain. It happens. Rather than crash, keep the
# first occurrence, drop the rest, and report every one of them.

def dedupe(rows: list[dict], record_type: str) -> tuple[list[dict], list[dict]]:
    seen: dict[str, dict] = {}
    unique: list[dict] = []
    review: list[dict] = []

    for item in rows:
        rid = str(item.get("id", "")).strip()
        if not rid:
            unique.append(item)
            continue
        if rid in seen:
            identical = json.dumps(seen[rid], sort_keys=True) == json.dumps(item, sort_keys=True)
            review.append({
                "record": record_type,
                "id": rid,
                "field": "id",
                "value": str(item.get("name") or item.get("title") or ""),
                "why": ("exact duplicate of an earlier row — kept one"
                        if identical else
                        "DUPLICATE ID with different content — kept the first, "
                        "please check which is correct"),
            })
            log.warning("%s id %s appears more than once — keeping the first", record_type, rid)
            continue
        seen[rid] = item
        unique.append(item)

    return unique, review


# --- writing ----------------------------------------------------------

def seed_categories() -> dict[str, int]:
    ids = {}
    for order, name in enumerate(SHORTLIST, start=1):
        ids[name] = reference_repo.ensure_category(name, sort_order=order)
    return ids


def migrate_proposals(rows: list[dict], category_ids: dict[str, int]) -> list[dict]:
    review: list[dict] = []
    with transaction() as conn:
        for item in rows:
            row = proposal_model.from_legacy_dict(item)
            pid = row.get("id")
            if not pid:
                review.append({"record": "proposal", "id": "(none)",
                               "field": "id", "value": "", "why": "record has no id"})
                continue

            original_category = item.get("category", "") or ""
            mapped, confident = map_category(original_category)
            row["original_category"] = original_category
            row["category_id"] = category_ids.get(mapped)
            if not confident:
                review.append({"record": "proposal", "id": pid, "field": "category",
                               "value": original_category,
                               "why": f"not in the mapping — filed as {mapped}"})

            # money that could not be read confidently
            from .models.common import parse_money
            money = parse_money(item.get("value"))
            if money.needs_review:
                review.append({"record": "proposal", "id": pid, "field": "value",
                               "value": money.original,
                               "why": f"read as {money.amount} {money.currency} — please confirm"})

            # dates present in the file but unreadable
            for legacy_key, column in (("openDate", "open_date"), ("closeDate", "close_date"),
                                       ("startDate", "start_date"), ("endDate", "end_date")):
                raw = item.get(legacy_key, "")
                if raw and row.get(column) is None:
                    review.append({"record": "proposal", "id": pid, "field": legacy_key,
                                   "value": raw, "why": "not a date I can read — left blank"})

            entity = item.get("entity", "")
            if entity and entity not in {e.value for e in Entity}:
                review.append({"record": "proposal", "id": pid, "field": "entity",
                               "value": entity, "why": "unknown entity — left unassigned"})
                row["entity_code"] = None

            # Keep what the file said, exactly. Do not invent one for the
            # 156 records that never had this field.
            row["original_created_at"] = str(item.get("createdAt", "") or "")

            columns = [k for k in row if k is not None]
            placeholders = ", ".join("?" for _ in columns)
            conn.execute(
                f"INSERT INTO proposals ({', '.join(columns)}) VALUES ({placeholders})",
                [row[c] for c in columns],
            )
    return review


def migrate_grants(rows: list[dict]) -> list[dict]:
    review: list[dict] = []
    with transaction() as conn:
        for item in rows:
            row = grant_model.from_legacy_dict(item)
            gid = row.get("id")
            if not gid:
                review.append({"record": "grant", "id": "(none)", "field": "id",
                               "value": "", "why": "record has no id"})
                continue

            raw_closing = item.get("closing", "")
            if raw_closing and row.get("closing_date") is None:
                review.append({"record": "grant", "id": gid, "field": "closing",
                               "value": raw_closing,
                               "why": "not a date I can read — left blank"})

            columns = list(row.keys())
            placeholders = ", ".join("?" for _ in columns)
            conn.execute(
                f"INSERT INTO grant_programmes ({', '.join(columns)}) VALUES ({placeholders})",
                [row[c] for c in columns],
            )
    return review


def migrate_clients(rows: list[dict]) -> list[dict]:
    review: list[dict] = []
    with transaction() as conn:
        for item in rows:
            row = client_model.from_legacy_dict(item)
            cid = row.get("id")
            if not cid:
                review.append({"record": "client", "id": "(none)", "field": "id",
                               "value": "", "why": "record has no id"})
                continue

            entity = item.get("entity", "")
            if entity and entity not in {e.value for e in Entity}:
                review.append({"record": "client", "id": cid, "field": "entity",
                               "value": entity, "why": "unknown entity — left unassigned"})
                row["entity_code"] = None

            from .models.common import parse_money
            money = parse_money(item.get("value"))
            if money.needs_review:
                review.append({"record": "client", "id": cid, "field": "value",
                               "value": money.original,
                               "why": f"read as {money.amount} {money.currency} — please confirm"})

            columns = list(row.keys())
            placeholders = ", ".join("?" for _ in columns)
            conn.execute(
                f"INSERT INTO clients ({', '.join(columns)}) VALUES ({placeholders})",
                [row[c] for c in columns],
            )
    return review


# --- verification -----------------------------------------------------

def verify(expected: dict[str, int]) -> None:
    conn = get_connection()
    actual = {
        "proposals": conn.execute("SELECT COUNT(*) FROM proposals").fetchone()[0],
        "grants": conn.execute("SELECT COUNT(*) FROM grant_programmes").fetchone()[0],
        "clients": conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0],
    }
    problems = [
        f"{name}: read {expected[name]} from the files but the database holds {actual[name]}"
        for name in expected
        if expected[name] != actual[name]
    ]
    if problems:
        for p in problems:
            log.error(p)
        raise MigrationError("counts do not match; nothing can be trusted — see above")

    log.info("verified: %d proposals, %d grant programmes, %d clients",
             actual["proposals"], actual["grants"], actual["clients"])


def reset_database() -> None:
    with transaction() as conn:
        for table in ("audit_log", "attachments", "proposals",
                      "grant_programmes", "clients"):
            conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM categories")
    log.info("cleared existing records")


def write_review_file(review: list[dict]) -> Path | None:
    if not review:
        return None
    settings.ensure_dirs()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = settings.data_dir / f"migration_review_{stamp}.csv"
    import csv
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["record", "id", "field", "value", "why"])
        writer.writeheader()
        writer.writerows(review)
    return path


# --- entry point ------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate the JSONL data into the database")
    parser.add_argument("--source", type=Path, default=settings.legacy_data_dir,
                        help="the old proposal_backups folder")
    parser.add_argument("--reset", action="store_true", help="clear existing records first")
    parser.add_argument("--dry-run", action="store_true", help="read and report, write nothing")
    args = parser.parse_args(argv)

    source = args.source.resolve()
    if not source.exists():
        log.error("source folder not found: %s", source)
        return 2

    log.info("reading from %s (read-only)", source)
    data = read_legacy(source)
    expected = {k: len(v) for k, v in data.items()}
    log.info("read %d proposals, %d grant programmes, %d clients",
             expected["proposals"], expected["grants"], expected["clients"])

    if args.dry_run:
        log.info("dry run — nothing written")
        return 0

    try:
        run_migrations()
    except StorageUnavailable as exc:
        log.error("%s", exc)
        return 4

    if args.reset:
        reset_database()

    conn = get_connection()
    if conn.execute("SELECT COUNT(*) FROM proposals").fetchone()[0]:
        log.error("the database already holds proposals — use --reset to rebuild")
        return 3

    category_ids = seed_categories()
    review: list[dict] = []

    # Drop duplicate ids before writing, and adjust what we expect to find.
    for key, record_type in (("proposals", "proposal"),
                             ("grants", "grant"),
                             ("clients", "client")):
        data[key], dupe_review = dedupe(data[key], record_type)
        review += dupe_review
        if dupe_review:
            log.warning("%s: %d duplicate id(s) removed, %d unique record(s) remain",
                        key, len(dupe_review), len(data[key]))
        expected[key] = len(data[key])

    review += migrate_proposals(data["proposals"], category_ids)
    review += migrate_grants(data["grants"])
    review += migrate_clients(data["clients"])

    verify(expected)

    # The migration itself is the first entry in the audit trail: from here on,
    # every change to these records has a name and a timestamp against it.
    from .database.audit_log import record
    from .database.connection import transaction
    with transaction() as conn:
        record(
            "create", "migration", source.name,
            actor=MIGRATOR,
            summary=(f"imported {expected['proposals']} proposals, "
                     f"{expected['grants']} grant programmes, "
                     f"{expected['clients']} clients from {source}"),
            after={"counts": expected, "items_needing_review": len(review)},
            conn=conn,
        )

    path = write_review_file(review)
    if path:
        log.warning("%d value(s) need a human eye — written to %s", len(review), path.name)
        by_field: dict[str, int] = {}
        for item in review:
            key = f"{item['record']}.{item['field']}"
            by_field[key] = by_field.get(key, 0) + 1
        for key, count in sorted(by_field.items(), key=lambda kv: -kv[1]):
            log.warning("    %-22s %d", key, count)
    else:
        log.info("every value read cleanly — no review needed")

    log.info("migration complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
