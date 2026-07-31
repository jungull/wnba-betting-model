"""bios_screen.py — RUN 2 of the preregistered pooled screen
player_feature_screen_v1: the COLLECT-S bios / city / tip-time tier
(catalog #7, 9, 10, 27, 28, 29, 30, 31, 33, 80, 86).

A thin runner over feature_lab.py's committed machinery — the universe,
baseline tuning, ridge scoring, alpha-sweep engine, permutation null, and
robustness rerun are IMPORTED from feature_lab (protocol-identical to run 1
by construction). Differences from run 1, all preregistration-compliant:

  * the battery is features/bios_features.CANDIDATES (11 candidates, 41
    candidate-x-channel tests) — the COLLECT-S tier that became buildable
    when the bios pull landed;
  * Benjamini-Hochberg at 10% runs ACROSS THIS RUN'S BATTERY as its own
    family (labeled run 2), per the assignment;
  * artifacts go to experiments/feature_screen_run2/ ONLY — run 1's
    experiments/feature_screen/ is never written;
  * a coverage-accounting table is added (tip times exist for 2022+ only;
    bios null-height/weight/draft rows stay NaN — never imputed).

QUARANTINE IS ABSOLUTE: screening window 2021-2024; every assembled matrix
asserts max(game_date) < 2025-01-01 (audit trail in quarantine_audit.json).
This script records NOTHING on the ledger: it never imports or calls
registry.register / evaluate / record_evaluation, never runs git, and never
touches experiments/registry.jsonl or leaderboards/. The orchestrator records
after verifying.

Run:  python bios_screen.py                 # full run-2 screen (200 perms)
      python bios_screen.py --perms 30 --limit 3   # dev smoke only
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from feature_lab import (ALPHA_GRID, FDR_Q, MIN_MINUTES, MIN_MINUTES_ROBUST,  # noqa: E402
                         MIN_PRIOR_APPS, N_PERM_DEFAULT, RIDGE_LAMBDA,
                         bh_adjust, build_universe, eval_candidate, mae,
                         ridge_fit, ridge_predict, tune_baselines)
from features import CHANNELS, Ctx  # noqa: E402
from features.common import QUARANTINE_CUTOFF, TRAIN_SEASONS, VAL_SEASON, assert_quarantine  # noqa: E402
from features import bios_features as BF  # noqa: E402  (NOT part of run 1's ALL_CANDIDATES)

RUN2_CANDIDATES = BF.CANDIDATES
BATTERY = "player_feature_screen_v1 / run 2 (COLLECT-S bios-city-tip tier)"

OUTDIR = REPO / "experiments" / "feature_screen_run2"
DIAG = OUTDIR / "diagnostics"
RUN1_DIR = REPO / "experiments" / "feature_screen"   # read-only reference


def make_arrays(ctx: Ctx, Ux: pd.DataFrame) -> dict:
    """Target/baseline arrays per channel on a universe (reimplementation of
    the identically-named closure inside feature_lab.main, which is not
    importable; byte-for-byte the same logic)."""
    assert_quarantine(Ux["game_date"], f"design_matrix(n={len(Ux)})", ctx.audit)
    out = {}
    for ch in CHANNELS:
        out[ch] = {
            "y": Ux[f"y_{ch}"].to_numpy(float),
            "b": ctx.baselines[ch].loc[Ux.index].to_numpy(float),
            "season": Ux["season"].to_numpy(int),
        }
        nb = np.isnan(out[ch]["b"])
        if nb.any():
            raise RuntimeError(f"{int(nb.sum())} NaN baseline values on {ch}")
    return out


def representative_param(cand):
    """A parameter whose build has the same NaN footprint as any other (all
    run-2 NaN patterns come from trait/tip coverage, not the swept value)."""
    if cand.alpha_swept:
        return (cand.sweep_grid or ALPHA_GRID)[0]
    return None


def coverage_accounting(ctx: Ctx, U: pd.DataFrame, cands) -> pd.DataFrame:
    """Per (candidate, channel, season): share of universe rows with a
    DEFINED (non-NaN) feature value — the honest coverage ledger for the
    tip-time 2022+ restriction and the bios null rows."""
    rows = []
    for cand in cands:
        built = cand.build(ctx, representative_param(cand))
        for ch in cand.channels:
            s = built[ch] if isinstance(built, dict) else built
            x = s.loc[U.index]
            for season, sub in U.groupby("season"):
                xs = x.loc[sub.index]
                rows.append({
                    "catalog_number": cand.num, "name": cand.name, "channel": ch,
                    "season": int(season), "n_universe_rows": int(len(sub)),
                    "n_defined": int(xs.notna().sum()),
                    "defined_share": round(float(xs.notna().mean()), 4),
                })
    return pd.DataFrame(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--perms", type=int, default=N_PERM_DEFAULT,
                    help="permutations per test (protocol: 200)")
    ap.add_argument("--limit", type=int, default=None,
                    help="DEV ONLY: screen only the first N candidates")
    args = ap.parse_args(argv)

    t_start = time.time()
    OUTDIR.mkdir(parents=True, exist_ok=True)
    DIAG.mkdir(parents=True, exist_ok=True)

    print("[run2] battery:", BATTERY)
    print("[load] building context (quarantine-filtered at source) ...")
    ctx = Ctx()
    U, outer, folds = build_universe(ctx)
    print(f"[universe] {len(U)} target rows (min>={MIN_MINUTES:g}, "
          f">={MIN_PRIOR_APPS} prior apps); train={len(outer.train_idx)}, "
          f"val2024={len(outer.test_idx)}")

    print("[baseline] tuning per-channel EWMA alpha on inner folds ...")
    chosen, base_curves = tune_baselines(ctx, U, outer, folds)
    print(f"[baseline] frozen alphas: {chosen}")

    U15 = U[U["minutes"] >= MIN_MINUTES_ROBUST].copy()
    arr = make_arrays(ctx, U)
    arr15 = make_arrays(ctx, U15)

    # baseline reference MAEs for the report (identical computation to run 1)
    tr_pos = U.index.get_indexer(outer.train_idx)
    va_pos = U.index.get_indexer(outer.test_idx)
    base_ref = {}
    for ch in CHANNELS:
        A = arr[ch]
        raw = mae(A["y"][va_pos], A["b"][va_pos])
        mb, sb = float(np.mean(A["b"][tr_pos])), float(np.std(A["b"][tr_pos]))
        beta0 = ridge_fit(((A["b"][tr_pos] - mb) / sb)[:, None], A["y"][tr_pos])
        rid = mae(A["y"][va_pos], ridge_predict(((A["b"][va_pos] - mb) / sb)[:, None], beta0))
        base_ref[ch] = {"alpha": chosen[ch], "mae_raw_ewma_2024": round(raw, 5),
                        "mae_ridge_base_2024": round(rid, 5)}
        print(f"[baseline] {ch}: alpha={chosen[ch]} raw2024={raw:.4f} ridge2024={rid:.4f}")

    cands = RUN2_CANDIDATES[: args.limit] if args.limit else RUN2_CANDIDATES
    print(f"[screen] {len(cands)} candidates, {args.perms} permutations per test")

    all_rows, all_robust, all_alpha, all_diag = [], [], [], {}
    for i, cand in enumerate(cands, 1):
        try:
            rows, rob, arows, diag, dt = eval_candidate(
                ctx, cand, U, U15, outer, folds, args.perms, arr, arr15)
        except Exception as e:  # a candidate must never sink the screen
            print(f"  !! #{cand.num} {cand.name} FAILED: {type(e).__name__}: {e}")
            rows = [{"catalog_number": cand.num, "name": cand.name,
                     "family": cand.family, "channel": ch, "alpha_chosen": None,
                     "n_train": 0, "n_val": 0, "nan_share": 1.0,
                     "mae_base_ridge_2024": np.nan, "mae_feat_2024": np.nan,
                     "delta_mae": np.nan, "improvement": np.nan,
                     "beta_feature_std": np.nan, "fold_deltas": "",
                     "fold_signs": "", "sign_2024": "", "sign_consistent": False,
                     "p_value": 1.0, "degenerate": True,
                     "note": f"BUILD FAILED: {type(e).__name__}: {e}"}
                    for ch in cand.channels]
            rob, arows, diag, dt = [], [], {}, 0.0
        all_rows += rows
        all_robust += rob
        all_alpha += arows
        all_diag[cand.num] = diag
        best = min(rows, key=lambda r: r["p_value"])
        print(f"  [{i:>2}/{len(cands)}] #{cand.num:<3} {cand.name:<28} "
              f"best p={best['p_value']:.3f} delta={best['delta_mae']} "
              f"ch={best['channel']} ({dt:.1f}s)")

    res = pd.DataFrame(all_rows)
    # BH ACROSS THIS RUN'S BATTERY ONLY (its own family, labeled run 2)
    res["q_value"] = bh_adjust(res["p_value"].to_numpy(float))
    res["bh_pass"] = res["q_value"] <= FDR_Q
    res["survives"] = res["bh_pass"] & res["sign_consistent"]
    res = res.sort_values(["survives", "q_value", "delta_mae"],
                          ascending=[False, True, True]).reset_index(drop=True)
    res.to_csv(OUTDIR / "screen_results.csv", index=False)

    rob = pd.DataFrame(all_robust)
    rob.to_csv(OUTDIR / "robustness_min15.csv", index=False)
    pd.DataFrame(all_alpha).to_csv(OUTDIR / "alpha_curves.csv", index=False)
    base_curves.to_csv(OUTDIR / "baseline_alpha_curves.csv", index=False)

    surv = res[res["survives"]].copy()
    if len(surv) and len(rob):
        surv = surv.merge(rob[["catalog_number", "channel", "delta_mae_min15",
                               "sign_min15"]], on=["catalog_number", "channel"],
                          how="left")
    else:  # keep run 1's full survivor schema even when empty
        surv = surv.reindex(columns=list(surv.columns)
                            + ["delta_mae_min15", "sign_min15"])
    surv.to_csv(OUTDIR / "survivor_summary.csv", index=False)

    # top-20 diagnostics with null quantiles (same shape as run 1)
    top = res.head(20).copy()
    drows = []
    for _, r in top.iterrows():
        d = all_diag.get(r["catalog_number"], {}).get(r["channel"], {})
        drows.append({**r.to_dict(), **d})
    pd.DataFrame(drows).to_csv(DIAG / "top20_diagnostics.csv", index=False)

    # coverage accounting (tip 2022+ restriction, bios nulls)
    cov = coverage_accounting(ctx, U, cands)
    cov.to_csv(OUTDIR / "coverage_accounting.csv", index=False)
    tipinfo = BF.tip_local(ctx)

    with open(OUTDIR / "quarantine_audit.json", "w") as f:
        json.dump({"battery": BATTERY,
                   "cutoff": str(QUARANTINE_CUTOFF.date()),
                   "all_pass": all(a["pass"] for a in ctx.audit),
                   "matrices": ctx.audit}, f, indent=2)

    write_report(res, rob, surv, cov, tipinfo, base_ref, chosen, args, ctx,
                 time.time() - t_start, len(cands))
    n_tests = len(res)
    print(f"\n[done] {n_tests} tests, {int(res['survives'].sum())} survivors "
          f"({int(res['bh_pass'].sum())} BH-pass), "
          f"expected false at q<={FDR_Q}: ~{FDR_Q * int(res['bh_pass'].sum()):.1f}; "
          f"runtime {time.time() - t_start:.0f}s")
    return 0


def write_report(res, rob, surv, cov, tipinfo, base_ref, chosen, args, ctx,
                 runtime, n_cands):
    n_tests = len(res)
    n_bh = int(res["bh_pass"].sum())
    n_surv = int(res["survives"].sum())
    n_p05 = int((res["p_value"] <= 0.05).sum())
    hist, _ = np.histogram(res["p_value"].dropna(), bins=np.arange(0, 1.05, 0.05))
    lines = []
    A = lines.append
    A("# player_feature_screen_v1 — RUN 2 (COLLECT-S bios / city / tip-time tier)")
    A("")
    A(f"*Generated by bios_screen.py; runtime {runtime:.0f}s; {args.perms} "
      f"permutations per test; ridge lambda={RIDGE_LAMBDA} on standardized "
      "inputs. Protocol machinery imported unchanged from feature_lab.py "
      "(run 1); battery = features/bios_features.py.*")
    A("")
    A("## Protocol (as registered; run-2 specifics documented below)")
    A("")
    A("- Screening window 2021-2024 ONLY; quarantine asserted on every matrix "
      "(`quarantine_audit.json`, all-pass="
      f"{all(a['pass'] for a in ctx.audit)}, {len(ctx.audit)} matrices). The "
      "tip-times and bios tables are filtered to season<=2024 at read; "
      "2025/2026 rows never enter memory.")
    A("- Targets, universe, baseline, ridge, alpha-sweep engine, permutation "
      "null, BH+sign-consistency survival rule, and the >=15-minute "
      "robustness rerun: identical to run 1 (see "
      "experiments/feature_screen/REPORT.md). Frozen baseline alphas this "
      f"run: {chosen} (same as run 1 — same code, same data).")
    A(f"- **False-discovery control: Benjamini-Hochberg at {FDR_Q:.0%} across "
      f"THIS RUN'S battery of {n_tests} (candidate x channel) tests — its own "
      "family, labeled run 2** (the assignment's multiplicity clause; run 1's "
      "256 tests were corrected within their own family the same way).")
    A("")
    A("## Baseline reference (2024)")
    A("")
    A("| channel | alpha | raw EWMA MAE | ridge-recalibrated MAE |")
    A("|---|---|---|---|")
    for ch, r in base_ref.items():
        A(f"| {ch} | {r['alpha']} | {r['mae_raw_ewma_2024']} | {r['mae_ridge_base_2024']} |")
    A("")
    A("## Headline")
    A("")
    A(f"- **{n_tests} tests** ({n_cands} candidates x relevant channels).")
    A(f"- **p<=0.05 before any correction: {n_p05}** (expected under a global "
      f"null: ~{0.05 * n_tests:.1f}).")
    A(f"- **BH({FDR_Q:.0%}) significant: {n_bh}**; with sign-consistency: "
      f"**{n_surv} survivors**.")
    A(f"- Expected false discoveries among BH-passers at q<={FDR_Q}: "
      f"~{FDR_Q * n_bh:.1f}.")
    A("")
    A("p-value histogram (bin width 0.05, left edge 0):")
    A("")
    A("```")
    A(" ".join(f"{int(h):>4}" for h in hist))
    A("```")
    A("")
    A("## Survivors")
    A("")
    if len(surv):
        A("| # | name | channel | delta | p | q | param | folds | min15 |")
        A("|---|---|---|---|---|---|---|---|---|")
        for _, r in surv.iterrows():
            m15 = r.get("delta_mae_min15", "")
            A(f"| {r['catalog_number']} | {r['name']} | {r['channel']} | "
              f"{r['delta_mae']:+.4f} | {r['p_value']:.4f} | {r['q_value']:.4f} | "
              f"{r['alpha_chosen']} | {r['fold_signs']} | {m15} |")
    else:
        A("**None.** The bios / city / tip-time tier did not beat the trend "
          "baseline plus multiplicity control AND the sign-consistency "
          "requirement on this window.")
    A("")
    A("## BH-passers that failed sign-consistency (not survivors; logged for the record)")
    A("")
    near = res[res["bh_pass"] & ~res["survives"]]
    if len(near):
        A("These cleared BH(10%) on the 2024 score but their improvement was "
          "NOT negative on all 3 inner folds — the preregistered survival rule "
          "excludes them, and that rule exists precisely to kill "
          "validation-year-only effects. Logged with their >=15-minute "
          "robustness sign for the confirmation experiment's context; they "
          "promote nothing.")
        A("")
        A("| # | name | channel | delta | p | q | folds | min15 delta | min15 agrees |")
        A("|---|---|---|---|---|---|---|---|---|")
        rk = rob.set_index(["catalog_number", "channel"]) if len(rob) else None
        for _, r in near.iterrows():
            m15d, m15a = "", ""
            if rk is not None and (r["catalog_number"], r["channel"]) in rk.index:
                rr = rk.loc[(r["catalog_number"], r["channel"])]
                m15d, m15a = rr["delta_mae_min15"], rr["agrees_with_primary"]
            A(f"| {r['catalog_number']} | {r['name']} | {r['channel']} | "
              f"{r['delta_mae']:+.4f} | {r['p_value']:.4f} | {r['q_value']:.4f} | "
              f"{r['fold_signs']} | {m15d} | {m15a} |")
    else:
        A("None.")
    A("")
    A("## Full battery results")
    A("")
    A("| # | name | channel | delta | p | q | sign-consistent | nan_share |")
    A("|---|---|---|---|---|---|---|---|")
    for _, r in res.iterrows():
        A(f"| {r['catalog_number']} | {r['name']} | {r['channel']} | "
          f"{r['delta_mae']} | {r['p_value']} | {r['q_value']:.4f} | "
          f"{r['sign_consistent']} | {r['nan_share']} |")
    A("")
    A("## Coverage accounting (preregistered honesty items)")
    A("")
    tip_by_season = (cov[cov["catalog_number"] == 10]
                     .groupby("season")[["n_universe_rows", "n_defined"]].sum())
    A("- **Tip times exist for 2022+ only** (2021 has no captured commence "
      "times). #10 rows without a captured tip are NaN — mean-filled at FIT "
      "time by the harness's documented NaN policy, never silently bucketed. "
      "Defined share of universe rows by season:")
    for season, r in tip_by_season.iterrows():
        A(f"  - {season}: {int(r['n_defined'])}/{int(r['n_universe_rows'])} "
          f"({r['n_defined'] / max(r['n_universe_rows'], 1):.1%})")
    A(f"- Tip table: {tipinfo['n_games']} screen-window games carry a captured "
      f"tip; local-hour recompute (tip_utc + team_cities timezone, zoneinfo) "
      f"vs the table's tip_hour_local: {tipinfo['n_mismatch']} mismatches.")
    A("- **Null-height player-seasons stay null** (never imputed). Both "
      "null-height bios rows (1630445/2021, 1643434/2026) belong to "
      "player-seasons with zero played regular-season rows, so the screen "
      "universe has 100% height/age coverage; weight is null for 15 in-window "
      "player-seasons (#31 NaN there) and experience/draft-year is undefined "
      "for undrafted players (#29/#30 NaN there). Per-candidate, per-season "
      "defined shares: `coverage_accounting.csv`.")
    A("- Feature NaNs are mean-filled with FIT-window means at fit time "
      "(fold-train means inside folds) — feature encoding, not raw-data "
      "imputation; `nan_share` in screen_results.csv reports every share.")
    A("")
    A("## Run-2 interpretation decisions (pinned before results were seen)")
    A("")
    A("- **No double-claiming**: #7, #28, #29, #31, #33, #80 are inherently "
      "interactions; here each enters as the honest POOLED encoding — one "
      "centered product column. The moderator-permutation interaction test "
      "for each lives in the separately registered "
      "player_feature_interactions_v1 protocol. A pooled row here claims "
      "nothing about moderation.")
    A("- **A-priori centering constants** (round numbers near league center, "
      "fixed before any statistic was computed): AGE_REF=27.0, H_REF=72.5 in, "
      "W_REF=170 lbs, EXP_REF=5 yrs, UNDRAFTED_PICK=40, low-experience gate "
      "<=2 yrs, afternoon = local tip < 17.0 (run 1's cutoff).")
    A("- **#10 is a re-test with a better source**: run 1 screened #10 from "
      "the PBP wall-clock ET proxy with unknown tips silently classed "
      "'evening'; run 2 uses captured local tip times (the catalog's intended "
      "source) with honest NaN coverage. Same personal aft/eve surprise "
      "encoding (k=10, personalized-only). Both results stand in their own "
      "batteries; the confirmation experiment arbitrates.")
    A("- **#9 vs #33**: #9 is the raw haversine distance (main effect); the "
      "catalog's 'x age' note is realized by #33 as the centered product — "
      "not duplicated inside #9.")
    A("- **#27 sweeps its peak age** (22..34) through the harness's inner-fold "
      "sweep engine (the committed #92 blend-weight precedent); "
      "-(age-peak)^2 carries both linear and quadratic age terms in one "
      "column, peak frozen per channel before 2024 is touched.")
    A("- **B2B is the player-level flag** (own previous played game yesterday) "
      "— the same rest basis as run 1's #6; a player who sat yesterday is "
      "not on a back-to-back.")
    A("- **Schedule facts** (B2B, travel, tip hour, elevation) attach "
      "unshifted; trend components (#28/#29 volatilities, #80 load) are "
      "strictly-prior via run 1's sroll/#79 machinery; traits are static per "
      "(player, season).")
    A("- **Known limitation** (inherited from run 1): row-exchangeable "
      "permutation understates within-player clustering of slow-moving "
      "features — trait products (#27-#31 style) are exactly that shape, so "
      "their p-values are honest against the registered null but the "
      "2025-2026 confirmation is the real gate.")
    A("")
    A("## The fun ones (elevation / tip hour / travel), regardless of survival")
    A("")
    fun = res[res["catalog_number"].isin([9, 10, 33, 86])]
    A("| # | name | channel | delta | p | q | survives |")
    A("|---|---|---|---|---|---|---|")
    for _, r in fun.iterrows():
        A(f"| {r['catalog_number']} | {r['name']} | {r['channel']} | "
          f"{r['delta_mae']} | {r['p_value']} | {r['q_value']:.4f} | {r['survives']} |")
    A("")
    A("## Failed builds")
    A("")
    failed = res[res["note"].astype(str).str.startswith("BUILD FAILED")]
    if len(failed):
        for _, r in failed.drop_duplicates("catalog_number").iterrows():
            A(f"- #{r['catalog_number']} {r['name']}: {r['note']}")
    else:
        A("None.")
    A("")
    A("## Files")
    A("")
    A("- `screen_results.csv` — one row per (candidate, channel); run-1 schema")
    A("- `survivor_summary.csv` — survivors only (+ min15 robustness)")
    A("- `robustness_min15.csv` — full >=15-minute rerun (frozen params)")
    A("- `alpha_curves.csv`, `baseline_alpha_curves.csv` — inner-fold sweeps")
    A("- `coverage_accounting.csv` — per (candidate, channel, season) defined share")
    A("- `diagnostics/top20_diagnostics.csv` — null quantiles for the top 20")
    A("- `quarantine_audit.json` — per-matrix date audit")
    (OUTDIR / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
