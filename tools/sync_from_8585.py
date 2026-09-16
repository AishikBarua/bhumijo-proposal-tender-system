#!/usr/bin/env python3
"""
One-off: bring the 8787 database up to date with the 8585 CSV export.

Everything EXCEPT the title is taken from the CSV. Titles stay as they
are in the database (explicit choice - the 8787 spellings are kept).

Usage:
    python -m tools.sync_from_8585 --csv ..\\_sync_source_8585.csv --dry-run
    python -m tools.sync_from_8585 --csv ..\\_sync_source_8585.csv --apply
"""
from __future__ import annotations
import argparse, csv, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database.audit_log import Actor
from backend.database.category_mapping import map_category
from backend.database.repositories import proposal_repo, reference_repo
from backend.models import proposal as proposal_model

ACTOR = Actor(username="sync-from-8585")

# Titles that were corrected on 8585 after the migration. The database keeps
# its own spelling; this map only exists so the two rows can be paired up.
TITLE_ALIASES = {
    "ncc park": "ncc beparipara park",
    "child friendly play space_save the children": "child friendly play space",
    "uniliver toilet renovation project": "unilever toilet renovation project",
    "sathibari commercial complex rangpur": "shotibari commercial complex, rangpur",
    "sylhel hospital": "sylhet hospital",
}

CSV_TO_LEGACY = {
    "Category": "category", "Client": "client", "Value": "value",
    "Opening Date": "openDate", "Closing Date": "closeDate",
    "Start Date": "startDate", "End Date": "endDate",
    "Status": "status", "Result": "result", "Responsible": "responsible",
    "Contract": "contract", "Remarks": "remark",
}

# Columns this script is allowed to write. 'title' is deliberately absent.
SYNCED = [
    "original_category", "category_id", "client_name",
    "value_amount", "value_currency", "original_value", "responsible",
    "open_date", "close_date", "start_date", "end_date",
    "original_open_date", "original_close_date",
    "original_start_date", "original_end_date",
    "status", "result", "contract", "remark",
]


def norm(s) -> str:
    return " ".join(str(s or "").split()).strip().lower()


def key_of(title: str, entity: str) -> str:
    t = norm(title)
    return TITLE_ALIASES.get(t, t) + "||" + norm(entity)


def index(rows, title_key, entity_key):
    seen, out = {}, {}
    for r in rows:
        k = key_of(r[title_key], r[entity_key])
        n = seen.get(k, 0)
        seen[k] = n + 1
        out[f"{k}#{n}"] = r
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.apply == args.dry_run:
        print("Pick exactly one of --apply / --dry-run")
        return 2

    with open(args.csv, encoding="utf-8-sig", newline="") as f:
        csv_rows = list(csv.DictReader(f))
    db_rows = proposal_repo.list_all(limit=100000)
    if isinstance(db_rows, dict):
        db_rows = db_rows.get("items", db_rows.get("rows", []))

    src = index(csv_rows, "Title", "Entity")
    dst = index(db_rows, "title", "entity_code")

    only_csv = sorted(set(src) - set(dst))
    only_db = sorted(set(dst) - set(src))
    if only_csv or only_db:
        print("REFUSING: the two sides do not line up 1:1.")
        for k in only_csv[:20]:
            print("  only in CSV:", k)
        for k in only_db[:20]:
            print("  only in DB :", k)
        return 1

    changed = 0
    field_count = 0
    for k, s in src.items():
        d = dst[k]
        legacy = {csvk: s.get(csvk, "") or "" for csvk in CSV_TO_LEGACY}
        legacy = {CSV_TO_LEGACY[a]: b for a, b in legacy.items()}
        legacy["title"] = d["title"]          # keep the database title
        legacy["entity"] = d["entity_code"]
        legacy["id"] = d["id"]
        row = proposal_model.from_legacy_dict(legacy)

        mapped, _ = map_category(row["original_category"])
        row["category_id"] = reference_repo.ensure_category(mapped)

        payload = {c: row[c] for c in SYNCED if c in row}
        deltas = [c for c, v in payload.items()
                  if (d.get(c) or "") != (v or "") and not (
                      c in ("value_amount",) and
                      (d.get(c) is None) == (v is None) and
                      (d.get(c) or 0) == (v or 0))]
        if not deltas:
            continue
        changed += 1
        field_count += len(deltas)
        print(f"[{d['entity_code']:4}] {d['title'][:52]:52} -> {', '.join(deltas)}")
        if args.apply:
            proposal_repo.update(d["id"], payload, actor=ACTOR)

    print()
    print(f"{'APPLIED' if args.apply else 'DRY RUN'}: "
          f"{changed} records, {field_count} fields. Titles untouched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
