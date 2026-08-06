#!/usr/bin/env python3
"""O14/D022 migration: add the resolved player_id column to the prospective
capture artifacts, backfilling historical rows against the cross-season
identity index + alias table (entity_resolution.py).

Targets (defaults, overridable):
    data/injury_capture/injury_log.csv    (name column: player)
    data/props_capture/master_props.csv   (name column: player_name)

SHIPPED, NOT RUN: per D022 this script is committed as part of the adoption
but is NOT executed against live capture data by the adoption itself. Running
it against the live artifacts is a deliberate operator action.

Safety properties:
  * DRY RUN by default -- reports what would change; writes nothing without
    an explicit --apply.
  * IDEMPOTENT -- adds the player_id column if absent, fills only EMPTY
    player_id cells, never overwrites a non-empty one; a second run is a
    byte-identical no-op and does not rewrite the file.
  * ATOMIC -- writes a temp file in the target's own directory, fsyncs, then
    os.replace()s over the original; a crash never leaves a half-written log.
  * RAW-PRESERVING -- the raw capture name column and every other field are
    copied through unchanged; row count and order are asserted before the
    replace. Unresolved names stay blank (cold start or unlisted alias);
    there is NO fuzzy fallback.

Usage:
    python migrate_o14_capture_player_id.py            # dry run, both targets
    python migrate_o14_capture_player_id.py --apply
    python migrate_o14_capture_player_id.py --apply --injury-log PATH
    python migrate_o14_capture_player_id.py --apply --props PATH
    (--master / --alias / --season override the index inputs, e.g. for
     fixtures under ops_adoption_tests/O14/.)
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from entity_resolution import load_capture_index, resolve_player_id  # noqa: E402

DEFAULT_INJURY = ROOT / "data" / "injury_capture" / "injury_log.csv"
DEFAULT_PROPS = ROOT / "data" / "props_capture" / "master_props.csv"


def migrate_csv(path, name_col, name_to_id, apply=False):
    """Migrate one capture CSV. Returns a summary dict; writes only when
    apply=True AND something actually changed."""
    path = Path(path)
    if not path.exists():
        return {"path": str(path), "status": "MISSING", "changed": False}
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if not rows:
        return {"path": str(path), "status": "EMPTY", "changed": False}
    header = rows[0]
    if name_col not in header:
        raise ValueError(f"{path}: expected column {name_col!r} in header "
                         f"{header} — wrong file or wrong --*-log path")
    name_i = header.index(name_col)
    had_pid = "player_id" in header
    new_header = header if had_pid else header + ["player_id"]
    pid_i = new_header.index("player_id")

    out_rows = [new_header]
    filled, unresolved_names, changed = 0, set(), not had_pid
    for r in rows[1:]:
        r = list(r)
        while len(r) < len(new_header):            # pad v1 rows to v2 width
            r.append("")
        if r[pid_i] == "":                          # fill EMPTY cells only
            pid = resolve_player_id(r[name_i], name_to_id)
            if pid is not None:
                r[pid_i] = str(pid)
                filled += 1
                changed = True
            elif r[name_i]:
                unresolved_names.add(r[name_i])
        out_rows.append(r)

    # raw-preservation + row-count assertions before any write
    assert len(out_rows) == len(rows), "row count changed — refusing"
    for orig, new in zip(rows[1:], out_rows[1:]):
        assert new[name_i] == orig[name_i], "raw name mutated — refusing"

    summary = {"path": str(path), "status": "OK", "rows": len(rows) - 1,
               "added_column": not had_pid, "filled": filled,
               "unresolved": sorted(unresolved_names), "changed": changed,
               "applied": False}
    if apply and changed:
        fd, tmp = tempfile.mkstemp(dir=str(path.parent),
                                   prefix=path.name + ".", suffix=".migrating")
        try:
            with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerows(out_rows)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)                   # atomic on one volume
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
        summary["applied"] = True
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--apply", action="store_true",
                    help="actually rewrite the artifacts (default: dry run)")
    ap.add_argument("--injury-log", type=Path, default=DEFAULT_INJURY)
    ap.add_argument("--props", type=Path, default=DEFAULT_PROPS)
    ap.add_argument("--master", type=Path, default=None,
                    help="master_player.parquet override (fixtures/testing)")
    ap.add_argument("--alias", type=Path, default=None,
                    help="alias_table.json override (fixtures/testing)")
    ap.add_argument("--season", type=int, default=None)
    args = ap.parse_args()

    name_to_id = load_capture_index(args.master, args.alias, args.season)
    print(f"identity index: {len(name_to_id)} normalized names"
          + ("" if args.apply else "  [DRY RUN — pass --apply to write]"))
    rc = 0
    for path, name_col in ((args.injury_log, "player"),
                           (args.props, "player_name")):
        s = migrate_csv(path, name_col, name_to_id, apply=args.apply)
        print(f"{s['path']}: {s['status']}"
              + (f" | rows={s.get('rows')} add_column={s.get('added_column')}"
                 f" filled={s.get('filled')}"
                 f" unresolved={len(s.get('unresolved', []))}"
                 f" changed={s['changed']} applied={s['applied']}"
                 if s["status"] == "OK" else ""))
        if s["status"] == "OK" and s.get("unresolved"):
            print(f"  unresolved (blank player_id, NO fuzzy fallback): "
                  f"{s['unresolved']}")
        if s["status"] == "MISSING":
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
