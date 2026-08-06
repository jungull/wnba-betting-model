# Bundle A (O11) adoption notes

**Status: APPLIED.**

## What changed since the prior (BLOCKED) attempt

The earlier attempt in this worktree was BLOCKED because
`prospective_pair/should_run_base.py` did not exist under version control anywhere
in the adoption worktree. The coordinator has since committed the live module as a
pre-patch baseline and merged it into this worktree. The file now exists at
`prospective_pair/should_run_base.py` and the patch could be applied.

## Patch applied

`PROPOSED_PATCH.diff`
(`experiments/player_program/ops_lane/O11_OBLIGATION_DISCOVERY_LEAD_WINDOW/PROPOSED_PATCH.diff`,
read-only spec directory) was applied to
`prospective_pair/should_run_base.py` in this worktree, exactly as written. The
patch's context (the `assess()` loop body, the `in_window`/`fire` computation, and
the three `reason` branches) matched the live file byte-for-byte, so the hunk applied
cleanly with no hand-merging and no whitespace adjustment.

**No hunk was BLOCKED.**

### Behavioural change

* A slate row with no official `game_id` is no longer dropped before the window
  test. It is now served under the same provisional id
  (`PROV-<slate_date>-<away>@<home>`) that `daily_forecast.py:562` already mints
  for it, via `provisional`/`gid` fallback logic added to the `assess()` loop.
* Every decline now names the number of upcoming games examined and lists every
  game served under a provisional id, so a decline can never again be silent about
  a dropped row.
* `current_label`, `CONTRACT_LABELS`, `LEAD`, and the `fire = bool(in_window) and
  not dup` conjunction are untouched, per the patch's stated scope (the `and not
  dup` masking defect is D-c / node O12, explicitly out of scope here).

### sha256 (`prospective_pair/should_run_base.py`)

| | sha256 |
|---|---|
| pre-patch (committed baseline) | `0D41A3B492221BD8A7A1A20CDB3B3A03DBC61834E9DC3539DEF6559DFE8A048D` |
| post-patch (this change) | `1A34E871DD69D02A00608EC02495C153DF9E7A94C0FF889582F334E08D576497` |

(Both computed with `Get-FileHash -Algorithm SHA256` on the file in this worktree.)

## Test suite

`ops_adoption_tests/O11/TESTS.py` (own files, under this bundle's ownership) now
exercises two layers:

1. **Sections 1-8** -- the original 45-check-minus-live-capture design
   verification, unchanged, against the pure-function reproduction in
   `ops_adoption_tests/O11/gate_logic.py` (`classify_original` /
   `classify_fixed`, copied verbatim from the research worktree). These confirm
   the *shape* of the fix independent of any live wiring.
2. **Section 9** (new, replacing the old live-capture re-measurement) -- drives
   the REAL `prospective_pair/should_run_base.py::assess()` directly, imported
   from the actual file (`import should_run_base as srb` with
   `prospective_pair/` added to `sys.path`), with only its two I/O boundary
   functions (`build_slate`, `read_official`) monkeypatched to the same fixture
   data used in sections 1-8. Everything downstream -- `current_label`, the
   window/dup logic, the reason string, and the provisional-id fallback added by
   the patch -- runs as the live, patched module actually wrote it. Section 9
   covers: the defect no longer reproduces (9a), the provisional obligation
   fires inside its lead window (9b), a true decline now carries a true, visible
   reason (9c), the decline-reason masking case for a mixed served/unserved
   slate (9d), no regression when every game already has an official id (9e),
   and that `LEAD`/`CONTRACT_LABELS`/`current_label` are untouched in the real
   module (9f).

The old section 9 (re-running `measure_discovery_lag.py` against
`C:/Users/jgallagher/wnba-betting-model`, the live main worktree) remains
removed: that worktree is explicitly off-limits ("NEVER touch") for this node,
and `measure_discovery_lag.py` is not in this bundle's ownership set to port.

### Result

```
python ops_adoption_tests/O11/TESTS.py
```

**69/69 checks pass, 0 failures** (45 original pure-repro checks minus the 3 that
lived in the removed live-capture section 8→9 = 42 pure-repro checks, plus 27 new
real-module checks in section 9 = 69 total).

## Confirmation: the decline-reason masking defect is fixed in the real module

The defect (D-b, `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:200`) was:
a slate row with no official `game_id` was dropped from `upcoming`/`new`/`in_window`
before any window test, so the gate fell through to `elif not in_window:` and
reported "no unserved obligation inside its 20-minute lead window" -- blaming the
lead window for a decline the lead window did not cause, with nothing printed for
the dropped game.

Section 9c of the applied test suite exercises this directly against
`prospective_pair/should_run_base.py::assess()` itself (not the isolated
reproduction): at 01:30, 29.9 minutes before the T-24h cutoff -- genuinely outside
the 20-minute lead window -- the real module now:

* still correctly declines (`fire is False`), because 29.9 min really is outside
  the window;
* but the game is visible in `upcoming` (`len(r["upcoming"]) == 1`), not silently
  dropped;
* and the reason string names both the game count examined
  (`"1 upcoming game(s) examined"`) and the unresolved provisional id
  (`"provisional id" in r["reason"]`), so the decline reason is now true and
  non-silent rather than blaming the lead window for an identity problem.

Section 9d additionally confirms the `and not dup` conjunction was left untouched
as scoped: with GSV v TOR already served under its provisional id and a second,
unrelated game (ATL v PHX) genuinely outside the window, the overall decline is
correctly attributed to the duplicate (`would_duplicate` has 1 entry, `fire is
False`), and the unrelated game remains visible in `upcoming` rather than being
erased -- the masking behaviour this bundle's patch does NOT touch (`and not dup`
precedence is defect D-c / node O12) is exercised here to confirm it is unchanged,
not silently made worse by this patch. The duplicate-vs-lead-window reason
*precedence* itself is out of scope for this bundle, per the patch's own stated
scope and `gate_logic.py`'s documentation.

## Ownership discipline

Only `prospective_pair/should_run_base.py` (patched, in scope) and
`ops_adoption_tests/O11/*` (this directory) were touched. No other file in the
adoption worktree was modified. No git commands were run.
