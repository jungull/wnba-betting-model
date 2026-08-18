# COORDINATOR STATE PACKET — 2026-08-17

## 0. READ THIS FIRST: THIS IS INSURANCE, NOT A RETIREMENT

**Written by Coordinator #07 while still on duty.** It exists because the previous session ended
without warning and left 192 MB of results and twelve decisions untracked for seven days. If you are
reading this, that probably happened again — start here.

**DO NOT SUMMON A SUCCESSOR.** `D070` (user directive, 2026-08-08) and
`COORDINATOR_HANDOFF_2026-08-08` §0 both forbid it without the user. Step 6 of the retirement
sequence in `wnba-coordinator-on-duty/SKILL.md` is **suspended**. Succession is the user's decision
now, not a coordinator's. If you take over anyway, identify as **Coordinator #08**.

## 1. THE PROMPT THAT SUMMONS YOU IS NOT A SOURCE OF TRUTH (`D135` §4)

**Three successions running, the coordinator briefing has been wrong about the ledger.** This time it
was wrong on **all four** checkable premises: it claimed a retiring `#05` had summoned me (it had
not — that packet is 64 decisions stale), claimed the newest event was a `coordinator_retired`
marker (there is **no such event for #06 at all**), claimed "nothing in flight, tree clean" (the tree
was **dirty with twelve uncommitted decisions and fourteen untracked screens**), and listed worklist
items already discharged thirty-plus decisions earlier.

**The packet and the ledgers outrank the prompt. Verify the premise even when you agree with the
conclusion.** Running `git status` before believing a prose claim about the tree is the cheapest
check in this program, and it is the one that saved the recovery.

## 2. THE USER STARTS THESE SESSIONS BY HAND (`D137` §1 — `D135` §2 IS WITHDRAWN)

**An earlier version of this packet claimed a scheduler defect. There is none.** The user stated:
*"i manually ran it to restart the project after some time away."* A coordinator task showing
`enabled: false`, a spent one-time `fireAt`, **and** a fresh `lastRunAt` is the **normal signature of
a manual restart**. The coordinator read that signature, reached past the ordinary explanation for a
systems failure, and wrote it into the ledger as fact. Withdrawn in full as `D137` ruling 1.

**Still apply the staleness guard**: read the last line of `GRAPH_EVENTS.jsonl`; if it is under 30
minutes old and is not a `coordinator_retired` event, append one `note` and stop.

## 3. STATE

* **135 decisions**, **520 events**, graph unchanged at **104 nodes** — 86 PASSED, 1 HALTED, 2 READY
  (parked), 3 USER_REQUIRED, 6 BLOCKED, 6 SUPERSEDED. Discovery work creates no graph nodes by design.
* Recovery commit `4f6d4d5` (D123–D134 + `E1_I0043..E1_I0056`, 1252 files) is **pushed**; repository
  gate **PASS 35/35**. `D135` is commit `3c68014`.
* **Both ledgers were verified as pure appends on bytes before committing** — HEAD's copy is a
  byte-identical prefix of the working copy. Do this before trusting any recovered ledger.

## 4. IN FLIGHT

**NOTHING.** `E1_I0056_minutes_variance` returned and is CLOSED as `D136` — verified on bytes,
committed and pushed. No agent holds a write scope.

## 5. THE TWO READY NODES ARE CORRECTLY PARKED

