# Pre/post operational-manifest evidence — what exists, and what does not

The supervisor's requirement for run **B5** was: *retain distinct pre-run and post-run
manifests plus a comparison receipt; one retained manifest and prose cannot independently
prove the pair was identical.*

This document records the outcome honestly. **The requirement is only partly satisfiable
retrospectively, and the part that is not satisfiable has not been manufactured.**

---

## 1. The finding

`GATE_LOG_2026-08-01.md` claims, for each of B1–B5, that the manifest was regenerated
immediately before and after the run with an identical aggregate. Auditing the artifacts:

| run | window (UTC) | manifests on disk for that run | pre-run capture retained? |
|---|---|---|---|
| B1 | 18:22:49 → 18:23:22 | `…T1823Z.json` (18:23:26) | **no** |
| B2 | 19:15:09 → 19:15:33 | `…T1915Z.json` (19:15:36) | **no** |
| B3 | 19:54:08 → 19:54:46 | `…T1954Z.json` (19:54:51) | **no** |
| B4 | 20:31:38 → 20:32:14 | `…T2032Z.json` (20:32:17) | **no** |
| B5 | 21:30:18 → 21:31:03 | `…T2131Z.json` (21:31:08) | **no** |

Every retained manifest's `generated_utc` falls **3–6 seconds after its run ended**. All five
are **post-run** captures. **Zero pre-run captures survive**, for any run. There is no
manifest with a `generated_utc` between 20:32:17Z and 21:31:08Z, so B5's asserted pre-run
capture has no file behind it.

`operational_input_manifest.py` also had **no comparison mode** at the time — no flag, no
function, and no code path that read an existing manifest. Even had two files existed, nothing
would have compared them or emitted evidence of the comparison. The only cross-run signal the
tool produced was an ephemeral stderr line.

**The supervisor's diagnosis was correct: for B1–B5 the identical-pair claim rests on prose
plus one post-run file.**

## 2. What was fixed

`operational_input_manifest.py --compare PRE POST --receipt OUT` now exists
(`compare_manifests`, schema `operational_input_comparison/1`). It loads two manifests,
compares them entry by entry, and writes a receipt a later reader can re-derive from the two
files without trusting any summary. It reports the two halves separately, because collapsing
them would hide a real distinction:

* `aggregate_identical` — the content aggregate over `(path, bytes, sha256)`;
* `producer_identity_identical` — the producer-tree identity (or `root_commit` on the older
  manifest generations);
* explicit `entries_added` / `entries_removed` / `entries_changed` lists.

Exit code is 0 only when both hold and no entry moved.

## 3. What the tool proves about the manifests that DO exist

**It cannot invent B5's missing pre-run capture, and it was not asked to.** What it can do is
compare retained artifacts. Two comparisons were run against real files:

### 3.1 B3 — a genuine artifact-backed bracketing pair

`…T1915Z.json` (19:15:36Z) precedes B3's window (19:54:08 → 19:54:46), and `…T1954Z.json`
(19:54:51Z) follows it. These two retained files genuinely bracket B3.

Receipt: **`project_docs/OPERATIONAL_INPUTS_COMPARISON_B3_2026-08-01T1954Z.json`**

> **INPUTS IDENTICAL, PRODUCER MOVED.** Aggregate `7965c304…4014` on both sides;
> **0 entries added, 0 removed, 0 changed**. But the producer identity differs —
> `root_commit` `b3f024c` before, `3096c5d` after — because a commit landed between the
> two captures.

So the *input* half of the ledger's claim for B3 is now **independently substantiated by
artifact**, and the *producer* half is **refuted**: the pair does not bracket one unchanged
tree. This is the first pre/post comparison in the project backed by two files rather than a
sentence.

### 3.2 B4 → B5 — drift between runs, NOT a pre/post pair

`…T2032Z.json` is B4's post-run capture, 58 minutes before B5 began. It is **not** a B5
pre-run manifest and is not labelled as one here.

Receipt: **`project_docs/OPERATIONAL_INPUTS_DRIFT_B4_TO_B5_2026-08-01T2131Z.json`**

> **INPUTS MOVED: 2 added, 0 removed, 2 changed**, and the producer identity differs.
> Added: `data/injury_capture/raw/wnba_official_20260801T210003Z.pdf`,
> `data/odds_capture/live_20260801T210003Z.json`. Changed:
> `data/injury_capture/injury_log.csv`, `data/odds_capture/capture_log.csv`.

That is the 21:00:03Z live capture firing between the two runs — expected behaviour, and
precisely why a post-run manifest from an earlier run cannot stand in for a pre-run manifest
of a later one.

## 4. Standing correction to the evidence label

For **B1, B2, B4 and B5** the sentence *"the manifest was regenerated immediately before and
after the run with an identical aggregate"* is **not substantiated by any retained artifact**
and must be read as an unverified operator note. For **B3** the input half is now proven and
the producer half is disproven.

No retrospective pre-run manifest has been, or will be, generated and back-labelled. Writing a
manifest today and presenting it as a capture from 21:30Z on 2026-08-01 would be a fabricated
timestamp — the precise failure mode the charter's review focus names.

## 5. Required procedure for every future layer-B run

1. `python operational_input_manifest.py --out project_docs/OPERATIONAL_INPUTS_<UTC>_PRE.json`
2. run `python verify_all.py` (layer B)
3. `python operational_input_manifest.py --out project_docs/OPERATIONAL_INPUTS_<UTC>_POST.json`
4. `python operational_input_manifest.py --compare <PRE> <POST> --receipt
   project_docs/OPERATIONAL_INPUTS_COMPARISON_<UTC>.json`
5. Bind the run in the gate log to **all three** filenames. A layer-B result claimed as bound
   to a stable input set without a comparison receipt is an unverified claim.

All manifests are retained; none is ever replaced or deleted.
