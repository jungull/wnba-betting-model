# `experiments/player_program/`

The player-level modelling program's artifact directory. Owned by branch `player-model-program`.

**Nothing in here is scored.** No accuracy, calibration, Brier, MAE, RMSE, pinball,
interval-coverage, threshold, edge, return or profitability figure is computed by anything in this
directory. "Coverage" means **obligation completeness**.

## Contents

| path | what |
|---|---|
| `audit_phase0_v14_player_oof.py` | the Phase 0 audit of `cbs_v14_player_oof/1` at `d69aa02`, as executable code |
| `PHASE0_AUDIT_RECEIPT.json` | its output — regenerate, don't hand-edit |
| `preserved_uncommitted_d69aa02/` | **team-thread material, preserved not adopted** — see below |

## Regenerating the audit

```bash
python experiments/player_program/audit_phase0_v14_player_oof.py --season 2022
```

~1 minute. Builds the real 2022 player frame from `prediction_contract_v4`, runs the real fold
**in memory**, and writes only the receipt. It deliberately persists nothing into any arm's output
namespace: `run_player_oof_v14.py` is the only sanctioned producer of `cbs_v14_player_oof/1`
artifacts, and an audit must not manufacture something that looks like its output.

`--season 2022` is the default and the right choice: 2021 is the cold-start fold whose training
window is empty, so it exercises the degenerate branch rather than the fitted one.

## `preserved_uncommitted_d69aa02/`

Uncommitted working-tree changes found in `.claude/worktrees/cbs-v2-gate-accounting` (HEAD
`d69aa02`), copied here with unified patches and a hash manifest because they are **unreviewed,
uncommitted, and repair a defect this program independently proved** (P-D1: the producer gate
reports a clean tree without measuring one).

Three files, +220 lines: `run_player_oof_v14.py`, `run_team_oof_v12_2.py`,
`tests/test_run_player_oof_v14.py`.

**The player program has not modified them and will not commit them to any team branch.** They are
team-thread material; disposition is the team thread's decision. The source worktree is untouched.

See `PRESERVATION_MANIFEST.json` for before/after hashes and the full rationale.
