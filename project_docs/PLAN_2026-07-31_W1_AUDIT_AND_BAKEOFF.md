# PLAN — W1 audit/hardening and the four-model bake-off

*Written 2026-07-31. **This is a proposal awaiting John's freeze.** Nothing in §2 is
registered yet and no model work begins until it is. Governed by `HANDOFF.md` §3,
`ROADMAP.md`, `PROGRAM_FIREWALL.md`, and the registry amendment chain
(`screening_protocol_amendment_v2`…`v5`, `conditional_edge_design_freeze_v2`), later
amendments controlling.*

---

## 0. Session verification (done before planning)

| check | result |
|---|---|
| repo / branch / HEAD | `C:\Users\jgallagher\wnba-betting-model`, `data-refresh-2026`, `1e0338a` |
| `python daily_certify.py` | **WARN** — 0 fail, 1 warn, 8 pass. Warn is the tip-time hook (3 commence-time changes, WARN-mode) |
| `verify_chain(forecasts/forecast_log.jsonl)` | **ok=True**, 3 records |
| five gating suites | **all exit 0** — 36 + 22 + 8 + 8 + 5 = 79 tests |

**One state correction.** `ROADMAP.md` §D says the prospective log began with the
`WNBA_DailyForecast_AM` task's "first fire 2026-07-31 10:20 ET". The scheduler disagrees:

```
WNBA_DailyForecast_AM  Last=11/30/1999  Result=267011 (SCHED_S_TASK_HAS_NOT_RUN)  Next=8/1 10:20
WNBA_DailyForecast_PM  Last=11/30/1999  Result=267011                             Next=7/31 18:45
```

Both forecast tasks — and all four `WNBA_PropsCapture_*` tasks — have **never executed**.
They were registered today *after* their morning triggers, so there was no missed run for
`-StartWhenAvailable` to catch up. The three chain records were written by a manual run.
This does not invalidate the log (the records are legitimate, hash-chained, and were
committed before outcomes existed) but it means **the automated path is unproven**. First
real scheduler-driven run is tonight 18:45 ET. Two follow-ups:

- Verify tomorrow that AM (10:20) and PM (18:45) both fired and appended.
- `WNBA_PropsCapture_1..4` have `StartWhenAvailable=False` — the §5 gotcha is still live on
  those four tasks and should be flipped.

---

## 1. W1 quality-and-integration audit plan

### 1.0 What I already measured (scoping only — no model, no outcomes touched)

These are cheap descriptive counts over the capture corpus. They reframe the problem, so
they belong in the plan rather than after it.

**Finding A — the corpus is headlines, not articles.** `news_capture_daily.py` populates
`summary_text` from the RSS `<description>` element (cap 1500 chars). Empirically, across
1,672 captured items:

| | |
|---|---|
| `summary_text` median length | **90 characters** |
| items in the 60–150 char band | 1,389 / 1,672 (83%) |
| items with ≥3 sentences | **23 / 1,672 (1.4%)** |
| items with empty `summary_text` | 83 |
| `title` median length | 86 characters |

**Finding B — extraction is therefore headline classification, and the evidence guardrail
proves it.** Matching each extraction's `quoted_evidence` back to its source item:

| grounding of `quoted_evidence` | n | share |
|---|---|---|
| verbatim substring of the **title** | **331** | 93.5% |
| verbatim substring of `summary_text` only | 22 | 6.2% |
| neither (paraphrase / ungrounded) | **1** | 0.3% |

The quoted-evidence requirement is working almost perfectly — 353/354 extractions are
literally grounded in captured text. The problem is not that Claude invents things; **it is
that the only text it is given is a headline.** That also explains the tier distribution:
`aggregator` 324/354, because a headline rarely reveals whether the underlying source is a
coach, a team account, or a content farm.

**Finding C — the raw corpus cannot be retroactively upgraded.** `data/news_capture/raw/`
stores the *feed* documents (RSS XML, ESPN JSON, AP/WNBA index HTML), not article pages.
Article bodies were never fetched, so no reprocessing of stored bytes can recover them.
Full text requires a **new forward-only fetch stage**.

**Finding D — the actionable funnel, on current fields alone.**

```
 354  all extractions
 137  specific status (≠ unknown)
  95    and not flagged speculation
  88    and team resolved
  23    and non-aggregator source tier
   0    and referencing a specific game date
```

