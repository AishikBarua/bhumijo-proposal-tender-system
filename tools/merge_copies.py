#!/usr/bin/env python3
"""
Merge two diverged copies of the tracker's data into one.

Two copies of the old 8585 tracker were in use at once, and they drifted
apart in BOTH directions — each held records and edits the other did not.
Taking either one wholesale would have thrown away real work:

    proposals   D:\\Tracker had 3 the other lacked, and newer edits on 9
    clients     D:\\Tracker had 2 the other lacked
    grants      the zip had 2 D:\\Tracker lacked

So neither is "the" copy. This takes the union and merges field by field.

The rule, in order:
    1. A record in only one copy is kept as-is.
    2. Where both have it and a field is empty in one, take the filled one.
    3. Where both have a different non-empty value, PREFER is used — and
       every such case is reported, because that is a real conflict and a
       person should see it rather than have it silently resolved.

Nothing is deleted. Run it, read the report, then import.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

# Which copy wins when both have a different non-empty value.
PREFER = "live"          # "live" = D:\Tracker, "other" = the uploaded copy

# Decisions taken with the user, applied by id. Recorded here rather than
# applied by hand so the merge stays repeatable and auditable.
OVERRIDES = {
    "grant": {
        # The two copies disagreed on whether this was dropped.
        # Confirmed with the user: still open.
        "166": {"status": "Yet to Submit"},

        # The live copy spells it "Bllomberg". Same organisation, one copy
        # simply has a typo — preferring the live value here would have
        # carried the misspelling forward for ever.
        "175": {"name": "Bloomberg Global Mayors Challenge 2026"},
    },
}

ENTITY_FOLDERS = ["Facility Management", "Planning & Design", "Technology",
                  "WASH-Toilets", "Other"]

report: list[str] = []
conflicts: list[str] = []


def log(line: str) -> None:
    report.append(line)
    print(line)


# --- reading ------------------------------------------------------------

def read_proposals(base: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for folder in (base / "proposals").glob("*"):
        path = folder / "proposals.jsonl"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                record = json.loads(line)
                record["_entity_folder"] = folder.name
                out[record["id"]] = record
    return out


def read_grants(base: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    path = base / "Hitlist" / "programs.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            record = json.loads(line)
            out[str(record["id"])] = record
    return out


def read_clients(base: Path) -> dict[str, dict]:
    path = base / "clients" / "clients.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {c["id"]: c for c in data.get("clients", [])}


# --- merging ------------------------------------------------------------

def is_empty(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def merge_record(kind: str, key: str, live: dict, other: dict,
                 label: str) -> dict:
    merged = dict(live)
    for field in set(live) | set(other):
        if field.startswith("_"):
            continue
        a, b = live.get(field), other.get(field)
        if a == b:
            continue

        if is_empty(a) and not is_empty(b):
            merged[field] = b
            log(f"      {field}: filled from the other copy -> {str(b)[:60]!r}")
        elif is_empty(b):
            pass  # live already has it
        else:
            keep = a if PREFER == "live" else b
            merged[field] = keep
            conflicts.append(
                f"{kind} {key} ({label}) field {field!r}: "
                f"live={str(a)[:50]!r} other={str(b)[:50]!r} -> kept {'live' if PREFER=='live' else 'other'}")
            log(f"      {field}: CONFLICT, kept the live value {str(keep)[:50]!r}")

    for field, value in OVERRIDES.get(kind, {}).get(key, {}).items():
        if merged.get(field) != value:
            log(f"      {field}: override applied -> {value!r}")
            merged[field] = value
    return merged


def merge(kind: str, live: dict[str, dict], other: dict[str, dict],
          name_field: str) -> dict[str, dict]:
    log(f"\n=== {kind.upper()} ===")
    only_live = set(live) - set(other)
    only_other = set(other) - set(live)
    both = set(live) & set(other)

    log(f"  in the live copy only : {len(only_live)}")
    log(f"  in the uploaded only  : {len(only_other)}")
    log(f"  in both               : {len(both)}")

    merged = dict(live)

    for key in sorted(only_other):
        merged[key] = other[key]
        label = other[key].get(name_field, "")
        log(f"    ADDED from the uploaded copy: {key} — {str(label)[:60]}")

    changed = 0
    for key in sorted(both):
        if json.dumps(live[key], sort_keys=True, default=str) == \
           json.dumps(other[key], sort_keys=True, default=str):
            continue
        changed += 1
        label = live[key].get(name_field, "")
        log(f"    merging {key} — {str(label)[:60]}")
        merged[key] = merge_record(kind, key, live[key], other[key], str(label)[:40])

    log(f"  {len(only_other)} added, {changed} merged, {len(merged)} total")
    return merged


# --- writing ------------------------------------------------------------

def write_proposals(base: Path, records: dict[str, dict]) -> None:
    grouped: dict[str, list] = {f: [] for f in ENTITY_FOLDERS}
    for record in records.values():
        folder = record.pop("_entity_folder", None) or "Other"
        grouped.setdefault(folder, []).append(record)

    for folder, items in grouped.items():
        path = base / "proposals" / folder / "proposals.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        text = "\n".join(json.dumps(r, ensure_ascii=False) for r in items)
        path.write_text(text + ("\n" if text else ""), encoding="utf-8")


def write_grants(base: Path, records: dict[str, dict]) -> None:
    def sort_key(r):
        try:
            return (0, int(r["id"]))
        except (TypeError, ValueError):
            return (1, str(r["id"]))

    items = sorted(records.values(), key=sort_key)
    path = base / "Hitlist" / "programs.jsonl"
    text = "\n".join(json.dumps(r, ensure_ascii=False) for r in items)
    path.write_text(text + ("\n" if text else ""), encoding="utf-8")


def write_clients(base: Path, records: dict[str, dict]) -> None:
    import time
    path = base / "clients" / "clients.json"
    payload = {"clients": list(records.values()),
               "updatedAt": int(time.time() * 1000)}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge two diverged copies")
    parser.add_argument("--live", type=Path, required=True,
                        help="the proposal_backups folder in daily use")
    parser.add_argument("--other", type=Path, required=True,
                        help="the proposal_backups folder from the other copy")
    parser.add_argument("--out", type=Path, required=True,
                        help="where to write the merged result")
    parser.add_argument("--report", type=Path, help="where to write the report")
    args = parser.parse_args()

    log(f"live copy : {args.live}")
    log(f"other copy: {args.other}")

    proposals = merge("proposal", read_proposals(args.live),
                      read_proposals(args.other), "title")
    grants = merge("grant", read_grants(args.live),
                   read_grants(args.other), "name")
    clients = merge("client", read_clients(args.live),
                    read_clients(args.other), "name")

    # Write to a fresh folder — the originals are never touched.
    if args.out.exists():
        shutil.rmtree(args.out)
    for sub in ("proposals", "Hitlist", "clients"):
        (args.out / sub).mkdir(parents=True, exist_ok=True)
    write_proposals(args.out, proposals)
    write_grants(args.out, grants)
    write_clients(args.out, clients)

    log(f"\n=== RESULT ===")
    log(f"  proposals {len(proposals)}")
    log(f"  grants    {len(grants)}")
    log(f"  clients   {len(clients)}")
    log(f"  written to {args.out}")

    if conflicts:
        log(f"\n=== {len(conflicts)} FIELD CONFLICT(S) — both copies had a different value ===")
        for line in conflicts:
            log(f"  {line}")
    else:
        log("\n  No field conflicts.")

    if args.report:
        args.report.write_text("\n".join(report), encoding="utf-8")
        print(f"\nreport written to {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
