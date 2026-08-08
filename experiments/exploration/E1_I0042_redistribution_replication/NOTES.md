# E1_I0042 — working notes

Preregistration `33135817779e66637ac68e3da2baa590dcb2be224f34c8a3332a159bb17c68d1`, 15,833 bytes,
14 cells fixed before anything was measured. **0 dropped. 3 added after the hash**, all labelled in
place: one allowlist correction (DEFECTS DEF-1), five extra anchors on E1_I0034's mechanism table
(§s4, they reproduced), and the D101-clean gate sweep (§s4.5, it weakened the operational
prescription). Every addition is stated with the direction it moved the headline.

---

## Order of operations, and why it was that order

1. **`s00_probe.py` before the hash.** Column names, season coverage, row and team-game counts,
   finite/zero counts. No cell evaluated, no arm compared, no response differenced. It exists so
   the preregistration's allowlists could be written **explicitly by name**. Declared in PREREG s0.
2. **`s01_windows.py`** — the window census, from the champion's own fold receipts. Run before any
   frame was loaded, because if the answer had been "zero clean windows" nothing else was worth
   doing.
3. **`s02`** — the decision-stratum intersection **first**, then all 23 reproduction anchors. The
   screen halts on any anchor failure; three drafts halted (DEF-2, DEF-3, and the DEF-1
   `KeyError`).
4. **`s03`–`s06`** — cells, threshold, specification, power.
5. **`s07`** — assembly only; nothing new measured except one carried rescale, labelled.

## The one thing that changed how I read every prior number in this programme

**`wf_shared` moves rows it does not treat, by up to 0.42 minutes.** Every arm in E1_I0034 and
E1_I0039 refits a walk-forward intercept jointly with the candidate's slopes, so the candidate's
presence changes the global calibration and therefore every row's forecast — including rows where
its own regressor is identically zero.

E1_I0039 found this and quantified it for A and B. What it could not see is that its own "frozen"
construction (base off the treated rows, full arm on them) leaves the recalibration **inside** the
treated-row forecast, which is where every headline in that screen lives.

A true freeze — hold `b(S)`, fit the slopes with no intercept on the residual about it — makes the
arm **bit-identical** to the base wherever `u = 0`. That single change:

* turned E1_I0039's "below the threshold the treatment is actively harmful, −0.0230, p 0.0003"
  into **exactly 0.0000**;
* turned C's pooled points figure from **+0.0012** into **−0.0161**;
* revealed that swapping in A and B is "worth" **+0.0287 at p 0.00005** on 1,051 rows where they
  substitute **nothing**, clearing both floors;
* and left C's own commercial number **larger**, +0.0796 against +0.0760.

The last of those is the reason this screen did not kill component C. The first three are the
reason it downgraded almost everything around it.

## Why the threshold work had to use an ungated arm

The published C arm gates its regressors at `freed ≥ 25`. Below the gate `u` is identically zero.
**A gated arm cannot produce a below-threshold treatment effect, only a below-threshold
recalibration artefact.** Every "the threshold has teeth in both directions" statement in the
literature this screen inherited was measured on a gated arm. The ungated frozen arm is the only
construction in which the sentence is even testable, and in it the effect is positive at every
level of freed minutes.

Two separate things are being called "the threshold" and they are not the same object:

* **the mechanism threshold** — where slack actually opens in the 200-minute budget. **Real.**
  Reproduces on 20 of 20 published figures. Slack is −1.5 at 15–30 minutes and +8.6 at 30–45.
* **the forecasting threshold** — a level below which applying the term hurts. **Does not exist.**
  On one fixed row set the ungated arm beats all eleven gates.

The mechanism being real does not imply the rule is. E1_I0034 §6 called the rule "the part of the
result with the largest effect size"; on this window it costs 13% of the gain.

## What I would tell the next screen to do

1. **Re-run the whole stacking lattice under a true frozen intercept.** E1_I0039's twenty
   decision-stratum cells were measured through a channel that manufactures a floor-clearing effect
   on rows a component does not touch. That is not a criticism of E1_I0039's care — it disclosed
   the channel — but the correction it applied was not strong enough, and the size of the artefact
   (+0.0287, 36% of the real effect) is large enough to matter.
2. **Stop reporting the analytic floor without a measured one.** This screen's own injection put
   the minutes floor at **1.88× the analytic rule**, exceeding D116's carried 1.22×. Three cells
   here would read decided on the analytic rule and none do on the measured one.
3. **Do not treat the 2023/2024 split as a replication.** It is the strongest test available and it
   is still one window. If the programme wants a replication of this candidate it needs either the
   sealed holdout — which is a confirmation decision, not a screening one — or more data.
4. **If C is ever authorised, authorise it ungated and untilted.** The two best-performing arms in
   the entire lattice are the ones that drop the threshold (+0.0414 vs +0.0360) and drop the tilt
   term (+0.1220 vs +0.0796). Neither is established, and neither should be enacted on this
   evidence — but the published specification is not the best available one, and that is a
   preregistered comparison on identical rows, not a fishing result.

## Numbers I checked and did not use

* `n_rem` ranges 5–12 with median 9; `u_minutes` is 0 on 4,808 of 14,826 REM rows. The allocation
  denominators are sane and no team-game divides by a near-zero.
* The EVEN and PROPORTIONAL allocations distribute the **same total** per treated team-game —
  max |Σ even − Σ prop| = **1.4e-14**. The comparison in VERDICT §6 is a comparison of *shape*
  only, which is what claim 2 is about.
* 2023 has 1,452 C-treated rows against 2024's 1,023 — a 42% difference between two seasons of
  480 team-games each. Worth someone's attention as an absence-recording artefact; not this
  screen's question, and not used to weight anything.

## Housekeeping

* **Processes launched: python, foreground only, one at a time, each exiting before the next
  began. No background job was started and nothing was killed.** No `Stop-Process`, no `taskkill`,
  no process enumeration of any kind was run at any point.
* **Nothing outside `experiments/exploration/E1_I0042_redistribution_replication/` was written,
  staged or committed.** No `git` command was run. The shared `_screen_kit` was **not imported and
  not modified** — this screen carries its own machinery in `scripts/rr_base.py`.
* **2025 and 2026 were never read.** Both sealed fold receipts exist on disk; `s01` lists them by
  name and skips them. A value-level partition guard runs on every frame at every load and raises
  on any sealed season value.
* `s06` and `s07` return exit 255 when piped through `Tee-Object` and exit 0 without it; all
  artefacts verified individually on disk. See DEFECTS DEF-9.
