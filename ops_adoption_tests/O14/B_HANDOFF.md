# B_HANDOFF — O14 entity-resolution contract: edits required inside C-owned files

Bundle B (O14, decision D022) shipped everything it owns:
`entity_resolution.py` (production module, fix components F1–F4),
capture-time resolution in `injury_capture_daily.py` and
`props_capture_daily.py` (writer-forward, LIVE-DATA RULE respected),
`data/entity_resolution/alias_table.json` (schema `ops_lane/O14/alias_table/1`),
`migrate_o14_capture_player_id.py` (shipped, NOT run), and
`ops_adoption_tests/O14/` (55 checks, all passing).

Two of the four approved proposals terminate inside `daily_forecast.py`,
which is agent C's file. B did NOT touch it. The exact edits follow.
All line numbers refer to `daily_forecast.py` at base 735b63b.

---

## Edit 1 — gap taxonomy: admit BLOCK severity (approved proposal 3 / fix F4)

**File:** `daily_forecast.py`
**Location:** line 150, inside `Gaps.add`

**Old text:**
```python
        assert severity in ("FATAL", "WARN", "INFO")
```

**New text:**
```python
        assert severity in ("FATAL", "BLOCK", "WARN", "INFO")
```

**Reason:** the approved proposal promotes an unbindable Out/Doubtful
designation from WARN to a BLOCK-severity gap so the availability estimate
fails closed rather than degrading silently (O14-F3; realized instance:
Aneesah Morrow 2026-08-02, 22.73 min mis-attributed). The resolved player
layer (`entity_resolution.player_layer_resolved`) emits
`gaps.add("BLOCK", "entity-resolution", ...)` for exactly that case, and the
current assert would crash the run instead of recording it.

**Semantics C must decide and document:**
- `Gaps.fatal()` (line 157-158) should remain FATAL-only while the player
  layer is informational in v0 — BLOCK marks the AVAILABILITY estimate as
  untrustworthy for the affected team; it does not abort the team forecast.
- If any forecast-log record schema or validator enumerates gap severities
  (forecast-log writers are C-owned), it must accept `"BLOCK"`.

---

## Edit 2 — wire `player_layer` to the resolved implementation
## (approved proposals 1-context, 2; fix F1–F3)

**File:** `daily_forecast.py`
**Location:** the whole body of `player_layer`, lines 640–760
(`def player_layer(...)` through `return out, inj_prov`). Keep
`load_injuries_at_cutoff` (lines 612–637) and `_norm_name` (606–609)
unchanged — no edit is needed there (see "Reader tolerance" below).

**Old text:** the entire existing function at lines 640–760, beginning
```python
def player_layer(slate: list[dict], season: int, slate_date, cutoff: datetime,
                 gaps: Gaps) -> tuple[dict, dict]:
    """Recency dressed roster + minutes EWMA(0.30) + the Phase-3 rule gate:
    latest captured designation 'Out' at the cutoff => excluded. Informational
    only in v0: never modifies the team forecast."""
    inj, inj_prov = load_injuries_at_cutoff(cutoff, gaps)
    have_inj = len(inj) > 0
    p = pd.read_parquet(MASTER_PLAYER)
```
and ending
```python
        out[team_ab]["designations_counts"] = dc
    return out, inj_prov
```

**New text:**
```python
def player_layer(slate: list[dict], season: int, slate_date, cutoff: datetime,
                 gaps: Gaps) -> tuple[dict, dict]:
    """Identity-resolved roster + minutes EWMA(0.30) + the Phase-3 rule gate
    (O14/D022): minutes history is keyed on player_id across the season (F1);
    rosters are single-tenant per identity as of the cutoff, each entry
    recording assignment_source last_game vs designation_transfer (F2);
    designations bind by identity via the cross-season index + alias table,
    never by (franchise-name, spelling) pair (F3); an unbindable Out/Doubtful
    raises BLOCK and materialises an explicit unresolved cold-start object —
    the availability estimate fails closed (F4). Informational only in v0:
    never modifies the team forecast."""
    from entity_resolution import player_layer_resolved
    inj, inj_prov = load_injuries_at_cutoff(cutoff, gaps)
    p_all = pd.read_parquet(MASTER_PLAYER)
    p = p_all[(p_all.season == season)
              & (pd.to_datetime(p_all.game_date).dt.date < slate_date)].copy()
    p["game_date"] = pd.to_datetime(p.game_date)
    abbr_to_name = {v: k for k, v in TEAMS.items()}
    teams = sorted({g["home"] for g in slate} | {g["away"] for g in slate})
    out = player_layer_resolved(teams, p, inj, abbr_to_name, gaps,
                                p_all=p_all, season=season)
    return out, inj_prov
```

(If module-level imports are preferred, move
`from entity_resolution import player_layer_resolved` next to the
`evalharness.forecast_log` import at lines 88–95; `sys.path` already contains
REPO at that point.)

**Reason:** proposals 1 and 2 — identity-keyed history, single-tenant roster
construction with recorded assignment source — are implemented in the B-owned
module `entity_resolution.player_layer_resolved`, ported from the approved
design `experiments/player_program/ops_lane/O14_OPS_ENTITY_RESOLUTION/
fix_entity_resolution.py`. Only the call site lives in C's file.

**Note on the cross-season frame:** `p_all` is passed unfiltered because the
identity index reads only (player_id, player_name, season) — names and ids,
no stats — so it cannot leak future performance into the as-of path. If
asof_invariant discipline is wanted anyway, filtering `p_all` to
`game_date < slate_date` changes nothing about identity binding for past
seasons.

**Output-shape deltas C should verify against downstream consumers**
(lines 839–852, 1133–1137, 1234–1235 all keep working; keys preserved:
`available`, `out`, `n_roster`, `n_out`, `n_cold_start`,
`sum_min_ewma_available`, `vacated_min_ewma`, `designations_counts`,
`report_only`, `unmatched_injury_rows`, `roster_last_game`,
`unknown_roster`, `availability_data`):
- roster entries gain `player_id`, `history_spans_teams`,
  `transferred_in_season`, `assignment_source`
  (`"last_game"` | `"designation_transfer"`); unresolved designation rows
  appear as explicit entries with `cold_start_unresolved: True`.
- team dicts gain `designation_transfers_in`.
- `n_roster` now counts identities (was distinct name strings).
- `report_only` now contains only IDENTITY-BOUND designations outside the
  recency roster (long-term absentee INFO / possible-return WARN preserved);
  rows that bind to no identity are no longer buried there — they surface as
  BLOCK/WARN gaps plus explicit cold-start objects, and remain listed in
  `unmatched_injury_rows`.

---

## Reader tolerance for the v2 capture schema (no edit strictly required)

`load_injuries_at_cutoff` uses `pd.read_csv`, which carries the new
`player_id` column through automatically once
`migrate_o14_capture_player_id.py` has been run (or a fresh v2 log exists);
the dedupe at lines 634–635 stays on the raw `(team, player)` strings, which
is correct — forecast-time binding re-resolves from the raw string against
the index, so the capture-time column is provenance/settlement support, not
a forecast-path dependency. Same for `master_props.csv` readers. Optional
follow-up (C's discretion, post-migration): prefer `player_id` in the dedupe
key when present.
