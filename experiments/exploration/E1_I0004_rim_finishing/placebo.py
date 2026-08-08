"""E1 I0004 -- placebo / noise floor for the rim-finishing x rim-allowance lead.

THE SPECIFIC TRAP THIS SCRIPT DOCUMENTS
---------------------------------------
A negative control that permutes a GROUPING KEY and then RECOMPUTES the aggregate
from the permuted key is a NO-OP. A bijective relabelling of teams maps each
permuted cell onto exactly the same row set under a different name, so every row
still receives its own true value. It looks like a working placebo and tests
nothing. Diagnostic signature: it reproduces the real number EXACTLY, with
sd EXACTLY 0.000000.

This script runs that defective form ON PURPOSE (control D0) and shows the
signature, then shows the genuine controls (P1, P2) do not have it.

The correct form permutes the ASSIGNMENT OF AN ALREADY-COMPUTED VALUE TO ROWS.

Deterministic controls (C1, C2) have sd 0 BY CONSTRUCTION -- there is nothing
random in them -- and are labelled as such so they are never confused with D0's
defect signature.

PARTITION: seasons 2021-2024 only, inherited from ra_common_frame.parquet, which
is re-asserted on load (# FILTER-POINT) and again before every write.
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PARTITION = [2021, 2022, 2023, 2024]
N_DRAWS = 400
SEED = 20260807

frame = pd.read_parquet(os.path.join(HERE, "ra_common_frame.parquet"))
# FILTER-POINT 1: re-assert the exploration partition on load.
frame = frame[frame["season"].isin(PARTITION)].copy()
print(f"loaded ra_common_frame: {len(frame)} RA shots")
print(f"sorted(season.unique()) = {sorted(frame['season'].unique())}")
assert set(frame["season"].unique()) <= set(PARTITION), "PARTITION VIOLATION"

CELLS = {
    "headline_fully_pregame": ("resid_B1_own_rate_v2_split_alpha", "O2"),
    "e0_cell_retrospective": ("resid_B0_E0_leave_one_season_out", "O1"),
}


def stat(y, x):
    y = np.asarray(y, float)
    x = np.asarray(x, float)
    if np.nanstd(x) == 0:
        return dict(corr=np.nan, diff=np.nan, beta=np.nan)
    corr = float(np.corrcoef(y, x)[0, 1])
    med = np.median(x)
    hi = x > med
    diff = float(y[hi].mean() - y[~hi].mean())
    beta = float(np.polyfit(x, y, 1)[0])
    return dict(corr=corr, diff=diff, beta=beta)


def summarize(name, kind, draws, real, note, real_alt=None):
    d = {k: np.array([dd[k] for dd in draws], float) for k in ("corr", "diff", "beta")}
    out = dict(control=name, kind=kind, n_draws=len(draws), note=note, real=real)
    for k in ("corr", "diff", "beta"):
        v = d[k]
        out[k] = dict(real=real[k], mean=float(np.nanmean(v)), sd=float(np.nanstd(v, ddof=1)),
                      p05=float(np.nanpercentile(v, 5)), p95=float(np.nanpercentile(v, 95)),
                      frac_ge_real=float(np.mean(v >= real[k])),
                      max_abs_dev_from_real=float(np.nanmax(np.abs(v - real[k]))))
        if real_alt is not None:
            # Conservative cross-check: the permuted x is team-season-constant, so the
            # like-for-like real is the team-season-mean one. Score the ROW-LEVEL real
            # against the same null too, since that is the number actually reported.
            out[k]["real_rowlevel"] = real_alt[k]
            out[k]["frac_ge_real_rowlevel"] = float(np.mean(v >= real_alt[k]))
            out[k]["z_rowlevel"] = float((real_alt[k] - np.nanmean(v))
                                         / np.nanstd(v, ddof=1))
    return out


results = []
rng_master = np.random.default_rng(SEED)

for cell_name, (ycol, xcol) in CELLS.items():
    d = frame[[ycol, xcol, "OPP_TEAM_ID", "season", "GAME_ID"]].dropna().copy()
    real_row = stat(d[ycol], d[xcol])

    # Team-season mean of the already-computed allowance. The permutable object.
    tsv = d.groupby(["season", "OPP_TEAM_ID"])[xcol].mean().rename("v").reset_index()
    d = d.merge(tsv, on=["season", "OPP_TEAM_ID"], how="left")
    real_ts = stat(d[ycol], d["v"])

    print("\n" + "=" * 100)
    print(f"CELL {cell_name}:  y = {ycol}   x = {xcol}   n = {len(d)}")
    print("=" * 100)
    print(f"  REAL (row-level x)        : corr={real_row['corr']:+.6f}  "
          f"diff={real_row['diff']:+.6f}  beta={real_row['beta']:+.6f}")
    print(f"  REAL (team-season-mean x) : corr={real_ts['corr']:+.6f}  "
          f"diff={real_ts['diff']:+.6f}  beta={real_ts['beta']:+.6f}   "
          f"<- the comparator every permutation control below is scored against")

    # ------------------------------------------------------------------ D0: the defect
    # Permute the GROUPING KEY (a bijective relabel within season), then RECOMPUTE
    # the team-season aggregate from the permuted key and join back on it.
    rng = np.random.default_rng(SEED + 1)
    per_game = d.groupby(["season", "OPP_TEAM_ID", "GAME_ID"])[xcol].mean().reset_index()

    def d0_draw(maps):
        pgp = per_game.copy()
        pgp["key_perm"] = pgp["OPP_TEAM_ID"].map(maps)
        agg = pgp.groupby(["season", "key_perm"])[xcol].mean().rename("v_perm").reset_index()
        dd = d.copy()
        dd["key_perm"] = dd["OPP_TEAM_ID"].map(maps)
        dd = dd.merge(agg, on=["season", "key_perm"], how="left")
        return stat(dd[ycol], dd["v_perm"])

    # Reference: the SAME pipeline under the IDENTITY relabel. This is the "real"
    # number the defective control must reproduce; using real_ts here instead would
    # compare a per-game-mean aggregate against a per-row-mean one and hide the point.
    ident = {t: t for t in per_game["OPP_TEAM_ID"].unique()}
    real_d0 = d0_draw(ident)
    draws_d0 = []
    for _ in range(N_DRAWS):
        maps = {}
        for ssn, g in per_game.groupby("season"):
            teams = g["OPP_TEAM_ID"].unique()
            maps.update(dict(zip(teams, rng.permutation(teams))))
        draws_d0.append(d0_draw(maps))
    r = summarize("D0_permute_grouping_key_then_recompute_aggregate", "DEFECTIVE_NOOP",
                  draws_d0, real_d0,
                  "Run deliberately. A bijective relabel makes each permuted cell the "
                  "same row set renamed, so every row still gets its OWN true value. "
                  "Expected signature: every draw == the identity-relabel reference, "
                  "sd == 0.000000 exactly.")
    r["cell"] = cell_name
    r["reference"] = "identity relabel through the same recompute pipeline"
    results.append(r)
    print(f"\n  D0  DEFECTIVE NO-OP (run on purpose, {N_DRAWS} draws)")
    for k in ("corr", "diff", "beta"):
        print(f"      {k:<5} ref={r[k]['real']:+.6f}  mean={r[k]['mean']:+.6f}  "
              f"sd={r[k]['sd']:.10f}  max|dev from ref|={r[k]['max_abs_dev_from_real']:.2e}")
    # Criterion: EVERY draw is bit-identical to the reference (max dev exactly 0.0),
    # and sd is zero to float precision. np.nanstd's two-pass form leaves ~1e-17
    # rounding dust on a constant array, so the sd test carries a 1e-12 tolerance
    # while the "reproduces the real number" test is exact.
    sig = all(r[k]["max_abs_dev_from_real"] == 0.0 and r[k]["sd"] < 1e-12
              for k in ("corr", "diff", "beta"))
    print(f"      DEFECT SIGNATURE PRESENT (every draw bit-identical to the real "
          f"number; sd 0 to float precision): {sig}")
    print("      => this control tests NOTHING. It is shown to prove P1/P2 below are genuine.")
    r["defect_signature_confirmed"] = bool(sig)

    # ------------------------------------- P1: genuine -- permute value -> team assignment
    rng = np.random.default_rng(SEED + 2)
    draws_p1 = []
    for _ in range(N_DRAWS):
        remap = {}
        for ssn, g in tsv.groupby("season"):
            teams = g["OPP_TEAM_ID"].to_numpy()
            vals = g["v"].to_numpy()
            remap.update({(ssn, t): v for t, v in zip(teams, rng.permutation(vals))})
        vv = [remap[(ssn, t)] for ssn, t in zip(d["season"], d["OPP_TEAM_ID"])]
        draws_p1.append(stat(d[ycol], vv))
    r = summarize("P1_permute_computed_allowance_across_teams_within_season", "GENUINE",
                  draws_p1, real_ts,
                  "The correct form: the already-computed team-season allowance VALUES "
                  "are reshuffled across teams within season, then re-assigned to rows. "
                  "Preserves the marginal distribution and the clustered row structure; "
                  "destroys only the true team<->allowance pairing.", real_alt=real_row)
    r["cell"] = cell_name
    results.append(r)
    print(f"\n  P1  GENUINE placebo ({N_DRAWS} draws) -- permute computed value across teams")
    for k in ("corr", "diff", "beta"):
        print(f"      {k:<5} real={r[k]['real']:+.6f}  mean={r[k]['mean']:+.6f}  "
              f"sd={r[k]['sd']:.6f}  p05={r[k]['p05']:+.6f}  p95={r[k]['p95']:+.6f}  "
              f"frac_ge_real={r[k]['frac_ge_real']:.4f}   |  row-level real="
              f"{r[k]['real_rowlevel']:+.6f}  z={r[k]['z_rowlevel']:+.2f}  "
              f"frac_ge={r[k]['frac_ge_real_rowlevel']:.4f}")

    # ------------------------------------------- P2: genuine -- shuffle values across rows
    rng = np.random.default_rng(SEED + 3)
    draws_p2 = []
    xv = d["v"].to_numpy()
    ssn_arr = d["season"].to_numpy()
    for _ in range(N_DRAWS):
        vv = xv.copy()
        for ssn in PARTITION:
            m = ssn_arr == ssn
            vv[m] = rng.permutation(xv[m])
        draws_p2.append(stat(d[ycol], vv))
    r = summarize("P2_shuffle_computed_allowance_across_rows_within_season", "GENUINE",
                  draws_p2, real_ts,
                  "Also correct, but it additionally destroys the within-team clustering, "
                  "so its sd is an UNDERSTATED noise floor. Reported for contrast with P1; "
                  "P1 is the one to read.", real_alt=real_row)
    r["cell"] = cell_name
    results.append(r)
    print(f"\n  P2  GENUINE placebo ({N_DRAWS} draws) -- shuffle values across rows "
          f"(anti-conservative: destroys clustering)")
    for k in ("corr", "diff", "beta"):
        print(f"      {k:<5} real={r[k]['real']:+.6f}  mean={r[k]['mean']:+.6f}  "
              f"sd={r[k]['sd']:.6f}  frac_ge_real={r[k]['frac_ge_real']:.4f}   |  "
              f"row-level real={r[k]['real_rowlevel']:+.6f}  z={r[k]['z_rowlevel']:+.2f}  "
              f"frac_ge={r[k]['frac_ge_real_rowlevel']:.4f}")

# ------------------------------------------------------ deterministic controls (sd 0 by construction)
print("\n" + "=" * 100)
print("DETERMINISTIC CONTROLS -- sd is 0 BY CONSTRUCTION (nothing random in them).")
print("This is NOT the D0 defect signature; do not confuse the two.")
print("=" * 100)
det = []

# C1: opponent POOLED FG% allowed instead of the rim-specific residual.
for cn, (yc, _) in CELLS.items():
    dd = frame[[yc, "opp_pool_loo"]].dropna()
    st = stat(dd[yc], dd["opp_pool_loo"])
    det.append(dict(control="C1_opponent_pooled_fg_allowed_not_rim_specific", kind="DETERMINISTIC",
                    cell=cn, sd_note="sd 0 by construction", n=int(len(dd)), **st))
    print(f"  C1 {cn:<26} corr={st['corr']:+.6f}  diff={st['diff']:+.6f}  beta={st['beta']:+.6f}")

# C2: the same test in Above the Break 3 -- a zone E0 showed has NO real
# between-team dispersion in allowance. Rebuilt from the E0 reproduction path.
print("\n  C2 (Above the Break 3, no real opponent dispersion) is reported in "
      "run_log_01 section 1: corr=+0.0027 diff=+0.0033 se=0.0051 -- indistinguishable "
      "from zero, as a negative-zone control should be. Deterministic, sd 0 by construction.")
det.append(dict(control="C2_above_the_break_3_zone_no_real_dispersion", kind="DETERMINISTIC",
                cell="e0_cell_retrospective", sd_note="sd 0 by construction",
                n=34961, corr=0.0027, diff=0.0033, beta=None))

payload = dict(n_draws=N_DRAWS, seed=SEED, permutation_controls=results,
               deterministic_controls=det, seasons=PARTITION)
assert set(frame["season"].unique()) <= set(PARTITION), "PARTITION VIOLATION before write"
with open(os.path.join(HERE, "placebo_results.json"), "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2)
print(f"\nwrote placebo_results.json  (partition re-asserted: "
      f"{sorted(frame['season'].unique())})")
