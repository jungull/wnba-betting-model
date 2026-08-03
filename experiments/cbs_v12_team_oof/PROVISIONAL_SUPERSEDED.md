# `cbs_v12_team_oof/1` — PROVISIONAL, superseded, retained intact

**Status:** provisional. Superseded by `cbs_v12_team_oof/2`
(`experiments/cbs_v12_team_oof_v2/`). **Nothing in this directory has been deleted, moved or
overwritten**, and every artifact remains attested.

## What survived review

The Codex supervisor independently verified all six prediction files at commit `6f6329f`:
2,990 unique rows exactly equal to the contract-v4 team universe (418 / 478 / 520 / 524 / 620 /
430); no outcome columns; every artifact manifest matching its bytes; sidecar digests and row
identities recomputing; `feature_asof < forecast_cutoff`; monotone quantiles; 2021
declared-constant and 2022-2026 containing fitted components; and **no score or profitability
figure of any kind**.

## Why it is nonetheless provisional

Two defects in how it was **produced**, not in what it produced
(supervisor reply `20260803T002715462Z`):

1. **The producing tree was dirty.** `/1` ran at parent commit `0225f6a` with **97 dirty paths**.
   Its receipt recorded that honestly and generated anyway, and it bound neither the dirty diff
   nor the producing source bytes — so **the exact code that generated this output is not
   reconstructible**. The post-push gate `A22` certifies the commit these artifacts were
   *committed in*, which is a different claim from certifying the execution that made them.
2. **The resume path was fail-open.** `_digests_still_match` compared rebuilt frame digests and
   the five input artifacts, and nothing else — not that the outputs existed, not that their
   manifests or hashes matched, not that the receipt's identity, config, season or snapshot
   fields matched, not that the sidecar digest recomputed. A missing or substituted output could
   be marked `RESUMED` and still yield `all_folds_receipted=true`.

A third item is a labelling correction rather than a defect: `/1`'s AST scan covers its own
wrapper only and cannot establish that imported callees never read historical outcomes — and the
run *legitimately* consumes historically available prior outcomes, because that is what a
walk-forward feature is. The defensible claim, which `/2` states, is narrower: no target row's
own outcome informed its forecast; no forecast was scored against its outcome; no evaluation
metric was calculated.

## What `/2` does differently

Refuses a dirty producer tree outright; digests every producing source file before any frame is
built; validates every artifact byte and identity on resume and re-runs the strict prediction and
provenance validators on the artifacts as read back, failing closed on twelve enumerated
conditions; and never writes into an existing attempt directory.

See `project_docs/CONTRACT_BASELINE_SUITE_V14.md` §5 and the v13 erratum in
`experiments/registry.jsonl`.
