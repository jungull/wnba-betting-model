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

## 2. YOU MAY HAVE BEEN SUMMONED BY A BUG (`D135` §2)

`wnba-coordinator-06` carries **`enabled: false`** and a **one-time `fireAt` of 2026-08-08T01:34Z
that had already fired**, yet its `lastRunAt` is 2026-08-17T13:08Z. A spent, disabled, one-time task
re-fired seven days late. All five coordinator tasks are confirmed disabled, so `D070` was never
violated by a coordinator — **the scheduler ignored it.**

**This can recur at any moment and can put two coordinators on one branch** — the exact collision the
staleness guard exists to prevent. Apply the staleness guard strictly: read the last line of
`GRAPH_EVENTS.jsonl`, and if it is under 30 minutes old and is not a `coordinator_retired` event,
append one `note` and stop.

## 3. STATE

* **135 decisions**, **520 events**, graph unchanged at **104 nodes** — 86 PASSED, 1 HALTED, 2 READY
  (parked), 3 USER_REQUIRED, 6 BLOCKED, 6 SUPERSEDED. Discovery work creates no graph nodes by design.
* Recovery commit `4f6d4d5` (D123–D134 + `E1_I0043..E1_I0056`, 1252 files) is **pushed**; repository
  gate **PASS 35/35**. `D135` is commit `3c68014`.
* **Both ledgers were verified as pure appends on bytes before committing** — HEAD's copy is a
  byte-identical prefix of the working copy. Do this before trusting any recovered ledger.

## 4. IN FLIGHT

| directory | state |
|---|---|
| `E1_I0056_minutes_variance` | **AGENT LIVE at time of writing.** Write scope is that directory only. **DO NOT RE-DISPATCH — check for `FINDINGS.json`, `PREREG.md` and `run_log_s*.txt` first.** |

If that agent died, its `s00` output is still trustworthy (log ends `DONE s00`, empty stderr) and
`s00` deliberately runs *before* the PREREG is written. Resume from the preregistration.

## 5. THE TWO READY NODES ARE CORRECTLY PARKED

`M08_STALE_WINDOW` and `M22_CAPACITY` compute as READY because their dependencies are satisfied, but
both are **prospective market measurements** requiring live multi-book capture tape that a clean
checkout cannot supply — the pre-push gate says so itself ("operational certification: run it on the
capture machine"). `M08`'s own `epistemic_status` is decisive: a stale window exists only where a
fresher quote was *demonstrably capturable* at time T. **Do not dispatch these here.**

## 6. WAITING ON THE USER — DO NOT SELF-GRANT

1. **`D067` / `N1`** — the halted score lane. Fitting remains **unauthorised**.
2. **`D095`** — the measurement regime boundary coincides with the exploration/confirmation partition
   boundary; **no E2 may start** until ruled on. Costs nothing; nothing is ready for promotion.
3. **`D078`** — M13/M14 calibration defect; measured and immaterial, annotate + fix-forward.
4. **Two validated production changes await authorisation**: cold-start tiering (`D092`) and fallback
   routing (`D094`).
5. **NEW — the scheduler defect in §2.** The user must decide whether to delete the spent coordinator
   tasks or re-enable a controlled one.

## 7. THE SCIENCE, AND THE ONE OPEN THREAD

Single-game scoring **efficiency is not forecastable from pre-game state** (`D081`, `D084`, `D085`,
`D087`). Minutes is a **powered, honest null** on the mean (`D133`) — rest, density, pace, foul
history and starter transitions are all dead where it matters, and the pre-game projection gain that
was briefly reported was an **overtime oracle** worth −0.000061 on regulation games. The largest
apparent positive the program ever produced — sixteen family-wise survivors — **closed as a volume
tautology** (`D134`): twelve had an exact algebraic identity behind them, and none improved points.

**The one live thread is variance, and only on minutes** (`D134`): predicted-error forecasts are well
calibrated (decile ratio 1.91, slope 1.01, OOF R² +0.043 on minutes) but **trailing level alone
matches them on points and beats them on attempts**, so only minutes carries genuine non-level
signal. **The incumbent variance model in the codebase has a NEGATIVE out-of-fold R².**
`E1_I0056`'s `s00` already recorded a candidate mechanism: `_SEASON_CONSTANCY.csv` marks
`minutes__pred_sd`, `pts__pred_sd`, `fga__pred_sd` and `minutes__pred_iqr` as **season-constant —
one distinct value per season**, i.e. carrying zero per-row information. That is what `E1_I0056` was
resumed to confirm or refute. **The reference to beat is trailing level, not the shipped column.**

## 8. THE HABIT THAT MATTERED MOST

**Verify agent claims on bytes, and read the construction rather than the label.** The recurring
failure in this program is not agents being wrong — it is **the coordinator restating an agent's
finding slightly stronger than the agent stated it** (`D133` records three such errors in one
family). Agents have caught coordinator errors repeatedly, including a briefing that misquoted its
own ledger. A powered honest null is a real result; an underpowered one is not a finding at all.
