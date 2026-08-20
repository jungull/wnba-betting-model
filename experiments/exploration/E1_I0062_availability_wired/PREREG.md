# E1_I0062 — wire the good availability model into the minutes forecast

Frozen after the join's **shape** was printed and before any score existed. Known at freezing:
14,299 usable rows, 222 players, seasons 2022–2024, appeared rate 0.8575, `v15 p_active` mean
0.8141 sd 0.2382, crude prior-rate mean 0.8713 sd 0.2026, correlation between the two 0.7782,
fallback rate 0.0000. No Brier, CRPS or calibration statistic had been computed.

**Partition: exploration only.** The availability frame carries seasons 2022–2024 (2021 is
degenerate in both arms and absent). 2025 and 2026 are never read, joined, plotted or
described.

---

## What this tests and why it is not the last screen's finding again

E1_I0061 established that adding **any** availability branch to a minutes forecast beats
having none — Brier on "more than 15 minutes" improved 11.5%. It used a deliberately crude
instrument: an EWMA of the player's own prior appearance rate. It then **recommended something
it had not tested**, namely wiring in the programme's good availability model.

That recommendation is the hypothesis here. E0_I0019 measured the shipped `v15 p_active` at
**Brier 0.092 / AUC 0.902** against the prior-rate family at **0.122 / 0.841**. The two
instruments correlate 0.7782 on this frame, so they are related but far from the same thing.

**The question is not whether availability matters — that is settled. It is how much of the
value comes from HAVING a branch versus from having a GOOD one.**

## Inherited assumption, stated as a dependency

`v15 p_active` is an out-of-fold prediction from the production arm. Its point-in-time
provenance is **inherited from E0_I0019**, which verified it with four leak probes, three of
which it had to withdraw and rebuild, reaching verdict ESTABLISHED. This screen does not
re-derive that. If E0_I0019's provenance verdict is ever overturned, every number here falls
with it.

## Arms, frozen

Identical minutes point forecast and identical played-branch distribution
(`A3_EMPIRICAL_COND` from E1_I0061) in every arm. Only the availability term varies.

| id | availability term |
|---|---|
| `N_NONE` | none — the played-branch distribution alone, i.e. assume the player plays |
| `W_CRUDE` | EWMA of the player's own prior appearance rate (what E1_I0061 used) |
| `G_GOOD` | `v15 p_active`, the shipped model E0_I0019 characterised |

Each mixture places an explicit point mass of `1 − p` at zero minutes.

## Metrics, frozen. PRIMARY is threshold Brier at t = 15.

- **PRIMARY**: Brier for `P(minutes > 15)` — the threshold E1_I0061 found availability
  dominates. Also reported at t ∈ {20, 25, 30, 35}.
- CRPS over the full dressed distribution, on the common 0.25-minute grid from E1_I0061.
- **Instrument quality**, reported separately so the two questions never blur: Brier and AUC
  of each availability term against `appeared` itself.
- Calibration of each availability term: 10-bin reliability and its mean absolute deviation.

Cluster bootstrap by **player-season**, 2,000 draws, seed 20260820.

## Predictions, committed before computing

- **P1** `G_GOOD` beats `W_CRUDE` on the primary. The better instrument wins.
- **P2** *(the sceptical one, and the reason this screen is interesting)* **Most of the value
  is in having a branch at all, not in its quality**: the gain of `W_CRUDE` over `N_NONE`
  exceeds the gain of `G_GOOD` over `W_CRUDE`, at t = 15.
- **P3** `G_GOOD` beats `W_CRUDE` on CRPS over dressed rows.
- **P4** For both `W` and `G`, the improvement over `N_NONE` shrinks monotonically as the
  threshold rises, reproducing E1_I0061's gradient.
- **P5** *(sanity)* `G_GOOD` is the better instrument on its own terms — lower Brier against
  `appeared` than `W_CRUDE`. If this fails, the join or the artifact is wrong and no other
  number here may be read.

## What would make this screen worthless

- **P5 failing.** That is a join or provenance failure, not a finding.
- **The point forecast and played branch are not re-tuned and are not the contribution.** Any
  difference between arms is the availability term alone, by construction.
- **`v15 p_active` is an out-of-fold production artifact, not a forecast this screen built.**
  It is being *consumed*. Its walk-forward discipline is E0_I0019's finding, not this one's.
- **Nothing here is a wager-shaped claim.** S42 stands. Threshold Brier is prop-shaped; that
  is not permission to price a prop.
- **`appeared` means appeared for the target team in the target box.** A player who is not on
  the roster at all never enters the frame, so every arm answers a conditional question and
  none of them answers "will this named player produce minutes tonight".