`game_date_referenced` is `none` in 335/354. So **no extraction is currently attachable to a
particular game except by publication-time proximity** — which is a large part of why the
retrospective overlay touched one row.

**Finding E — duplication and versioning.** 354 rows over 284 URLs. 57 URLs carry >1 row;
38 of those are legitimately multi-player, but **19 are repeat rows for the same player**,
and there are **26 exact duplicate `(url, player, status)` triples**. Extraction is keyed by
source+URL with no content hash, so re-captures re-emit rather than version.

### 1.1 What this means for the audit's design

The brief asked whether captured text is full article or snippet, and to label those
separately. The answer is that the corpus is ~99% snippet, so a "full-text vs snippet"
split has no full-text stratum to compare against. The audit is therefore restructured:

- **A1 (measure the ceiling).** Audit the *existing* headline-grade layer honestly and
  quantify what it can and cannot support. Do not tune it.
- **A2 (test whether the ceiling moves).** Add a body-fetch stage on a bounded sample and
  re-extract, so "headline-grade" vs "body-grade" becomes a real measured contrast rather
  than an assumption.

### 1.2 Work items

**W1-A — Truth set.** Build a per-player-game availability ground truth from sources we
already hold: official injury-report designations (`data/injury_capture/`, deterministic
parse), realised active/DNP from `master_player`, realised minutes, and confirmed starters.
Key on `(player_id, game_id)`. This is a data-engineering artifact and is *permitted*
cross-program information under the firewall.

**W1-B — Entity resolution as-of publication.** Resolve `player_name` → `player_id` and
`team` → `team_id` **against the roster as it existed at `published_utc`**, not today's
roster. Report: resolution rate, ambiguity rate (`Sykes` in the sample is a live example of
a surname-only mention), and wrong-team rate. Trades and 7-day contracts are the hazard.

**W1-C — Precision / recall / false-availability.** Against W1-A, per stratum
(status × source tier × speculation flag), report precision, recall, and the brief's
requested **false availability signals per 100 extracted player mentions**, each with a
Wilson interval. Strata with fewer than ~20 mentions get an interval and no point claim.

**W1-D — Source tier from metadata, not from the model.** Build a deterministic
domain→tier map (`wnba.com`/team domains → `team_official`/`league_official`; known beat
outlets → `beat_reporter`; syndicators → `aggregator`) and compare it to the LLM's tier.
Expectation from Finding B: the deterministic map is strictly better, because tier is a
property of the publisher, which is metadata, not of the sentence. Recommend the LLM tier
be **demoted to a corroborating field**.

**W1-E — Versioning and dedup.** Re-key extraction on
`(url, content_sha256, published_or_updated_utc)` so an article revised at the same URL
becomes a **new version** rather than a silent miss, and duplicate re-emissions collapse.
Separately, measure what normalized-title dedup is discarding: for a sample of dropped
items, check whether the dropped copy came from an *independent* publisher — corroboration
from two independent sources is signal, and dropping it is a loss.

**W1-F — Contradiction and supersession.** Define an explicit precedence order (official
designation > team official > coach > beat reporter > aggregator; and later-published
supersedes earlier at equal tier), then **measure how often it fires** and how often it
would have changed the fielded signal. Contradiction rate is itself a quality metric.

**W1-G — Abstain / confidence field.** Add a required three-way field to the extraction
schema: `supported` (status stated in quoted text), `ambiguous` (text touches availability
but does not state a status), `unsupported_inference` (status not derivable). Under Finding
B the current `unknown`/speculation pair is doing this job badly — `unknown` conflates "the
article says nothing" with "the headline is too short to tell".

**W1-H — Stratified manual audit sample.** ~150 extractions, stratified by status × tier ×
speculation, reviewed by hand against the source URL and W1-A. This is the only way to
measure the LLM's error modes rather than the pipeline's. Report inter-rater agreement on a
30-row overlap if John reviews a subset.

**W1-I — Body-fetch pilot (the A2 arm).** Fetch article bodies for a bounded sample
(~300 URLs, robots-respecting, rate-limited, cached to `raw/`), re-run the *unchanged*
extraction prompt, and re-measure W1-C and W1-D on the same URLs. This is the decisive
experiment: it separates "the prompt is weak" from "the input is a headline". **Cost and
legal surface must be approved before this runs.**

**W1-J — The quantified answer.** Re-run the Finding-D funnel with resolution, truth-match
and the abstain field in place, and state plainly: *how many genuinely actionable pre-cutoff
player-game signals per slate does W1 produce, headline-grade and body-grade?* If the honest
answer is "under one per slate", W1 is not a model input this season and the plan says so.