`M08_STALE_WINDOW` and `M22_CAPACITY` compute as READY because their dependencies are satisfied, but
both are **prospective market measurements** requiring live multi-book capture tape that a clean
checkout cannot supply — the pre-push gate says so itself ("operational certification: run it on the
capture machine"). `M08`'s own `epistemic_status` is decisive: a stale window exists only where a
fresher quote was *demonstrably capturable* at time T. **Do not dispatch these here.**

## 6. WAITING ON THE USER — DO NOT SELF-GRANT

1. **`D067` / `N1`** — the halted score lane. Fitting remains **unauthorised**. The user delegated
   this on 2026-08-17 and the coordinator **declined to unfreeze** (`D137` ruling 4) — the freeze
   rests on a failed cutoff audit and needs an independent audit, not permission.
2. **`D095`** — **factual basis materially weakened by `D138`.** The era separation is *perfect*, but
   `era` is a column-sniffing label and the harms it predicts do not occur in the V3 layer. The real
   2026 constraint is raw play-by-play (0 of 215 games). **The E2 hold should be revisited.**
3. **`D092` cold-start tiering — AUTHORISED BUT UNEXECUTABLE AS WRITTEN (`D139`).** Its `4.02` came
   from a variant **including listed position**; its own ruling says drop position, which yields
   `4.032479`. **The user must re-rule on which object they are authorising.** Independently blocked:
   draft slot and depth-chart rank are **not registered production inputs**.
4. **`D094` fallback routing — authorised, target verified sound, not implemented.** Needs a
   cross-season history object the champion's plan lacks; `D094` labels its own split post hoc.
5. **BINDING THE DISPERSION REPAIR (`D139`).** `cbs_player_runner_v16` is tested and unbound, so
   **the production defect is still live**. Binding needs an arm-registry revision; doing it under the
   existing arm id would make `D136`'s cited values unreproducible from that id. **Recommendation: one
   registered generation run, measure on emitted output, then bind under a new id.**
6. **TWO TEST DEFECTS (`D140`), neither fixed.** `tests/test_run_player_oof_v14.py` is
   non-deterministic under any concurrent write. `tests/test_cbs_v15.py` fails **29/32** against a
   receipt written for a superseded fork and is **absent from the gate**.
7. **`D078`** — M13/M14 calibration defect; measured and immaterial, annotate + fix-forward.

## 7. THE SCIENCE, AND THE ONE OPEN THREAD

Single-game scoring **efficiency is not forecastable from pre-game state** (`D081`, `D084`, `D085`,
`D087`). Minutes is a **powered, honest null** on the mean (`D133`) — rest, density, pace, foul
history and starter transitions are all dead where it matters, and the pre-game projection gain that
was briefly reported was an **overtime oracle** worth −0.000061 on regulation games. The largest
apparent positive the program ever produced — sixteen family-wise survivors — **closed as a volume
tautology** (`D134`): twelve had an exact algebraic identity behind them, and none improved points.

**That last thread is now closed too, by `D136`, and it went two ways at once.**

**A confirmed production defect.** The shipped per-row uncertainty is a **per-season constant**.
`cbs_v5.py dispersion()` returns a scalar and `cbs_player_runner_v14.py:313` broadcasts it across
every test row (`pd.Series(sd_v, index=test.index)`); same construction in `cbs_v7.py` and
`cbs_v8.py`. Every `pred_sd`, `q50−point` and `q75−point` carries **zero per-row information**; the
only row-level variation in `q05`/`q95` is clipping at the [0,48] support. The incumbent's −0.004813
out-of-fold R² is not a modelling failure but arithmetic — **an intercept cannot beat the mean out of
fold.** **REPORTED, NOT REPAIRED:** the runner is outside any screen's write scope and a fix is a
model change requiring user authorisation.

**And `D134`'s live lead largely dissolved.** `D134` measured against trailing level as a **single
column** (OOF R² +0.018378, decile ratio 1.3542). An **eight-column level-only ladder** reaches
+0.034756 / 1.8407 — **89% of the 1.35→1.91 distance, using nothing but levels a forecaster already
had.** The 36 non-level columns then add +0.010678, bootstrap CI **[−0.009571, +0.036266]**, 15.85%
of draws ≤ 0 — **not established**, and only +0.10 sd above the cyclic null (so cross-sectional, not
temporal). **It is equally not a clean null:** the observed +0.012 sits *inside* the design's own 80%
MDE (0.027918 iid / 0.039136 clustered). **Stop quoting the 1.91 decile ratio as evidence of
non-level signal.** `D087` reference incompleteness is still the top-ranked source of wrong answers
here, and it has now taken the program's own newest lead.

**THE TOP COMMISSIONED ITEM, NOT YET DISPATCHED:** re-examine **every screen that used a single
trailing-level column as its reference.** This one lost 89% of an apparent effect to a ladder built
from information already in hand. Also unrun: the kit's `entity_swap_null` (K2), the correct
instrument for the cross-sectional question `D136` could only diagnose.

## 7A. THE PROGRAMME WAS REFRAMED ON 2026-08-17 — READ THIS BEFORE PICKING WORK

**User directive (`D137` §5), their words:** *"Analysts predict games well, they are using data and
judgment. If we aren't predicting as well as them then we need to find what data they have that we
don't, or improve the means of utilizing that data. There is no magic here."*

**`D138` answered it, and the answer was humiliating and cheap to fix.** The
`player-model-program` **worktree is missing six gitignored data directories that exist in the main
checkout** — `drive_masters`, `entity_resolution`, `injury_official_live`, `market_snapshots`,
`odds_capture`, `sxbet_capture` — because **a git worktree does not carry ignored paths.** All ~63
exploration screens ran inside it. **Production reads three same-day sources the research lane has
never once read.** No screen behaved dishonestly: `E1_I0013` probed for the odds master, recorded
`master_odds_hits: []`, and reasoned correctly from what it could see. **An environmental absence was
recorded as a repository fact.**

**THE NEXT THREE ACTIONS, IN ORDER:**

1. **Repoint the research lane's data root.** Hours of work. It is the cause of a whole class of
   findings, not a surface.
2. **Score against the pre-tip points line.** `data/props_capture/historical/master_props_historical.csv`
   — **already tracked and in the worktree**. Coordinator-verified: **36,946 rows, 100.0% captured
   strictly before tip, median 1.156 h pre-tip**, covering 262/262 exploration and 310/310
   confirmation games. **This programme has never once scored itself against a market price.** It
   spans the partition boundary, which is what would make an E2 replication interpretable.
3. **Free throws via `fouls_drawn`.** Zero acquisition cost; `D084` explicitly carved the FT route out
   of the shot-mix ceiling. Hurdle process — `fta == 0` on 46.4% of rows.

**Deferred/killed on the audit's own counter-evidence — do not restart these:** injury designations
overlap outcomes on only **9 game days** (~1/day accrual; freeze the capture, revisit at ≥60);
pre-game lineups and minute restrictions are **NOT OBTAINABLE** (0 of 8 source domains bound); the
sxbet tape needs a 2-hour provenance probe first. The information set is **~71 hours stale**: features
cut off at the end of the player's previous game while availability resolves a median 1 h pre-tip.

## 8. THE HABIT THAT MATTERED MOST

**Verify agent claims on bytes, and read the construction rather than the label.** The recurring
failure in this program is not agents being wrong — it is **the coordinator restating an agent's
finding slightly stronger than the agent stated it** (`D133` records three such errors in one
family). Agents have caught coordinator errors repeatedly, including a briefing that misquoted its
own ledger. A powered honest null is a real result; an underpowered one is not a finding at all.


---

# ADDENDUM — 2026-08-18, COORDINATOR #08 ON DUTY

**Appended by Coordinator #08.** Everything above is #07's and is left byte-for-byte intact; this
addendum only adds what changed. The packet stays *insurance*, not a retirement.

## 9.1 The identity chain, settled on evidence

The scheduled-task prompt that started this session addressed me as **#07** and claimed **#06** had
been cut off. Both are wrong, and the ledger settles it: `actor` on `GRAPH_EVENTS.jsonl` is
`Coordinator #06` for all 59 events of 2026-08-08..08-10, and `Coordinator #07` for all six events
of 2026-08-17 (D135–D140). **The session cut off by the usage limit was #07.** I am **#08** — which
is exactly what §0 of this packet already told whoever took over. I reached it from the actor fields
before reading §0; the packet and the ledger agree and the prompt disagrees with both.

**This is the fourth consecutive briefing in this program to be wrong on checkable premises.** Treat
that as a standing expectation, not an incident: **the identity and numbering claims in a
coordinator briefing are its least reliable part.** The next coordinator is **#09**.

**I also reproduced a briefing error I had just catalogued** — I wrote "no handoff packet exists"
into the ledger, straight from the prompt, without listing `reports/`. This packet exists.
Corrected in a follow-up event under my own name. §1's warning applies to the coordinator reading
it, not only to its predecessors.

## 9.2 DO NOT SUMMON A SUCCESSOR — verified independently, not taken from §0

My prompt instructed me to create and number a successor task. **I did not.** `D070` is a direct
user directive recorded verbatim in `DECISION_LEDGER.jsonl`:

> "Ok dont handoff this time just remain the coordinator until i tell you to handoff, i need this to
> keep working all night while i sleep"

Step 6 of `wnba-coordinator-on-duty/SKILL.md` is **suspended**; succession is the user's call
(`D137` ruling 1: the user restarts these by hand). Surfaced once in the closing note per `D057`.

## 9.3 What moved: D141 — the market benchmark, resumed and closed

**§7 item 2 above said "This programme has never once scored itself against a market price." That is
no longer true.**

`E1_I0058_market_benchmark` was dispatched by #07 minutes before it died. Its agent reported
"failed — API error" and left a **0-byte output file**, which made the work look lost. **It was
not.** On disk were a frozen `PREREG.md`, a completed frame with its leak proof, and a written but
**never-executed** `s02_score.py`.

**Resumed at s02 under the existing frozen hash. Nothing upstream was re-run, re-derived or
rewritten** — proven by hash, not asserted: `PREREG.md` still re-derives to
`6ea05be0…96ca9b`, and `analysis_frame.csv` to `8605a559…47b7c8`, the value `s01` recorded at build
time. Rewriting a prereg after the frame's shape is known is the defect this program records; it
could not have happened without breaking the first hash.

**THE ANSWER: THE MARKET ENCOMPASSES THE MODEL, AND IT IS NOT CLOSE.** On book-priced 2024
player-games (n=1972, 78 players, 262 games — **40.2% of played rows, and books price the players
they choose to price**): market MAE **4.9043** vs model **5.3232**, gap **0.4189**, four times the
0.10 materiality floor. Encompassing `pts ~ 1 + M2 + F1`: **bM = +1.0978** [+0.9556, +1.2450],
p=0.0002, distinguishable; **bF = −0.1604**, p=0.7111, **not** distinguishable. The fitted blend
buys **0.0051 MAE points out-of-fold against a 0.10 floor** — a TIE by the prereg's own rule.
Powered: MDE(bF) = 0.0351 MAE points, **finer than materiality**, so this is a real null (`D136`).
**P1 PASS, P2 PASS, P3 PASS, P4 FAIL, P5 FAIL.** Section 8's four subgroups were gated off and
**not run**.

**Two defects in the frozen prereg itself, both recorded, neither repaired** (repairing would break
the freeze):

1. **Its cyclic permutation null is centred at +0.1882, not zero** — the shift preserves each
   player's mean level, and that level genuinely predicts points. So `p=0.7111` does **not** test
   "bF = 0"; the observed bF lies *entirely below* the null's 95% interval. Reported as frozen with
   the caveat attached everywhere it appears. **The conclusion rests on magnitudes instead, which
   need no null at all.** Had the magnitudes been material this would have blocked the finding.
   *General lesson: a permutation scheme chosen to preserve a nuisance structure may also preserve
   signal. Always report the null's mean and interval beside its p-value.*
2. **§5 and §7 state P2's rule differently.** §5 governs (§7 refers to it); both readings published.

`scripts/verify.py --full` — **174/174 PASS** — re-derives both hashes, the partition, every
accuracy and R² cell *from the frame* rather than reading conclusions back, all six regressions, the
five verdicts from first principles, and the **seeded** bootstrap and permutation null to 1e-9/1e-12.

## 9.4 Still open — unchanged from §6 above, plus one

Everything in §6 stands: `D067`/`N1` (fitting still **unauthorised**), `D095`, `D092`, `D094`, the
unbound dispersion repair, the two test defects, `D078`. **Nothing there was touched this session.**

New, from `D141`, and **a lead rather than a result** — not preregistered, not tested, must not be
reported as a finding: the model is **more dispersed than the market yet less correlated with
outcomes** (sd 4.706 vs 4.297; corr 0.4474 vs 0.5450), and the univariate slope of `pts` on F1 is
**0.7027**, CI [0.6031, 0.7819], **excluding 1.0**. The model's forecasts want shrinking ~30% toward
the mean — the signature of a forecast treating noise as signal.

Also from `D141`, cheap and useful: **the raw line is an adequate market estimate** for this market
at this snapshot regime (`corr(M1,M2) = 0.9964`; de-vig worth +0.0188 MAE, below materiality). The
de-vig machinery is not load-bearing and future screens need not treat it as such.

## 9.5 The scope this screen does NOT cover

It says nothing about the **~60% of played player-games books do not price** — silent on them *by
construction*, and that is where a model could still be worth something. It tests forecast accuracy
only: no bet selection, no staking, no decision rule. One season, one league, E1, single partition.
**It promotes nothing.**
