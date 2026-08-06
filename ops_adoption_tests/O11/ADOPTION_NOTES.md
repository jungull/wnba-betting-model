# Bundle A (O11) adoption notes

**Status: BLOCKED at the patch-application step.**

## What was attempted

`PROPOSED_PATCH.diff` (research worktree,
`experiments/player_program/ops_lane/O11_OBLIGATION_DISCOVERY_LEAD_WINDOW/PROPOSED_PATCH.diff`)
targets `prospective_pair/should_run_base.py`. My ownership for this bundle is exactly that file
plus new files under `ops_adoption_tests/O11/`.

## The conflict

`prospective_pair/should_run_base.py` **does not exist anywhere in the adoption worktree**
(`C:/Users/jgallagher/wnba-betting-model/.claude/worktrees/o16-adoption`, branch
`graph/O16_ADOPTION`, base `735b63b` of `data-refresh-2026`). Verified by direct filesystem search,
not by trusting a listing:

- `Get-ChildItem -Filter "prospective_pair"` under the worktree root: no match.
- `Get-ChildItem -Filter "should_run*" -Recurse`: no match.
- A content grep across every `*.py` file in the worktree for any of `CONTRACT_LABELS`,
  `would_duplicate`, or `"minute lead window"` (all distinctive strings from the target module):
  no match anywhere.
- `daily_forecast.py` exists at the worktree root (so this is the right worktree/repo), and it
  does not reference `should_run_base` or `prospective_pair`.

There is no `prospective_pair/` directory at all in this worktree. The patch has no file to apply
to — not a whitespace/context mismatch, an outright absence of the target module. Per the BLOCKED
DISCIPLINE rule, I did not improvise a location to hand-apply the change into (e.g. guessing it
merged into `daily_forecast.py` or a `scripts/` equivalent); I searched but did not find a
plausible successor module, and inventing one would be redesign, not adoption.

**Nothing was written to `prospective_pair/should_run_base.py`; no such file was created.**

## What was done instead (unambiguous, within ownership)

The `TESTS.py` (45 checks) and `gate_logic.py` (the isolated `classify_original` /
`classify_fixed` pure-function reproduction) from the research worktree were ported verbatim into
`ops_adoption_tests/O11/` so the candidate fix logic itself is still verified in isolation:

- `ops_adoption_tests/O11/gate_logic.py` — unmodified copy.
- `ops_adoption_tests/O11/TESTS.py` — ported with two adjustments:
  1. import path changed to pull `gate_logic` from this directory instead of the research
     worktree.
  2. **Section 9 removed.** The original section 9 re-runs `measure_discovery_lag.py` against
     `C:/Users/jgallagher/wnba-betting-model` (the live main worktree) if `data/odds_capture`
     exists there. That path is explicitly off-limits ("NEVER touch") for this node, and
     `measure_discovery_lag.py` is not in this bundle's ownership set to port alongside it.
     Sections 1-8 do not depend on section 9.

Result: **42/42 ported checks pass** (45 in the original minus the 3 checks that lived inside the
removed section 9). Full output captured by the coordinator's test run of
`python ops_adoption_tests/O11/TESTS.py`.

This confirms the fix logic is sound and the decline-reason masking defect (duplicate branch
precedence over the lead-window reason, PROJECT_UPDATE's "per-game scope does not fix this") is
addressed by `classify_fixed` exactly as the research node claimed — but it is verification of the
*design*, not adoption into the live scheduler, because the live scheduler file this bundle owns
does not exist here to receive the edit.

## What the coordinator needs to do

Either:
1. Confirm whether `prospective_pair/should_run_base.py` was moved/renamed/removed in a later
   commit than `735b63b` on `data-refresh-2026` (this worktree's base), and re-point this bundle at
   the correct current path/base if so; or
2. Confirm the module genuinely does not exist yet at this base (i.e. the scheduler this defect
   describes has not been built here yet), in which case D022/O11 adoption is premature for this
   worktree and should be deferred until the module exists.

No git commands were run to investigate this (out of scope per the hard rules); the above is a
filesystem-only finding.