### 1.3 Integration rule (unchanged from the brief, restated as binding)

Any W1-informed model is **frozen and logged alongside the core-only model prospectively**,
in the same chain record (`core_only_prediction` / `core_plus_w1_prediction` already exist
in the schema and are currently null). It must estimate **three separate quantities**:
`P(active)`, `E[minutes | active]`, and **uncertainty around conditional minutes**. The LLM
supplies **evidence only**; a statistical layer converts evidence to probabilities and
minutes. No fixed cap (e.g. "out ⇒ ≤0.25") is promoted unless it beats the appropriate
baseline **prospectively**. Regime **B** for any historical availability subset work,
regime **C** for the oracle bracket, regime **D** for the live pairing.

---

## 2. Four-model bake-off — registration text (NOT yet registered)

**Registration id:** `player_model_bakeoff_v1` · **regime A** · **kind:** experiment
**incumbent_id:** `ewma_ridge_incumbent` · **primary_metric:** `minutes_mae_oof`
**decision_time:** T-24h

**Hypothesis.** The incumbent EWMA/ridge player layer **underfits player behaviour**, and at
least one of three challengers materially reduces error in minutes, volume and scoring
channels on identical as-of inputs, folds, targets and evaluation rows.

**Arms.**
1. **Incumbent** — current EWMA/ridge, unchanged, as the control.
2. **Dynamic hierarchical player profiles** — *highest priority*. Partially pooled latent
   states for stable ability, current form, role, availability, minutes, shot volume, shot
   mix and conversion, with **player-specific update speeds** and **explicit uncertainty**
   for rookies, returns, trades and sparse histories.
3. **CatBoost** — nonlinear and categorical player/team interactions ridge cannot represent.
4. **TabPFN** — pretrained small-data tabular challenger.

**Identical-treatment clause (binding).** All four arms receive the same as-of feature
matrix, the same walk-forward fold boundaries, the same targets, and the same evaluation
rows. Any arm that cannot consume the shared matrix is **dropped, not accommodated**.

**Comparisons** (all reported per arm):
minutes and volume error · scoring-channel and total-points error · calibration and
distributional accuracy (CRPS, pinball, reliability) · **incremental value over the market**
· coverage and operational failure rate · **performance split by player-history depth and
rotation regime**.

**Multiplicity and inference.** m = (4 arms − 1 control) × (6 metric families) = 18 primary
comparisons. Per amendment v5 C2, a single predetermined
`B_final = max(2000, ceil(m/q)) = 2000` at q = 0.10, fixed before the first draw, with the
only permitted early stop being the impossibility bound `(1+e)/(B_final+1) > q`. Nulls
blocked by **player-season** and by **game-date**, decision on the more conservative, per
v2 P3. Every arm × metric cell carries its **MDE beside the result**, per v4 P1-CORRECTION.

**Degrees-of-freedom control.** Each challenger gets a **fixed hyperparameter grid named in
the registration** and tuned only by walk-forward inner CV on the fitting slice. CatBoost
and TabPFN are the two arms most able to launder selection into apparent skill, so their
grids are small and stated in advance.

**Negative control.** Per v4 P5, all three challengers fit and select parameters, so each
runs a label-permuted arm; a challenger whose permuted arm also "beats" the incumbent is
disqualified before its real result is read.

**Provenance bar.** Per v5 **C3-BLOCKING**, no bake-off result may support any promotion,
nomination or freeze decision until every fitted artifact it consumes or produces carries a
manifest with dependency hashes, config hash, producer commit, data-snapshot hash, and
`fit_through` recorded as *when the source information became available*. Results may be
computed, recorded and discussed during the gap; they may not confer legitimacy.

**Slices.** Fitting and model selection on 2021–2024. **2025 is a development check, not
confirmation.** 2026 is retrospective descriptive only. **The prospective live log is the
only holdout that can promote anything.** Identical to
`conditional_edge_design_freeze_v2` — and this matters especially here, because the
motivation ("is the incumbent underfitting?") arises from having already seen 2025–26
results.

**Firewall note for the `extra` field.** This bake-off is a **player-rate program**
activity, and its motivation is cross-program: it was prompted by game-model and props
results on 2025–26 (props lose to lines in every slice). Under `PROGRAM_FIREWALL.md` rule 3
this must be declared in the registration. Under rule 1, no arm, feature or encoding may be
selected by reference to a 2025/26 outcome; selection evidence must be 2021–2024 only.

