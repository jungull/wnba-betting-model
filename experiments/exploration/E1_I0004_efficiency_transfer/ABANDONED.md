# ABANDONED — DO NOT CITE ANY NUMBER IN THIS DIRECTORY

**Status: DEAD AGENT. Partial work. UNCLAIMED and UNUSABLE as a result.**
Marked by Coordinator #06, 2026-08-08. See `DECISION_LEDGER.jsonl` D083.

## What happened

The agent screening `E1_I0004_efficiency_transfer` was terminated early by an
**API error — "Connection closed mid-response"**. Under GRAPH_POLICY §12 this is an
**infrastructure event, not a finding**: its partial work is unusable and unclaimed,
and the task is to be retried at the same-or-higher model tier.

## Why `FINDINGS.json` in this directory is a TRAP

`FINDINGS.json` (34 KB), `efficiency_contrast.csv`, `points_contrast.csv`,
`arithmetic_ceiling.csv` and `permutation_draws_paired_cluster.csv` all exist and
**look complete. They are not.**

The agent's final transmission before it died was:

> "The uncentred allowance is a level shift, not a cross-sectional signal —
> I need to fix that before computing any contrast."

**It was telling the coordinator that the construction underlying every contrast in
this directory is wrong, and that it had not yet fixed it.** The artifacts on disk
therefore embody the *pre-fix* construction. A reader who opens `FINDINGS.json`
without reading this file would take a defective contrast for a screened result.

This is the exact hazard GRAPH_POLICY §12 anticipates when it calls dead-agent output
"unusable and unclaimed" — the danger is not that partial work is obviously broken,
it is that it can look finished.

## What the defect means (recorded because it is a real methodological point)

An opponent conversion-allowance term used **uncentred** shifts every prediction by
roughly the same amount rather than discriminating between opponents. It is then a
**level shift, not a cross-sectional signal**, and a contrast built on it measures
almost nothing about matchup. It must be centred — expressed relative to the
point-in-time league mean — before any contrast is computed.

This is the same distinction recorded in **D080**: a season-level scalar anchor shared
by all teams is harmless for a *cross-sectional* claim and not harmless for a *level*
claim. Two independent agents reached it from opposite directions, which is why it is
being carried forward into the retry rather than rediscovered a third time.

## What may and may not be reused

* **MAY be read as scaffolding**: `et_base.py`, `s00`–`s04` scripts, and
  `efficiency_frame.parquet` — as *code and inputs to re-derive from*, saving setup time.
* **MUST NOT be reused**: any number, any contrast, any p-value, any verdict, and
  `FINDINGS.json` in its entirety.

The retry runs in **`E1_I0004_efficiency_transfer_v2/`** and must rebuild every
contrast with the centring corrected.
