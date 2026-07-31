# FREEZE PROPOSAL v0 — starting the regime-D prospective clock

*Drafted 2026-07-30 late evening for John's sign-off. Nothing here is active until approved:
the forecast job's guard hard-refuses any non-scratch log path, and the real chain file
(`forecasts/forecast_log.jsonl`) does not exist. Per ROADMAP regime D, the FIRST REAL RECORD
is the official prospective start — an explicit act, taken once, on your word.*

## Why now

Tonight's evidence (all on the ledger):

- At near-tip timing the current model has **no cover edge** (`dist_margin_cover_v1`:
  cover Brier 0.2602 vs coin 0.2500 vs market 0.2498).
- At **T−24h** the model is statistically **at the market in 2026** (`clv_transfer_v1`:
  gap +0.116, CI [−0.54, +0.29]), and the small-disagreement flat-stake cell shows
  ROI +6.4% (262 bets, CI [−2.0%, +14.4%]) — **in-sample and unproven**.
- The market's T−24h line is as accurate as its close, so early timing is a fair arena,
  and it is the only arena where an edge is still plausible for this model.

Only immutable, timestamped, prospective predictions can confirm or kill that cell. Every
week the clock isn't running is evidence not accumulating. Capture began 2026-07-30;
prospective evaluation begins only with the freeze.

## What freezes (v0 composition)

| Component | Source | Frozen state |
|---|---|---|
| Margin/score/total point forecast | structural channel chains + train-only calibrations (`chanreval_2026_structural_repaired`, promoted) | code + calibration params at the freeze commit |
| Margin distribution | Gaussian, sigma = 12.9022 (`dist_margin_cover_v1`: empirical quantiles add nothing) | constant |
| Cover probability | P(margin > −spread) under that Gaussian at the consensus line at cutoff | formula |
| Availability layer | captured injury designations: Out ⇒ excluded (rule gate); Stage-A p_plays + EWMA α=0.30 minutes as informational columns | code at freeze commit |
| Data dependency | `daily_refresh.py` chain (collect → masters → channel_base → certify), scheduled 08:30 daily (`WNBA_DailyRefresh`, created 2026-07-30) | operational, running |
| Explicitly null in v0 | W1 news features · predicted close · any bet execution | logged as null, never imputed |

Freeze mechanics: tag the freeze commit (`freeze-v0`), record the commit hash + calibration
hashes in the regime-D registration, and log both hashes on every forecast record (the job
already does).

## The preregistered prospective protocol (registered at freeze time, before record #1)

- **Cutoffs:** two fixed daily runs — 10:00 ET (≈T−24h for next-day games, T−8/10h for
  same-day evening games; each record carries its exact per-game cutoff label) and 18:30 ET
  (≈T−90m for evening tips). Per-game dispatching is a documented v1 upgrade.
- **Logged per game per cutoff:** model/version hash, data snapshot hash, score/margin/total
  point forecasts, Gaussian cover probability, market consensus line + best-executable price
  at cutoff, availability columns, all provenance fields. Core-only now; core+W1 rides along
  when W1 features exist (same games, cleanest incremental measurement per ROADMAP).
- **Paper-trade policy cells (flat stake, logged decision at cutoff, never executed):**
  T−24h-labeled records, thresholds |model − line| ≥ 0.5 and ≥ 1.0, at −110 and at
  best-executable. Graded on: ROI, CLV vs latest pre-tip line, hit rate.
- **Sample-defined verdict bars (no calendar promises, per ROADMAP):** no verdict of any
  kind is read before ALL of: ≥ 300 logged game-forecasts at T−24h; ≥ 150 policy bets in
  the 0.5-threshold cell; 90% CI width on that cell's ROI ≤ 12 percentage points;
  cover-probability reliability weighted |gap| ≤ 0.05 on logged forecasts. Interim numbers
  are never quoted outside the log.
- **Failure discipline:** masters stale > 2 days ⇒ the job refuses to log (explicit
  degradation, already implemented). Missed days are missed — never backfilled into the
  chain.

## Go-live steps (one session, ~30 minutes, after your yes)

1. Tag freeze commit; register the regime-D experiment (id `prospective_v0`, regime D,
   this protocol verbatim in `extra`).
2. Flip `daily_forecast.py` to the real chain path (one guarded constant).
3. Create `WNBA_DailyForecast_AM` (10:00) and `_PM` (18:30) scheduled tasks.
4. First record lands ⇒ prospective start; handoff and ROADMAP annotated with the date.

## Rollback / supersession

Tasks delete cleanly (`schtasks /delete`). The chain is append-only: a broken v0 is
superseded by a v1 freeze and a new registration — records are never rewritten. Costs:
none beyond existing captures (the odds-tier decision at ~Aug 30 is independent).

## The ask

Reply "freeze v0 approved" (or amendments). Until then nothing logs to the real chain.
