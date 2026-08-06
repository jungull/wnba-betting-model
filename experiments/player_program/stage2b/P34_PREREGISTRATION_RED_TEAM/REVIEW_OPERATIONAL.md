# P34 red-team review — dimension: OPERATIONAL RELEVANCE

ADVERSARIAL REVIEW. Reviewers are independent of the preregistration author. A clean review does not make an arm true; it makes it fittable.

**Reviewer:** independent operational-relevance reviewer (one of seven). Did not author P33.
**Verdict: ACCEPT_WITH_REQUIRED_CHANGES.** One Severity A (OP-1, A19 — closable by the arm's own
preregistered withdrawal clause), four Severity B, six Severity C.

**Stop conditions: NONE TRIPPED.** Assessed against all six named triggers. Nothing below changes
the primary target, the K0 structure, the five-fold/cluster inference structure, the 2,982/1,491
row universe, the cutoff-valid feature set, or the leakage status. The A19 finding removes an arm
via the arm's own preregistered withdrawal-as-design-failure clause; arm withdrawal is a family
denominator event, not a stop-condition event. Every other finding is arm-local specification
repair inside the P35 freeze window.

**Process disclosure, stated rather than glossed.** When this review session began, a file named
`REVIEW_OPERATIONAL.md` already existed at this path (25,245 bytes, mtime 2026-08-06 12:22:45,
sha256 `C5ECB6F15D65A3305A1EACE2A6E2F9E7F7B641A4651C677E8A610F5513CA6C63`), alongside the other six
reviewer files (mtimes 12:06–12:14). Per the blindness rule I read NONE of the seven, including the
pre-existing file bearing my own dimension's name; its hash is recorded above so the coordinator
can recover or diff the earlier bytes from any prior commit. This file replaces it. The
coordinator should decide which run's operational review is the review of record; if the earlier
run was validated and committed, both are recoverable.

---

## 0. Input verification (before any other read)

`Get-FileHash -Algorithm SHA256 <path>` on all four mandated inputs, matched case-insensitively:

| input | expected | match |
|---|---|---|
| `stage2b/P33_PREREGISTRATION_DRAFT/SPEC.json` | `066b2a04…7d093` | YES |
| `stage2b/P33_PREREGISTRATION_DRAFT/REPORT.md` | `6d945b86…48ab` | YES |
| `stage2b/P32_CANDIDATE_SYNTHESIS/SPEC.json` | `1dc25981…138c` | YES |
| `stage2b/P30_EVIDENCE_PACKET_V3/EVIDENCE_PACKET_V3.json` | `95d2412c…75` | YES |

Also verified live before use: `possessions_v2/possessions_raw_v2.parquet` sha256 =
`7200881fd811db9d0d6b10ea0a19b01ec7b6d027ee4567b9ef963241b15a4b1a`, identical to the value pinned
in the P29 report and `EVIDENCE_PACKET_V2.sources`.

## What I measured, and how

Two scripts (reproduced in the appendix) plus two one-liners, all feature/schedule/schema-only.
No target value entered any statistic; nothing was fitted; no performance number was computed;
nothing under `SEALED_RESULTS` was read (and per P33 the directory does not exist).

1. `p34_operational_measurements.py` — full `end_reason` level inventory of
   `possessions_raw_v2.parquet` (238,563 possessions), overall and per season, plus substring scans
   for live-ball/dead-ball markers.
2. `p34_operational_measurements2.py` — via `possession_features.load_universe()` and
   `chronological_folds()`: per-game count of strictly-earlier completed league games (A08 window
   coverage at K=20/80 per training fold); per-team strictly-earlier game counts (A16/A09/A10/A11
   empty- and partial-window rows).
3. Inline python — zero-prior and one-prior team-game rows by season and team_id.
4. `Glob **/*schedul*` over `experiments/player_program/` — no file matches (corroborates P33's
   directory-enumeration claim that no schedule artifact exists in scope).

---

## Findings, ranked

### OP-1 — SEVERITY A. A19's admissibility is already decided by the artifact's bytes: the live-ball dictionary cannot exist. The P35 deferral defers a fact that was measurable today.