---

## 3. Required data and compute

**Already in hand (no new acquisition).**
- `data/masters/master_player.parquet` — 33,636 player-game rows, 2021–2026, 1,058
  player-seasons, 881 with ≥20 games.
- Possessions, shots, lineups, RAPM walk-forward, zone maps, officials.
- Odds: `master_odds_extension` + hourly live capture; props via `master_props`.
- W1: 1,672 news items, 354 extractions, official injury PDFs.

**Needs building.**
- **Shared as-of feature matrix** for the bake-off, emitted **with a manifest** (this is the
  C3 migration's first real consumer, so build it manifest-first rather than retrofitting).
- **W1-A truth set** (player-game availability/minutes/starter).
- **Domain→tier map** (W1-D), roster-as-of index (W1-B).

**Needs a decision from John.**
- **Article body fetch** (W1-I) — bandwidth, robots/ToS surface, storage. My recommendation:
  approve a bounded 300-URL pilot only.
- **Odds tier by ~Aug 30** (carried from the handoff) — props need the paid tier, and the
  props arm is where the statistical power actually is (see §4).

**Compute.** Arms 1–3 are CPU-modest. TabPFN wants a GPU for comfort but runs on CPU at
these row counts. The binding cost is **permutation**: 2,000 draws × refit-everything-
downstream (amendment v2 P3 requires every iteration refit every feature-dependent
parameter). For CatBoost that is the dominant line item; budget it explicitly before
starting, and if it does not fit, **reduce the metric families to reduce m** — do not
reduce B.

**Anthropic API.** Re-extraction for W1-I: ~300 articles × 2 (headline vs body arms).
Modest. Keys stay in the git-ignored `.env`; the repo is public.

---

## 4. Sample-size limitations

**This section is the reason to read the plan.** I computed it rather than asserting it,
from `experiments/clv_transfer/matched_gap_by_cutoff_and_season.csv`.

2026 margins at T-24h: n = 150 games over 57 game-dates, gap = +0.116, CI90
[−0.544, +0.291]. Half-width 0.418 at z = 1.645 ⇒ **clustered SE = 0.254 points**.

2026 has 212 games played (15 teams, ~2.52 games/day since May 8). A 15-team, 44-game
season is ~330 games, so roughly **118 regular-season games over ~47 dates remain**.
Scaling the clustered SE by √(57/47) gives SE ≈ 0.280, so at 80% power and two-sided
α = 0.05 the **MDE for the rest of the 2026 season is ≈ 0.78 points**.

The effect under dispute is **0.12 points**.

| horizon | game-dates | MDE (margin, points) |
|---|---|---|
| rest of 2026 | ~47 | **0.78** |
| + a full 2027 | ~177 | 0.40 |
| to detect 0.12 | **~2,000** | ≈ **14 WNBA seasons** |

**The margin-versus-market question is not answerable prospectively on any timescale this
project operates on.** That is not a reason to stop; it is a reason to stop treating margin
MAE as the decision surface.

Cross-check that the method is sound: for unit-stake betting, MDE(ROI) ≈ 2.802/√n. At
n ≈ 200 bets that is **+0.198**, which reproduces the conditional-edge game arm's registered
MDE of **+0.199** almost exactly. The arithmetic is behaving.

**Consequences, which should shape what we build:**

1. **Anything decided on ~118 games is underpowered by roughly 6×.** Every null from this
   season must state this, and per v4 P1-CORRECTION, no effect may be called real merely
   because it exceeds its MDE.
2. **Props are where the power is.** ~118 games × ~15 player-markets ≈ 1,750 rows against
   a much larger disputed effect (0.31 vs 0.12). The clustered SE for props is **not yet
   computed** and computing it is a prerequisite of `calibrated_prob_edge_v1`, not an
   afterthought — the amendment already requires MDEs beside every bucket.
3. **ROI cannot be the primary prospective metric this season.** Detecting +5% ROI needs
   ~3,100 bets; +2% needs ~19,600. We will have hundreds. ROI is reported and never
   used to promote on this sample.
4. **The bake-off's honest ambition is development-stage model selection, not a market
   claim.** It should be judged on minutes/volume/channel error where n is large
   (33,636 player-games), not on whether it beats a line.

---

## 5. Implementation order

Ordered so that each step unblocks the next and nothing computes before it is registered.

| # | step | gate to clear before starting |
|---|---|---|
| 0 | **John freezes this plan.** | — |
| 1 | Fix `WNBA_PropsCapture_1..4` `-StartWhenAvailable`; confirm tonight's 18:45 run appended and tomorrow's 10:20 fired. | none — operational |
| 2 | **C3 provenance migration** — `assert_asof_metadata` split, `assert_asof` defaults `verify_hash=True` and fails closed, builders emit manifests. | none — infrastructure |
| 3 | **W1-A/B truth set + as-of roster resolution.** | step 2 (emit with manifests) |
| 4 | **W1-C/D/E/F/G audit** on the existing headline corpus; register as regime **B**. | registration committed first |
| 5 | **W1-H manual audit sample.** | step 4 |
| 6 | **W1-I body-fetch pilot.** | John's approval of cost/ToS |
| 7 | **W1-J** — the quantified actionable-yield answer. Decide here whether W1 becomes a live input at all. | steps 4–6 |
| 8 | **Shared as-of feature matrix** for the bake-off, manifest-first. | step 2 |
| 9 | **Register `player_model_bakeoff_v1`**, then run arms 1→2→3→4. | step 8; registration committed before any arm runs |
| 10 | **`calibrated_prob_edge_v1`** — already registered in full; run it without redesign. Its props MDE computation (§4.2) lands here. | independent of 3–9; can run in parallel |

Steps 1, 2, 8 are infrastructure and can proceed immediately on a freeze. Steps 4–7 and 9
are development evidence. Nothing in this list promotes anything.

**Why `calibrated_prob_edge_v1` is listed last but can start first:** it is registered, its
design is frozen, and re-registering or redesigning it after seeing anything would consume
its evaluation slice. It should run as-is, whenever there is capacity.

---

## 6. Infrastructure vs development evidence vs prospective promotion

The brief asks for this separation to be explicit. Stated as a rule with each item assigned:

**Infrastructure** — builds capability, makes no predictive claim, needs no holdout, cannot
promote anything. Free to proceed on a freeze.
> C3 provenance migration · shared as-of feature matrix · W1-A truth set · roster-as-of index
> · domain→tier map · content-hash versioning · abstain field · scheduled-task fixes · the
> body-fetch stage itself.

**Development evidence** — measured on 2021–2024 (and 2025 as a *development check*, 2026 as
*retrospective description only*). May rank, select and freeze candidates. **May never be
described as confirmation, and per v5 C3-BLOCKING may not support promotion until the
provenance bar is met.**
> The whole W1 audit (W1-C…W1-J) · all four bake-off arms · the props MDE computation ·
> anything computed on a season whose outcomes we have already seen.

**Prospective promotion** — the **only** surface that can promote: `forecast_log.jsonl`,
records committed before outcomes exist, hash-chained, frozen model, no refits.
> Core-only vs core+W1 paired live · the frozen `calibrated_prob_edge_v1` policy ·
> `prospective_pockets_v1` paper cells.

**Three rules that keep the boundary from eroding:**

1. **A model may cross from development to prospective exactly once, frozen.** Any change
   after live scoring begins is a new model with a new id and a new chain, and the old
   record stands.
2. **Registration precedes computation, always.** Including the audit — a "quality audit"
   that reports precision after choosing the threshold that made precision look good is a
   selection procedure wearing a lab coat.
3. **The recursive-AI firewall holds throughout.** An AI may propose and implement
   candidates; registration precedes results, a deterministic evaluator judges them, a
   separate audit checks leakage and provenance, and only the prospective log promotes.
   Subagents never run git, never register, never render leaderboards; the orchestrator
   verifies every number from row-level artifacts before recording it.

---

## 7. The one thing I'd flag hardest

§4 is the finding that should change plans. The project's stated goal — beat the market on
game margins — is **statistically unreachable on this sample**, by a factor of about six for
the remainder of this season and about three even with all of next season added. Continuing
to measure it is fine; *deciding* anything on it is not.

The two surfaces with enough rows to say something real are **player-level quantities**
(33,636 player-games, where the bake-off lives) and **props** (~1,750 prospective rows
against a 0.31 effect). I'd propose the program's near-term question be narrowed to those,
with margins reported as a monitored diagnostic rather than a decision variable. That is a
scope change, so it is John's call, not mine — flagged here rather than assumed.
