"""
E1 I0012 -- TARGETED ROBUSTNESS RE-RUN of the single survivor of E0_I0012_layer3_noncollinear.

SURVIVOR: formulations[13] = F3_style_orthogonalized__dpace, target = rebounds.
  opponent pace (poss/48), prior-expanding within season, residualized on the opponent's
  overall pregame allowance AND on the base O*D term, then interacted with the player's own
  pregame rebound rate (O).

THE QUESTION: the pooled effect is carried by 2021-2022 and beta_OxM decays monotonically
  0.356 -> 0.335 -> 0.167 -> 0.064. Re-run with 2021 DROPPED ENTIRELY. If 2022-2024 still
  decays, the lead is dying on its own and should be abandoned WITHOUT touching the holdout.

STAGES:
  A  ANCHOR      2021-2024, exact E0 replication. Must reproduce pooled dR2_OxM = 0.001071.
  B  HEADLINE    2022-2024 only, dropped at the ANALYSIS stage (features built with 2021
                 present so 2022's prev-season shrinkage priors are byte-identical to E0;
                 only the analysis sample and the standardisation/residualisation change).
  C  VARIANT     2022-2024 only, dropped at the LOAD stage (2021 never read at all, so 2022
                 loses its prev-season prior and falls back). Robustness on stage B.
  D  TREND TEST  formal O x Mres x season-index triple interaction on 2022-2024.

PARTITION (GRAPH_POLICY 13.2): 2021-2024 for the anchor ONLY, 2022-2024 for every headline
  number. The 2025/2026 confirmation holdout is never read, joined, filtered, counted,
  plotted or described. # FILTER-POINT markers below; sorted(season.unique()) printed.

R2 CONVENTION: plain unweighted OLS R2, inherited unchanged from base.r2 (E0 convention).

WRITE SCOPE: this directory only. base.OUT is re-pointed here defensively so that no import
  side effect can write into the read-only E0 directory.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

E0 = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\E0_I0012_layer3_noncollinear"
OUTDIR = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\E1_I0012_survivor_2021drop"
sys.path.insert(0, E0)

import base as B                 # noqa: E402  shared loaders/helpers, reused not reimplemented
import f34_style_rest as F       # noqa: E402  F3 style family that contains the survivor

# --- WRITE-SCOPE GUARD: never let a reused helper write into the read-only E0 directory ---
B.OUT = OUTDIR
F.B.OUT = OUTDIR

DIM = "dpace"
TARGET = "reb"
FULL = [2021, 2022, 2023, 2024]
DROP = [2022, 2023, 2024]
HOLDOUT_FORBIDDEN = {2025, 2026}
N_PERM = 400
PUBLISHED_ANCHOR = 0.0010713241044830735
PUBLISHED_BETAS = {2021: 0.35599767969471996, 2022: 0.33477624294433783,
                   2023: 0.16743308359021705, 2024: 0.06401679555459161}


def guard(df, label, allowed):
    """Partition guard. Prints sorted(season.unique()) and hard-asserts."""
    s = sorted(int(x) for x in pd.unique(df["season"]))
    print("  [PARTITION] %-38s seasons=%s  n=%d" % (label, s, len(df)))
    assert not (set(s) & HOLDOUT_FORBIDDEN), "HOLDOUT TOUCHED at %s" % label
    assert set(s) <= set(allowed), "PARTITION VIOLATION at %s: %s" % (label, s)
    return df


def build(seasons):
    """Full survivor feature build for target=reb, using ONLY E0 code paths."""
    B.PARTITION = list(seasons)          # # FILTER-POINT (load_player/load_team filter on this)
    F.B.PARTITION = list(seasons)
    mp = guard(B.load_player(), "master_player after load", seasons)
    mt = guard(B.load_team(), "master_team after load", seasons)
    B.poss_sanity(mp)
    played = mp[(mp["minutes"].fillna(0) > 0) & (mp["possessions"] > 0)].copy()

    STY, tteam = F.build_team_style(mt)
    PS = F.player_style(played)
    opp_sty = STY.rename(columns={"team_id": "opp_team_id"}).drop(columns=["game_id"])

    d = B.build_base(played, TARGET)
    d = d.merge(opp_sty, on=["season", "opp_team_id", "gdate"], how="left")
    d = d.merge(PS, on=["season", "game_id", "player_id"], how="left")
    guard(d, "merged feature frame", seasons)
    return d, tteam


def effect(w, seasons, label):
    guard(w, "analysis frame -> " + label, seasons)
    r_all, per = B.collinearity(w, DIM)
    print("  collinearity corr(dpace, def_pre) within season = %+.4f | per season %s"
          % (r_all, {k: round(v, 3) for k, v in per.items()}))
    eff = B.screen_increment(w, DIM, label, seasons=list(seasons))
    rows = {r["scope"]: r for r in eff["rows"]}
    return eff, rows, r_all, per


def trend_test(w, seasons):
    """Formal decay test: does beta on O x Mres shrink linearly across 2022-2024?

    Fits y ~ O + D + O*D + Mres + O*Mres + t + O*t + Mres*t + O*Mres*t, where t is the
    centered season index. The coefficient on O*Mres*t IS the decay: negative => still dying.
    """
    g = w.copy()
    g["M"] = B.zwithin(g, DIM)
    g["Mres"] = B.resid_on(g["M"].values, [g["D"].values, g["OD"].values])
    sd = g["Mres"].std()
    if sd > 0:
        g["Mres"] /= sd
    g["OM"] = g["O"] * g["Mres"]
    idx = {s: i for i, s in enumerate(sorted(seasons))}
    g["t"] = g["season"].map(idx).astype(float)
    g["t"] = g["t"] - g["t"].mean()
    y = g["y"].values
    cols = [g["O"].values, g["D"].values, g["OD"].values, g["Mres"].values, g["OM"].values,
            g["t"].values, (g["O"] * g["t"]).values, (g["Mres"] * g["t"]).values,
            (g["OM"] * g["t"]).values]
    b = B.fit_beta(y, cols)
    r_no = B.r2(y, cols[:-1])
    r_yes = B.r2(y, cols)
    out = {"beta_OxM_at_partition_midpoint": float(b[5]),
           "beta_OxM_x_seasonindex": float(b[-1]),
           "dR2_of_the_decay_term": float(r_yes - r_no),
           "seasons": sorted(int(s) for s in seasons)}
    print("  TREND TEST  beta(O x Mres) at midpoint = %+.4f | beta(O x Mres x season) = %+.4f"
          "  (negative = still decaying) | dR2 of decay term = %.6f"
          % (out["beta_OxM_at_partition_midpoint"], out["beta_OxM_x_seasonindex"],
             out["dR2_of_the_decay_term"]))
    return out


def main():
    res = {}
    rng = np.random.default_rng(B.SEED)

    # ================================================================= STAGE A: ANCHOR
    B.hdr("STAGE A -- REPRODUCTION ANCHOR (2021-2024, exact E0 replication)")
    d_full, _ = build(FULL)
    w_full = B.prep_frame(d_full, extra_required=[DIM])
    eff_f, rows_f, r_all_f, per_f = effect(w_full, FULL, "ANCHOR_2021_2024")
    got = rows_f["POOLED"]["dR2_OxM"]
    betas_f = {int(s): rows_f[str(s)]["beta_OxM"] for s in FULL if str(s) in rows_f}
    dev = abs(got - PUBLISHED_ANCHOR)
    ok = dev < 5e-9 and all(abs(betas_f[s] - PUBLISHED_BETAS[s]) < 5e-9 for s in FULL)
    print("\n  ANCHOR pooled dR2_OxM  reproduced = %.10f   published = %.10f   |diff| = %.3e"
          % (got, PUBLISHED_ANCHOR, dev))
    for s in FULL:
        print("    beta_OxM %d  reproduced = %+.10f   published = %+.10f"
              % (s, betas_f[s], PUBLISHED_BETAS[s]))
    print("  ANCHOR REPRODUCED: %s" % ok)
    res["anchor_2021_2024"] = {
        "n": int(rows_f["POOLED"]["n"]),
        "pooled_dR2_OxM_reproduced": float(got),
        "pooled_dR2_OxM_published": PUBLISHED_ANCHOR,
        "abs_diff": float(dev),
        "per_season_beta_OxM_reproduced": {str(k): float(v) for k, v in betas_f.items()},
        "per_season_beta_OxM_published": {str(k): float(v) for k, v in PUBLISHED_BETAS.items()},
        "reproduced": bool(ok)}
    if not ok:
        print("\n  *** ANCHOR NOT REPRODUCED -- stopping. A re-run that cannot be anchored "
              "is not interpretable. ***")
        with open(os.path.join(OUTDIR, "results_raw.json"), "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2, default=float)
        return res

    # ================================================================= STAGE B: HEADLINE
    B.hdr("STAGE B -- HEADLINE RE-RUN, 2021 DROPPED (analysis stage), seasons 2022-2024")
    d_b = d_full[d_full["season"].isin(DROP)].copy()      # # FILTER-POINT <<< drop 2021
    guard(d_b, "feature frame after dropping 2021", DROP)
    w_b = B.prep_frame(d_b, extra_required=[DIM])
    eff_b, rows_b, r_all_b, per_b = effect(w_b, DROP, "DROP2021_2022_2024")
    betas_b = {int(s): rows_b[str(s)]["beta_OxM"] for s in DROP if str(s) in rows_b}
    pooled_b = rows_b["POOLED"]["dR2_OxM"]
    print("\n  PLACEBO (%d perms, same value-assignment construction as E0):" % N_PERM)
    plc_b, V_b = F.placebo(w_b, DIM, rng, n=N_PERM)
    V_b.assign(stage="B_drop2021_analysis_stage").to_csv(
        os.path.join(OUTDIR, "placebo_draws_drop2021.csv"), index=False)
    trend_b = trend_test(w_b, DROP)
    res["headline_2022_2024_drop_at_analysis_stage"] = {
        "n": int(rows_b["POOLED"]["n"]),
        "per_season_n": {str(s): int(rows_b[str(s)]["n"]) for s in DROP if str(s) in rows_b},
        "per_season_beta_OxM": {str(k): float(v) for k, v in betas_b.items()},
        "per_season_dR2_OxM": {str(s): float(rows_b[str(s)]["dR2_OxM"]) for s in DROP if str(s) in rows_b},
        "pooled_dR2_OxM": float(pooled_b),
        "pooled_beta_OxM": float(rows_b["POOLED"]["beta_OxM"]),
        "pooled_dR2_M": float(rows_b["POOLED"]["dR2_M"]),
        "collinearity_vs_overall_def": float(r_all_b),
        "collinearity_per_season": {str(k): float(v) for k, v in per_b.items()},
        "placebo": plc_b, "placebo_n_perm": N_PERM,
        "placebo_degenerate": bool(plc_b["dR2_OxM"]["sd"] == 0.0),
        "trend_test": trend_b}

    # ================================================================= STAGE C: VARIANT
    B.hdr("STAGE C -- VARIANT, 2021 dropped at the LOAD stage (2021 never read)")
    d_c, _ = build(DROP)
    w_c = B.prep_frame(d_c, extra_required=[DIM])
    eff_c, rows_c, r_all_c, per_c = effect(w_c, DROP, "DROP2021_LOADSTAGE")
    betas_c = {int(s): rows_c[str(s)]["beta_OxM"] for s in DROP if str(s) in rows_c}
    print("\n  PLACEBO (%d perms):" % N_PERM)
    plc_c, V_c = F.placebo(w_c, DIM, rng, n=N_PERM)
    V_c.assign(stage="C_drop2021_load_stage").to_csv(
        os.path.join(OUTDIR, "placebo_draws_drop2021_loadstage.csv"), index=False)
    trend_c = trend_test(w_c, DROP)
    res["variant_2022_2024_drop_at_load_stage"] = {
        "n": int(rows_c["POOLED"]["n"]),
        "per_season_beta_OxM": {str(k): float(v) for k, v in betas_c.items()},
        "pooled_dR2_OxM": float(rows_c["POOLED"]["dR2_OxM"]),
        "pooled_beta_OxM": float(rows_c["POOLED"]["beta_OxM"]),
        "collinearity_vs_overall_def": float(r_all_c),
        "placebo": plc_c, "placebo_n_perm": N_PERM,
        "placebo_degenerate": bool(plc_c["dR2_OxM"]["sd"] == 0.0),
        "trend_test": trend_c}

    # ================================================================= SUMMARY
    B.hdr("SUMMARY")
    print("  season   beta_OxM (E0 all-4)   beta_OxM (2022-24 re-run)")
    for s in FULL:
        a = "%+.4f" % betas_f[s]
        b_ = "%+.4f" % betas_b[s] if s in betas_b else "   dropped"
        print("  %6d   %19s   %25s" % (s, a, b_))
    print("\n  pooled dR2_OxM   2021-2024 = %.6f" % got)
    print("  pooled dR2_OxM   2022-2024 = %.6f   placebo mean %.7f sd %.7f frac>=real %.3f"
          % (pooled_b, plc_b["dR2_OxM"]["mean"], plc_b["dR2_OxM"]["sd"],
             plc_b["dR2_OxM"]["frac_ge"]))
    mono = all(betas_b[DROP[i]] >= betas_b[DROP[i + 1]] for i in range(len(DROP) - 1))
    print("  monotonic decay across 2022-2024: %s | 2024/2022 beta ratio = %.3f"
          % (mono, betas_b[2024] / betas_b[2022] if betas_b[2022] != 0 else float("nan")))
    res["monotonic_decay_2022_2024"] = bool(mono)

    # final partition re-assertion before write
    for lbl, fr in [("w_full", w_full), ("w_b", w_b), ("w_c", w_c)]:
        s = set(int(x) for x in pd.unique(fr["season"]))
        assert not (s & HOLDOUT_FORBIDDEN), "HOLDOUT in %s before write" % lbl
    with open(os.path.join(OUTDIR, "results_raw.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, default=float)
    print("\n  wrote results_raw.json")
    return res


if __name__ == "__main__":
    main()