Measured on the pinned `possessions_raw_v2.parquet` (hash above): `end_reason` carries exactly
NINE levels — `defensive_rebound` (84,647), `made_shot` (82,738), **`turnover` (41,505)**,
`made_ft_final` (22,821), `period_end` (6,054), `technical_ft` (588), `inferred_flip` (200),
`miss_flip_no_rebound` (8), `made_ft_nonfinal_flip` (2). There is **one generic turnover level and
no level containing any live-ball or dead-ball marker** (substring scans for
steal/live/out_of_bounds/offensive_foul/violation/travel/shot_clock/dead all return empty).

A19's mechanism is *"defensive LIVE-ball turnover forcing"* via `end_reason in E_LB (fixed
live-ball dictionary)`. With a single undifferentiated `turnover` level, every possible frozen
dictionary fails: E_LB = {turnover} silently relabels the mechanism to all-turnover forcing
(which is A20's construct, symmetrized), and E_LB = {} yields a zero-variance column the feature
gate blocks. A19's own preregistered clause — *"WITHDRAWN as design failure if the frozen
dictionary cannot distinguish live-ball turnover terminators (mechanism unmeasurable in this
artifact)"* — is therefore **triggered now, by bytes, before any fit**.

P33 carried this in `could_not_establish` as "a data-dictionary question deferred to the P35
dictionary freeze". It was establishable in-scope by one schema read of a frozen input. Deferring
a decidable admissibility fact past the red team meant seven reviewers almost reviewed 26 arms
when the artifact says 25.

**Closure (uses the arm's own clause — this is why the verdict is not REJECT):** at or before the
P35 task-card freeze, either (a) record A19 WITHDRAWN_DESIGN_FAILURE citing this measurement, and
restate LAGGED_TEMPO_MIX as the single-member family {A17} — the joint-scoring /
weaker-member-drop rule becomes void and must be voided EXPLICITLY, with the family's Holm
denominator restated, not left at 2; or (b) hash-pin a new upstream receipted source that
distinguishes steals/live-ball terminators (none exists in scope today; this is parallel data-lane
work on the A06 pattern). Silent option (c) — freezing E_LB = {turnover} — must be named and
barred: it changes the preregistered mechanism after the fact.

**A20 survives the identical check, and this should be recorded as a positive:** {`turnover`} is a
complete, well-defined turnover-terminator set (17.40% of all possessions, present every season).
A20's dictionary freeze at P35 is a formality; the arm is operable as specified.

### OP-2 — SEVERITY B. Fifteen zero-prior-evidence rows contradict four arms' "defined on every row" claims; three of those rows are TEST rows of the two most recent folds.

Measured: 15 universe rows have ZERO strictly-earlier completed games for the offense team — 12
in 2021 (each franchise's first post-opening-day game; D010 removed only the opening day), 1 in
2025 (1611661331's debut), 2 in 2026 (1611661327/1611661332's debuts). 75 rows have fewer than 5
priors. The 2025/2026 rows sit in the TEST sets of `train_lt_2025`/`train_lt_2026` — at
operational decision time these are exactly the expansion cold starts the pipeline will face.

Document-vs-bytes contradictions, per arm:

* **A16** fallback: *"resolved universe already excludes the no-prior-games stratum; defined on
  all 2,982 rows in every fold"* — FALSE. The mean over "last k=5 completed games" is a mean over
  an EMPTY set on 15 rows and a partial window (1–4 games) on 60 more. The universe excludes only
  the 2021 opening day.
* **A09** fallback: *"both features continuous on every resolved row"* — FALSE at n=0: d_t is
  undefined and w(0)·d_t is 0·NaN operationally, not 0.
* **A10** fallback: *"contrast defined everywhere, exactly zero only for one-prior-game teams"* —
  FALSE at n=0.
* **A11**: for an expansion debut, n_cur = 0 AND m_prev = 0, so dblend = 0/0. The declared
  fallback covers only "train_lt_2022's training season", which is doubly mis-scoped: (a) 2021
  rows sit inside EVERY training fold under expanding windows, not just the first; (b) the
  2025/2026 expansion rows are covered by no fallback at all — and they are test rows.

Contrast with arms that got this right, proving the fix is cheap and already program-idiomatic:
A12 (*"no-prior-season teams get dev_prev = 0 identically in arm and null"*), A18/A20/A26 (E=3
deterministic symmetric imputation), A22 (churn := 0 with no base window).

**Required change:** before the P35 freeze, preregister for A09/A10/A11/A16 a deterministic,
symmetric, numerically-triggered empty/partial-window rule (the obvious candidate: deviation
terms := 0 when the window is empty; state whether a 1–4-game window is used as-is), identical in
arm and null, per GATE_INVOCATION_CONTRACT section 4 ("frozen and registered before any result is
visible... There is no third option"). Absent this, P36 implementers exercise discretion on 15
rows — the exact thing a preregistration exists to remove — or the gates fail the arms on
`non_finite` at invocation.

### OP-3 — SEVERITY B. A08's enumeration constraint is self-contradictory as written, and BOTH enumerated K elements fail it on the bytes.

A08's constraint text: *"K elements must keep L_t defined on all rows of every training fold"*.
Measured: rows whose game has fewer than K strictly-earlier completed league games — K=20: 44
rows; K=80: 162 rows — all early-2021, therefore inside EVERY training fold (expanding windows
all contain 2021). Read literally, both elements of the enumeration {20, 80} are inadmissible at
P27 invocation and the arm arrives at P36 pre-dead by its own constraint — 162/410 = 39.5% of the
first training fold is undefined at K=80. Read charitably against the same arm's fallback sentence
(*"league-window undefined rows handled by the window rule identically in arm and null"*), the
constraint sentence is a dead letter. Both sentences are frozen in the same record; they cannot
both govern.

**Required change:** before P35, replace the constraint with the actual rule and its numeric
trigger — e.g., "rows with fewer than K strictly-earlier completed league games take L_t := 0
(training-fold-centered scale) / are dropped from arm AND null identically; measured counts 44
(K=20) and 162 (K=80), all 2021" — so the P25/P27 invocation has a decidable spec instead of a
contradiction to resolve.

### OP-4 — SEVERITY B. A23 bundle_AI's defining semantics ("previous SCHEDULED same-season game") are not computable from any receipted in-scope artifact.

`Glob **/*schedul*` over `experiments/player_program/`: no matches. P33 itself established (for
A06) that no preseason-published schedule artifact exists in scope. The archive carries realized
`game_date`s of COMPLETED games only. "Previous scheduled game" differs from "most recent
completed game" exactly when games are postponed or cancelled — and whether any were, in
2021–2026, is not determinable from in-scope artifacts. So bundle_AI is implementable only under
the unreceipted assumption scheduled ≡ completed, at which point its defining distinction from
bundle_OM silently reduces to cap (7 vs 4) and opener rule.

This is the same class of defect that made A06 INADMISSIBLE_UNTIL_RECEIPTED at D021, but bundle_AI
was not given the same discipline.

**Required change (either branch acceptable, decided before P35):** (a) subject bundle_AI's
prior-game semantics to the A06 discipline — hash-pinned schedule source by the P35 freeze, else
the bundle is preregistered with "previous COMPLETED same-season game" and the substitution is
stated in the frozen record; or (b) preregister the scheduled≡completed assumption explicitly now.
What is not acceptable is P36 discovering the gap and choosing.

### OP-5 — SEVERITY B. The 13-arm PHO/PHX fail-closed precondition rests on an out-of-scope file whose bytes nothing pins.

The precondition machinery itself is REAL and TESTED — this review verified it rather than
assuming it: `merge_guard.py` resolves team_id 1611661317 solely from documented
first_season/last_season interval semantics (PHO 2021–2024, PHX 2025–open; contiguous,
non-overlapping, order-independent under 8 permutation seeds), and the exclusion branch
(`AmbiguousDimensionError` instructing EXCLUDE) is implemented and tested (P23 t06/t07/t13/t14).
The receipt is producible at gate-invocation time; the precondition is dischargeable, not a
landmine. The 13-arm list in `shared_arm_invariants` is also internally consistent: 12 of the 13
carry a per-arm `precondition` key, A14 inherits via the shared invariant plus its feature-level
note, and A23 correctly carries the narrower P23 game_date-join receipt instead.

The gap: the resolver's sole input is `data/reference/team_cities.csv` — OUTSIDE
`experiments/player_program/`, hash pinned nowhere in P33's SPEC (P23 measured it:
`10a544fdc52a9c80c1573437c9838b11815c9eafe6ac2cf052be17a2128ac42d`, 1,892 bytes). The guard fails
closed on AMBIGUITY, not on silent revision: a rewritten team_cities.csv with clean intervals
resolves successfully with different semantics and no error. Thirteen arms' cross-season features
inherit whatever those bytes say.

**Required change:** P35 task cards pin `team_cities.csv` at the P23-measured hash as part of
every franchise-continuity receipt; a mismatch fails the receipt closed. One line per task card.

### OP-6 — SEVERITY C. IRLS non-convergence disposition unspecified.

The estimation-objective freeze is operationally sound under this lens: deterministic, seedless,
cheap, identical tolerance (1e-10 deviance, max 100 iterations) on arm and null — the family
choice itself is another reviewer's dimension and draws no operational objection here. The one
hole: nothing says what happens when the 100-iteration cap is HIT. Evaluable? Unevaluable?
Error? Recommend P35 declare: cap reached in arm or null ⇒ arm/fold unevaluable, symmetric,
recorded — consistent with the program's fail-closed idiom.

### OP-7 — SEVERITY C. A22's supporting claim about |P|=1 rows is measured-false; the rule itself is fine.

A22's fallback note: *"|P|=1 rule declared (rows exist only in early-2021 inside train_lt_2022
training window)"*. Measured: 15 |P|=1 rows — 12 in 2021, 1 in 2025, 2 in 2026 (expansion second
games; the latter three are test-fold rows). The churn := 0 rule is symmetric and covers them, and
|P|=0 is covered by the cold-start text, so operability is intact — but a frozen record should not
carry a measured-false sentence. Correct the parenthetical at P35.

### OP-8 — SEVERITY C. end_reason schema drift is real but tiny; "fail closed" is actually fail-degrade. Record.

Measured level sets differ across seasons only in rare levels: `inferred_flip` absent in 2026,
`miss_flip_no_rebound` sporadic (8 rows total), `made_ft_nonfinal_flip` (2 rows total). At these
magnitudes (~0.09% of possessions) the A19/A20 denominator rule is harmless. But note the
semantics honestly: "unmapped levels count only in the denominator" means a novel level SILENTLY
deflates the share at decision time rather than halting — degradation, not closure. A
preregistered drift alarm (e.g., unmapped share > 1% in any team's trailing window ⇒ flag) would
make it genuinely fail-closed. Optional; record only.

### OP-9 — SEVERITY C. Compute budget is feasible; no arm's operational cost moots its scientific value; A14's diagnostic slot is cheap and worth its price.

Arithmetic (no fit performed): 32 unconditional elements (+2 conditional A06) × 5 folds × 2
designs (arm+null) × 2,001 IRLS fits (point fit + B=2,000 training-cluster refits) ≈ 1.29M
deterministic IRLS fits on designs of at most 2,552 rows × ~8 columns, plus B=10,000 test-side
resamples that only re-index precomputed per-row errors. Single-digit hours of single-core
compute, embarrassingly parallel across elements and folds. A14 — the deliberate
promotion-ineligible arm — costs 1/32 of this to keep the COLDSTART_FALLBACK denominator honest:
correctly spent under this lens.

### OP-10 — SEVERITY C. A06's conditional path is operationally decidable and well-formed; one caveat on repair path (b).

Decidable deadline (P35 freeze), explicit non-admission outcome (PREREGISTERED_CONDITIONAL_NOT_FIT
with the 2 elements leaving the denominator), receipt work correctly routed to the data lane.
Not a landmine as structured. Caveat: repair path (b) (past-only denominator redefinition) changes
the drift-column BYTES while preserving the 2-element form; require that a path-(b) redefinition
be itself hash-pinned at P35 under the same 2-element cap — anything looser is a new arm.

### OP-11 — SEVERITY C. The expected-failure-mode fields pass the boilerplate test. Record as a pass.

Audited all 26: each names a mechanism-specific, falsifiable death — P25 near-affinity for
A08/A09/A10/A16/A17/A26; depth absorption (with the 0.958 fold-1 R2 measured in advance) for A07;
the volume-proxy falsification for A21/A22; named strata with measured row/cluster counts for
A03 (113 rows), A05 (212 playoff team-games, 0 test rows in 2026), A14 (46 clusters, one fold).
None is generic. A24's lag-operator positive-control role and A25's guard positive-control role
are operationally load-bearing and correctly preserved.

---

## Decision-time operability sweep (the dimension's core question, arm by arm)

Every feature in all 26 arms was checked for pre-tip computability from receipted artifacts.
Summary: offset and calibration terms (A01–A05, A15, A25) are functions of the frozen incumbent's
own pre-tip outputs and schedule facts — operable. Lagged-aggregate arms (A07–A22, A24, A26)
require only strictly-earlier completed games at `game_date` granularity
(`possession_features.DECISION_TIME_COLUMN = "game_date"`; same-day fails closed where declared,
e.g. A17) — operable, subject to OP-2/OP-3 repairs. A16's archived-projection join was already
resolved by P33 (all 2,990 team-games retrievable from the frozen artifact). No arm uses
tip-time-derived features, so P29's INELIGIBLE ruling is respected by construction. The two
non-operable constructions found are OP-1 (A19, artifact cannot express the mechanism) and OP-4
(A23 bundle_AI, semantics unreceipted). Cold-start behavior is declared for every cold-start arm;
the declared behaviors are contradicted by bytes only where OP-2 says so.

## What I could NOT establish

* Whether any upstream pbp-level source could distinguish steals/live-ball turnovers (A19 repair
  path): out of scope; would need a new receipted producer.
* Whether postponements occurred in the 2021–2026 archive (whether bundle_AI ≡ bundle_OM on
  prior-game identity in practice): no scheduled-games source in scope — this is OP-4's point.
* Daily-pipeline ingest latency for previous-night games (whether "strictly earlier by game_date"
  content is reliably ingested before tip in live operation): no in-scope receipt speaks to live
  ops timing; the preregistration's fits are unaffected, but a promoted lagged arm inherits this
  unverified operational assumption. Recorded, not resolvable here.
* The contents of the six other reviewer files and the pre-existing operational review: not read,
  by the blindness rule.

## Contradictions found (document vs bytes / document vs document)

1. A16 "defined on all 2,982 rows in every fold" vs 15 measured empty-window rows (OP-2).
2. A09 "continuous on every resolved row" / A10 "defined everywhere" vs the same 15 rows (OP-2).
3. A11's fallback scope ("train_lt_2022's training season") vs 2021 rows present in all five
   training folds and uncovered expansion test rows (OP-2).
4. A08's "must keep L_t defined on all rows of every training fold" vs its own "undefined rows
   handled by the window rule" sentence, and vs the measured 44/162 undefined rows (OP-3).
5. A22's "|P|=1 rows exist only in early-2021" vs measured 2025/2026 rows (OP-7).
6. P33 `could_not_establish` lists the A19/A20 dictionary question as not establishable in scope;
   the deciding bytes are in a mandated frozen input and were read by this review in one query
   (OP-1). The A20 half of the deferral, conversely, resolves in the arm's favor.

## Required changes (the ACCEPT is conditional on exactly these)

1. **(OP-1, A)** A19: withdraw as design failure per its own clause, restating LAGGED_TEMPO_MIX as
   single-member {A17} with the joint-scoring rule explicitly voided and the Holm denominator
   restated — or hash-pin a steal-distinguishing receipted source before the P35 freeze. Bar the
   silent E_LB={turnover} relabeling by name.
2. **(OP-2, B)** A09/A10/A11/A16: preregister deterministic symmetric empty/partial-window rules
   (A12's dev_prev:=0 idiom) with numeric triggers, arm and null identically, at P35.
3. **(OP-3, B)** A08: replace the self-contradictory definedness constraint with the actual
   undefined-row rule and its measured counts (44 @ K=20, 162 @ K=80, all 2021).
4. **(OP-4, B)** A23 bundle_AI: receipt a scheduled-games source by P35 or preregister the
   scheduled≡completed substitution explicitly.
5. **(OP-5, B)** Pin `data/reference/team_cities.csv` (sha256 `10a544fd…ac42d`) in every P35
   franchise-continuity receipt requirement; mismatch fails closed.

C-items (OP-6..OP-8, OP-10 caveat) are recorded for P35's convenience and do not condition the verdict.

---

## Appendix — measurement scripts (verbatim)

### p34_operational_measurements.py
```python
# P34 operational-relevance reviewer: feature/schema-only measurements.
# NO target values enter any statistic. NOTHING is fitted. No performance number computed.
import hashlib, json, sys
from pathlib import Path

import pandas as pd

ROOT = Path(r"C:/Users/jgallagher/wnba-betting-model/.claude/worktrees/player-model-program/experiments/player_program")
POSS = ROOT / "possessions_v2" / "possessions_raw_v2.parquet"

out = {}
h = hashlib.sha256(POSS.read_bytes()).hexdigest()
out["possessions_raw_v2_sha256"] = h

cols = ["game_id", "season", "end_reason", "offense_team_id", "defense_team_id", "duration_sec"]
d = pd.read_parquet(POSS, columns=cols)
out["rows"] = int(len(d))

er = d["end_reason"].astype(str)
overall = er.value_counts(dropna=False)
out["end_reason_levels_overall"] = {k: int(v) for k, v in overall.items()}

by_season = {}
for s, grp in d.groupby("season"):
    vc = grp["end_reason"].astype(str).value_counts()
    by_season[str(s)] = {k: int(v) for k, v in vc.items()}
out["end_reason_levels_by_season"] = by_season

lvl_sets = {s: set(v.keys()) for s, v in by_season.items()}
all_lvls = set(overall.index)
union_minus = {s: sorted(all_lvls - lv) for s, lv in lvl_sets.items()}
out["levels_missing_per_season"] = union_minus
out["level_set_identical_across_seasons"] = all(lv == all_lvls for lv in lvl_sets.values())

tos = sorted([l for l in all_lvls if ("turnover" in l.lower()) or ("steal" in l.lower())])
out["turnover_like_levels"] = tos
out["turnover_like_share_of_rows"] = float(er.isin(tos).mean()) if tos else 0.0

live_markers = ["steal", "live"]
dead_markers = ["out_of_bounds", "out-of-bounds", "offensive_foul", "violation", "travel",
                "3sec", "shot_clock", "shotclock", "dead"]
out["levels_with_live_markers"] = sorted([l for l in all_lvls if any(m in l.lower() for m in live_markers)])
out["levels_with_dead_markers"] = sorted([l for l in all_lvls if any(m in l.lower() for m in dead_markers)])

print(json.dumps(out, indent=2))
```
Key outputs: nine levels as tabulated in OP-1; `turnover_like_levels = ["turnover"]`, share
0.17397920046277085; live/dead marker scans both empty; per-season level differences as in OP-8.

### p34_operational_measurements2.py
```python
# P34 operational reviewer, script 2: schedule-only window-coverage arithmetic.
# Uses load_universe() feature/schedule columns ONLY. No target column is read into any
# statistic; nothing is fitted; no performance number computed.
import json, sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"C:/Users/jgallagher/wnba-betting-model/.claude/worktrees/player-model-program/experiments/player_program")
sys.path.insert(0, str(ROOT))
import possession_features as pf

u = pf.load_universe()
F = u.frame.copy()

games = (F[["game_id", "game_date"]].drop_duplicates("game_id")
         .sort_values(["game_date", "game_id"]).reset_index(drop=True))
gd = games["game_date"].to_numpy()
games["n_league_prior"] = np.searchsorted(gd, gd, side="left")
F = F.merge(games[["game_id", "n_league_prior"]], on="game_id", how="left", validate="m:1")

folds = pf.chronological_folds(u)
for K in (20, 80):
    for f in folds:
        tr = F[F["game_date"] < pd.Timestamp(f.cutoff_date)]
        print(f.fold_id, K, len(tr), int((tr["n_league_prior"] < K).sum()))

F2 = F.sort_values(["team_id", "game_date", "game_id"]).copy()
F2["n_team_prior"] = F2.groupby("team_id").cumcount()
print("lt5:", int((F2["n_team_prior"] < 5).sum()), "zero:", int((F2["n_team_prior"] == 0).sum()))
print({str(k): int(v) for k, v in F2[F2["n_team_prior"] < 5].groupby("season").size().items()})
```
Key outputs: rows with < K strictly-earlier league games = 44 (K=20) and 162 (K=80), identical in
every training fold because all such rows are early-2021; rows with <5 team priors = 75
(2021: 60, 2025: 5, 2026: 10); zero-prior rows = 15.

Inline follow-up (zero/one-prior rows by season and team): zero-prior = {2021: 12, 2025: 1,
2026: 2}; one-prior = {2021: 12, 2025: 1, 2026: 2}; the 2025/2026 rows belong to team_ids
1611661331 / 1611661327 / 1611661332 — the measured expansion set, corroborating P33's A14
support numbers from an independent construction.
